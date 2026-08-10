# treeebb_scraper_allfields.py
# Doel: alle "kenmerken/filters" per TreeEbb plant naar CSV, zonder beschrijving en zonder foto's.
# Je start dit door te dubbelklikken op START_TreeEbb_Scrape.bat
#
# Locatie: <projectroot>/scripts/scraper/. De output gaat naar <projectroot>/data/.
# Het script bepaalt de projectroot zelf, dus het maakt niet uit vanuit welke map je
# het aanroept en waar het project op je schijf staat.

import os
import re
import csv
import time
import random
import pathlib
import argparse
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager


# ====== Instellingen ======
# Dit bestand staat in <projectroot>/scripts/scraper/ ⇒ twee niveaus omhoog is de projectroot.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT_DIR = str(PROJECT_ROOT / "data")
TREEEBB_START_URL = "https://www.ebben.nl/nl/treeebb/"

OUT_CSV = os.path.join(OUTPUT_DIR, "treeebb_planten_allfields.csv")
URLS_TXT = os.path.join(OUTPUT_DIR, "treeebb_urls.txt")

REQUEST_DELAY = 0.5
MAX_RETRIES = 5

CSV_DELIM = ";"
CSV_ENCODING = "utf-8-sig"

TREEEBB_PATH_FRAGMENT = "/treeebb/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TreeEbbScraper/2.0; +local-run)"
}


def ensure_parent_dir(path_str: str):
    pathlib.Path(path_str).parent.mkdir(parents=True, exist_ok=True)


# ====== Selenium ======
def init_driver(headless: bool = True):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,10000")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)
    return driver


def accept_cookies(driver):
    keywords = ["accepteer", "akkoord", "ok", "alles toestaan", "accept", "agree", "allow"]
    try:
        time.sleep(1.0)
        for kw in keywords:
            xpath = f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw}')]"
            for b in driver.find_elements(By.XPATH, xpath):
                if b.is_displayed():
                    try:
                        b.click()
                        time.sleep(0.6)
                        return
                    except ElementClickInterceptedException:
                        pass
    except Exception:
        pass


def is_species_url(href: str) -> bool:
    if not href:
        return False
    try:
        u = urlparse(href)
    except Exception:
        return False
    if not u.netloc.endswith("ebben.nl"):
        return False
    if TREEEBB_PATH_FRAGMENT not in u.path:
        return False
    if "/pdf/" in u.path:
        return False
    last = u.path.rstrip("/").split("/")[-1]
    bad_parts = {"over-treeebb", "contact", "about-treeebb", "over-ebben"}
    if last in bad_parts:
        return False
    return "-" in last


def collect_species_urls(driver, max_scroll_rounds=140, sleep_s=1.0):
    driver.get(TREEEBB_START_URL)
    accept_cookies(driver)
    time.sleep(1.5)

    seen = set()
    stagnation_rounds = 0
    last_count = 0

    load_more_xpaths = [
        "//button[contains(., 'Meer') or contains(., 'meer') or contains(., 'Toon')]",
        "//a[contains(., 'Meer') or contains(., 'meer') or contains(., 'Toon')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'more')]",
    ]

    for _ in range(max_scroll_rounds):
        for a in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
            href = a.get_attribute("href")
            if is_species_url(href):
                seen.add(href.split("#")[0])

        # probeer eventueel "meer laden" te klikken
        clicked = False
        for xp in load_more_xpaths:
            try:
                for e in driver.find_elements(By.XPATH, xp):
                    if e.is_displayed():
                        e.click()
                        clicked = True
                        time.sleep(0.8)
                        break
                if clicked:
                    break
            except Exception:
                pass

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(sleep_s + random.uniform(0.0, 0.4))

        if len(seen) == last_count:
            stagnation_rounds += 1
        else:
            stagnation_rounds = 0
            last_count = len(seen)

        if stagnation_rounds >= 7:
            break

    return sorted(seen)


# ====== Parser (gebaseerd op jouw HTML-fragment) ======
def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _uniq(items):
    out, seen = [], set()
    for it in items:
        it = _clean(it)
        if not it or it in seen:
            continue
        out.append(it)
        seen.add(it)
    return out


def parse_species_page_allfields(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    name = ""
    h1 = soup.find("h1")
    if h1:
        name = _clean(h1.get_text(" ", strip=True))
    if not name and soup.title and soup.title.string:
        name = soup.title.string.strip().split("|")[0].strip()

    data = {"naam": name, "url": url}

    # Dit is precies het blok dat jij stuurde: <div class="plant-specs ...">
    specs = soup.select_one("div.plant-specs")
    if not specs:
        return data

    for group in specs.select("div.spec-group"):
        # CTA/marketing overslaan
        if "cta" in (group.get("class") or []):
            continue

        h3 = group.select_one("div.title h3, h3")
        if not h3:
            continue

        section = _clean(h3.get_text(" ", strip=True))
        if section.lower().startswith("foto"):
            continue
        if section.lower().startswith("kennismaken"):
            continue

        # Elke "inner" bevat een h4 + waarden
        for inner in group.select("div.inner"):
            h4 = inner.select_one("h4")
            if not h4:
                continue
            field = _clean(h4.get_text(" ", strip=True))
            if field.lower().startswith("foto"):
                continue

            classes = " ".join(inner.get("class") or []).lower()
            values = []

            if "minmaxval" in classes:
                vmin = inner.select_one("span.min")
                vmax = inner.select_one("span.max")
                unit = inner.select_one("span.unit")
                vmin_t = _clean(vmin.get_text(" ", strip=True)) if vmin else ""
                vmax_t = _clean(vmax.get_text(" ", strip=True)) if vmax else ""
                unit_t = _clean(unit.get_text(" ", strip=True)) if unit else ""
                if vmin_t and vmax_t:
                    values = [f"{vmin_t} - {vmax_t}{(' ' + unit_t) if unit_t else ''}".strip()]
                elif vmin_t:
                    values = [f"{vmin_t}{(' ' + unit_t) if unit_t else ''}".strip()]
                elif vmax_t:
                    values = [f"{vmax_t}{(' ' + unit_t) if unit_t else ''}".strip()]

            elif "iconselection" in classes:
                # iconselection: <span><span class="name">...</span></span>
                for n in inner.select("span.name"):
                    values.append(_clean(n.get_text(" ", strip=True)))

            else:
                # enumselection of generiek: <span class="on">waarde</span>
                for sp in inner.select("span.on"):
                    values.append(_clean(sp.get_text(" ", strip=True)))

            values = _uniq(values)
            if not values:
                continue

            key = f"{section} > {field}"
            data[key] = " | ".join(values)

    return data


# ====== Fetch ======
def fetch_html(url: str) -> str:
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=40)
            if r.status_code in (429, 500, 502, 503, 504):
                wait = min(30, 1.5 ** attempt) + random.uniform(0, 0.4)
                print(f"[warn] {r.status_code} voor {url} -> wachten {wait:.1f}s en opnieuw...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            wait = min(30, 1.5 ** attempt) + random.uniform(0, 0.6)
            print(f"[warn] fout bij ophalen ({attempt}/{MAX_RETRIES}) {url}: {e} -> wachten {wait:.1f}s")
            time.sleep(wait)
    raise RuntimeError(f"Kon pagina niet ophalen na {MAX_RETRIES} pogingen: {url} ({last_err})")


def main(headless=True, max_plants=None, delay=REQUEST_DELAY, resume=True, out_csv=OUT_CSV):
    ensure_parent_dir(out_csv)
    ensure_parent_dir(URLS_TXT)

    if resume and pathlib.Path(URLS_TXT).exists():
        urls = [line.strip() for line in pathlib.Path(URLS_TXT).read_text(encoding="utf-8").splitlines() if line.strip()]
        print(f"[info] {len(urls)} URL's geladen uit {URLS_TXT}")
    else:
        driver = init_driver(headless=headless)
        try:
            print("[info] Soort-URL's verzamelen (dit kan even duren)...")
            urls = collect_species_urls(driver)
            print(f"[ok] {len(urls)} soortpagina's gevonden")
            pathlib.Path(URLS_TXT).write_text("\n".join(urls), encoding="utf-8")
            print(f"[ok] URL-lijst opgeslagen in {URLS_TXT}")
        finally:
            driver.quit()

    if max_plants:
        urls = urls[:max_plants]

    rows = []
    all_keys = set(["naam", "url"])

    for i, u in enumerate(urls, 1):
        try:
            html = fetch_html(u)
            data = parse_species_page_allfields(html, u)
            rows.append(data)
            all_keys.update(data.keys())
            print(f"[{i}/{len(urls)}] {data.get('naam','')}")
        except Exception as e:
            print(f"[fout] {u} -> {e}")

        time.sleep(delay + random.uniform(0.0, 0.12))

    base_cols = ["naam", "url"]
    extra_cols = sorted(k for k in all_keys if k not in base_cols)
    fieldnames = base_cols + extra_cols

    with open(out_csv, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=CSV_DELIM, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"[klaar] {len(rows)} records opgeslagen in {out_csv}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="TreeEbb scraper (alle velden, excl. beschrijving & foto's).")
    ap.add_argument("--no-headless", action="store_true", help="Toon browservenster (standaard headless).")
    ap.add_argument("--max", type=int, default=None, help="Maximaal aantal planten (voor testen).")
    ap.add_argument("--delay", type=float, default=REQUEST_DELAY, help="Pauze (s) tussen detail-requests.")
    ap.add_argument("--fresh", action="store_true", help="Negeer bestaande URL-cache en verzamel opnieuw.")
    ap.add_argument("--out", type=str, default=OUT_CSV, help=f"Pad/naam van output CSV (default: {OUT_CSV})")

    args = ap.parse_args()

    main(
        headless=not args.no_headless,
        max_plants=args.max,
        delay=args.delay,
        resume=not args.fresh,
        out_csv=args.out,
    )

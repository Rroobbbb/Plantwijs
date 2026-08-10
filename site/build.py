#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build.py — de statische sitegenerator van de contentlaag van Beplantingswijzer.

Leest `site/content/**/*.md` (Markdown met YAML-frontmatter) en schrijft alleen de
pagina's met status `live` én een publicatiedatum die is aangebroken naar
`site/_site/`. Zo publiceert de cron-run van .github/workflows/site.yml vanzelf de
artikelen waarvan de datum is bereikt (zie docs/SEO_PLAN.md §5).

Afhankelijkheden: `markdown` en `pyyaml` (site/requirements.txt). Geen Node, geen
framework, geen externe CDN's of fonts.

Gebruik:
    python site/build.py                     # normale build
    python site/build.py --today 2026-12-01  # doe alsof het een andere dag is
    python site/build.py --out /tmp/site     # naar een andere uitvoermap

Uitvoerstructuur:
    _site/gids/<slug>/index.html     pagina's uit content/gids/
    _site/blog/<slug>/index.html     pagina's uit content/blog/
    _site/gids/index.html            overzicht van de live gidsen
    _site/sitemap-content.xml        sitemap met absolute URL's
    _site/site-static/site.css       huisstijl (meegekopieerd uit site/static/)
    _site/_redirects                 Netlify-regels (meegekopieerd)
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import markdown
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - alleen bij een kale omgeving
    sys.exit(
        "Ontbrekende afhankelijkheid: {}.\n"
        "Installeer met: pip install -r site/requirements.txt".format(exc.name)
    )

# ───────────────────────────── instellingen ─────────────────────────────

SITE_URL = "https://beplantingswijzer.nl"
SITE_NAAM = "Beplantingswijzer"

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
TEMPLATE_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
REDIRECTS_FILE = ROOT / "_redirects"
DEFAULT_OUT = ROOT / "_site"

# De CSS staat op /site-static/ en niet op /static/: dat laatste pad hoort bij de
# FastAPI-app achter de proxy (zie site/_redirects).
STATIC_URL = "/site-static"
CSS_URL = STATIC_URL + "/site.css"

STATUSSEN = ("concept", "geverifieerd", "live")

# Per contentmap: het label in het kruimelpad en of er een indexpagina bestaat om
# naartoe te linken. Onbekende mappen krijgen automatisch een label zonder index.
SECTIES: Dict[str, Dict[str, Any]] = {
    "gids": {"label": "Gids", "index": True, "index_url": "/gids/"},
    "blog": {"label": "Blog", "index": False, "index_url": "/blog/"},
}

GIDS_INDEX_TITEL = "Gids: beplanting, bodem en landschap in Nederland"
GIDS_INDEX_BESCHRIJVING = (
    "Alle gidsen van Beplantingswijzer op een rij: hoe je de bodem en het landschap "
    "van je eigen plek leest, en welke bomen en struiken daarbij passen."
)

MAANDEN = (
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
)

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TOKEN_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
WOORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
COMMENTAAR_RE = re.compile(r"<!--.*?-->\s*", re.DOTALL)

MD_EXTENSIES = ["extra", "sane_lists", "toc"]
MD_EXTENSIE_CONFIG = {"toc": {"permalink": False}}

# SEO-drempels uit docs/SEO_PLAN.md §6; overschrijding is een waarschuwing, geen fout.
MAX_TITEL = 60
MAX_DESCRIPTION = 160
MIN_INTERNE_LINKS = 3
MAX_ANTWOORD_WOORDEN = 50


class BuildError(Exception):
    """Fout in de content of in een template: de build stopt."""


# ───────────────────────────── datamodel ─────────────────────────────


@dataclass
class Page:
    """Eén contentbestand, al gecontroleerd en klaar om te renderen."""

    bron: Path                       # pad van het .md-bestand
    rel: str                         # pad t.o.v. content/, voor meldingen
    sectie: str                      # eerste map onder content/ ("gids", "blog", …)
    map_delen: List[str]             # mapdelen t.o.v. content/, incl. sectie
    slug: str
    title: str
    seo_title: str
    description: str
    cluster: str
    status: str
    publicatiedatum: dt.date
    bijgewerkt: Optional[dt.date]
    antwoord: str                    # citeerbaar antwoordblok (Markdown), mag leeg zijn
    faq: List[Dict[str, str]]
    bronnen: List[Dict[str, str]]
    body_md: str
    waarschuwingen: List[str] = field(default_factory=list)

    @property
    def url_pad(self) -> str:
        return "/" + "/".join(self.map_delen + [self.slug]) + "/"

    @property
    def url(self) -> str:
        return SITE_URL + self.url_pad

    @property
    def uitvoerpad(self) -> Path:
        return Path(*self.map_delen) / self.slug / "index.html"

    @property
    def laatst_gewijzigd(self) -> dt.date:
        return self.bijgewerkt or self.publicatiedatum


# ───────────────────────────── hulpfuncties ─────────────────────────────


def esc(waarde: Any) -> str:
    """HTML-escape inclusief aanhalingstekens (veilig in een attribuut)."""
    return html.escape(str(waarde), quote=True)


def nl_datum(datum: dt.date) -> str:
    """2026-08-10 → '10 augustus 2026'."""
    return "{} {} {}".format(datum.day, MAANDEN[datum.month - 1], datum.year)


def als_datum(waarde: Any, veld: str, herkomst: str) -> dt.date:
    """Accepteer een ISO-string of een door PyYAML herkende datum."""
    if isinstance(waarde, dt.datetime):
        return waarde.date()
    if isinstance(waarde, dt.date):
        return waarde
    if isinstance(waarde, str):
        try:
            return dt.date.fromisoformat(waarde.strip())
        except ValueError:
            pass
    raise BuildError(
        "{}: veld '{}' moet een datum in ISO-vorm zijn (JJJJ-MM-DD), gevonden: {!r}".format(
            herkomst, veld, waarde
        )
    )


def tekst(waarde: Any) -> str:
    return "" if waarde is None else str(waarde).strip()


def lees_template(naam: str) -> str:
    """Lees een template. Uit HTML-templates verdwijnt het commentaar: dat is
    documentatie voor de redacteur en hoort niet in de gepubliceerde pagina."""
    pad = TEMPLATE_DIR / naam
    if not pad.is_file():
        raise BuildError("Template ontbreekt: {}".format(pad))
    ruw = pad.read_text(encoding="utf-8")
    if pad.suffix == ".html":
        ruw = COMMENTAAR_RE.sub("", ruw)
    return ruw


def render(sjabloon: str, context: Dict[str, str], herkomst: str) -> str:
    """Vervang `{{ naam }}` door context['naam'] (één pass, inhoud wordt niet herscand)."""

    def vervang(match: "re.Match[str]") -> str:
        sleutel = match.group(1)
        if sleutel not in context:
            raise BuildError(
                "{}: onbekende template-variabele {{{{ {} }}}}".format(herkomst, sleutel)
            )
        return context[sleutel]

    return TOKEN_RE.sub(vervang, sjabloon)


def markdown_naar_html(bron: str) -> str:
    """Markdown → HTML. Tabellen krijgen een scrollbare wrapper (mobiel)."""
    md = markdown.Markdown(extensions=MD_EXTENSIES, extension_configs=MD_EXTENSIE_CONFIG)
    uit = md.convert(bron)
    uit = uit.replace("<table>", '<div class="table-scroll"><table>')
    uit = uit.replace("</table>", "</table></div>")
    return uit


def json_ld(data: Dict[str, Any]) -> str:
    """JSON-LD als scriptblok; `</` wordt ontsnapt zodat de tag niet vroeg sluit."""
    ruw = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return '<script type="application/ld+json">\n{}\n</script>'.format(ruw)


def aantal_woorden(bron: str) -> int:
    return len(WOORD_RE.findall(bron))


# ───────────────────────────── content lezen ─────────────────────────────


def split_frontmatter(ruw: str, herkomst: str) -> Tuple[Dict[str, Any], str]:
    """Splits '---\\n…\\n---\\n' van de rest van het bestand."""
    tekst_ = ruw.lstrip("﻿")
    if not tekst_.startswith("---"):
        raise BuildError(
            "{}: bestand begint niet met een frontmatter-blok ('---' op regel 1)".format(herkomst)
        )
    delen = re.split(r"^---\s*$", tekst_, maxsplit=2, flags=re.MULTILINE)
    if len(delen) < 3:
        raise BuildError("{}: frontmatter is niet afgesloten met '---'".format(herkomst))
    try:
        meta = yaml.safe_load(delen[1]) or {}
    except yaml.YAMLError as exc:
        raise BuildError("{}: frontmatter is geen geldige YAML — {}".format(herkomst, exc))
    if not isinstance(meta, dict):
        raise BuildError("{}: frontmatter moet een lijst van velden zijn".format(herkomst))
    return meta, delen[2].lstrip("\n")


def lees_faq(waarde: Any, herkomst: str) -> List[Dict[str, str]]:
    if waarde in (None, ""):
        return []
    if not isinstance(waarde, list):
        raise BuildError("{}: 'faq' moet een lijst zijn van items met 'vraag' en 'antwoord'".format(herkomst))
    items: List[Dict[str, str]] = []
    for nummer, item in enumerate(waarde, start=1):
        if not isinstance(item, dict):
            raise BuildError("{}: faq-item {} is geen blok met 'vraag' en 'antwoord'".format(herkomst, nummer))
        vraag = tekst(item.get("vraag"))
        antwoord = tekst(item.get("antwoord"))
        if not vraag or not antwoord:
            raise BuildError("{}: faq-item {} mist 'vraag' of 'antwoord'".format(herkomst, nummer))
        items.append({"vraag": vraag, "antwoord": antwoord})
    return items


def lees_bronnen(waarde: Any, herkomst: str) -> List[Dict[str, str]]:
    """`bronnen` mag een lijst tekst zijn, of blokken met 'titel' en optioneel 'url'."""
    if waarde in (None, ""):
        return []
    if not isinstance(waarde, list):
        raise BuildError("{}: 'bronnen' moet een lijst zijn".format(herkomst))
    items: List[Dict[str, str]] = []
    for nummer, item in enumerate(waarde, start=1):
        if isinstance(item, str):
            items.append({"titel": item.strip(), "url": ""})
            continue
        if not isinstance(item, dict):
            raise BuildError("{}: bron {} is geen tekst en geen blok met 'titel'".format(herkomst, nummer))
        titel = tekst(item.get("titel"))
        if not titel:
            raise BuildError("{}: bron {} mist 'titel'".format(herkomst, nummer))
        items.append({"titel": titel, "url": tekst(item.get("url"))})
    return items


def lees_pagina(pad: Path) -> Page:
    rel = pad.relative_to(CONTENT_DIR).as_posix()
    meta, body = split_frontmatter(pad.read_text(encoding="utf-8"), rel)

    verplicht = ("title", "description", "slug", "cluster", "status", "publicatiedatum")
    ontbreekt = [veld for veld in verplicht if not tekst(meta.get(veld))]
    if ontbreekt:
        raise BuildError("{}: frontmatter mist verplichte velden: {}".format(rel, ", ".join(ontbreekt)))

    status = tekst(meta["status"]).lower()
    if status not in STATUSSEN:
        raise BuildError(
            "{}: status '{}' bestaat niet; kies uit {}".format(rel, status, ", ".join(STATUSSEN))
        )

    slug = tekst(meta["slug"]).lower()
    if not SLUG_RE.match(slug):
        raise BuildError(
            "{}: slug '{}' mag alleen kleine letters, cijfers en koppeltekens bevatten".format(rel, slug)
        )

    map_delen = list(pad.relative_to(CONTENT_DIR).parts[:-1])
    if not map_delen:
        raise BuildError(
            "{}: zet het bestand in een sectiemap, bijvoorbeeld content/gids/ of content/blog/".format(rel)
        )

    titel = tekst(meta["title"])
    beschrijving = " ".join(tekst(meta["description"]).split())
    seo_title = tekst(meta.get("seo_title")) or titel

    pagina = Page(
        bron=pad,
        rel=rel,
        sectie=map_delen[0],
        map_delen=map_delen,
        slug=slug,
        title=titel,
        seo_title=seo_title,
        description=beschrijving,
        cluster=tekst(meta["cluster"]),
        status=status,
        publicatiedatum=als_datum(meta["publicatiedatum"], "publicatiedatum", rel),
        bijgewerkt=als_datum(meta["bijgewerkt"], "bijgewerkt", rel) if meta.get("bijgewerkt") else None,
        antwoord=tekst(meta.get("antwoord")),
        faq=lees_faq(meta.get("faq"), rel),
        bronnen=lees_bronnen(meta.get("bronnen"), rel),
        body_md=body,
    )

    # Zachte SEO-controles (docs/SEO_PLAN.md §6): melden, niet blokkeren.
    if len(pagina.seo_title) > MAX_TITEL:
        pagina.waarschuwingen.append(
            "titel is {} tekens (richtlijn ≤{}); gebruik 'seo_title' voor een kortere <title>".format(
                len(pagina.seo_title), MAX_TITEL
            )
        )
    if len(pagina.description) > MAX_DESCRIPTION:
        pagina.waarschuwingen.append(
            "description is {} tekens (richtlijn ≤{})".format(len(pagina.description), MAX_DESCRIPTION)
        )
    if pagina.antwoord and aantal_woorden(pagina.antwoord) > MAX_ANTWOORD_WOORDEN:
        pagina.waarschuwingen.append(
            "antwoordblok telt {} woorden (richtlijn ≤{})".format(
                aantal_woorden(pagina.antwoord), MAX_ANTWOORD_WOORDEN
            )
        )
    if re.search(r"^#\s", pagina.body_md, flags=re.MULTILINE):
        pagina.waarschuwingen.append(
            "body bevat een '# '-kop; de H1 komt uit 'title', begin in de tekst bij '## '"
        )
    return pagina


def lees_alle_paginas() -> List[Page]:
    if not CONTENT_DIR.is_dir():
        raise BuildError("Contentmap ontbreekt: {}".format(CONTENT_DIR))
    paginas = [lees_pagina(pad) for pad in sorted(CONTENT_DIR.rglob("*.md"))]

    gezien: Dict[str, str] = {}
    for pagina in paginas:
        if pagina.url_pad in gezien:
            raise BuildError(
                "Dubbele URL {}: {} en {}".format(pagina.url_pad, gezien[pagina.url_pad], pagina.rel)
            )
        gezien[pagina.url_pad] = pagina.rel
    return paginas


def publiceerbaar(pagina: Page, vandaag: dt.date) -> Tuple[bool, str]:
    """Mag deze pagina gebouwd worden? Zo nee: de reden voor de melding."""
    if pagina.status != "live":
        return False, "status '{}' (alleen 'live' wordt gebouwd)".format(pagina.status)
    if pagina.publicatiedatum > vandaag:
        return False, "publicatiedatum {} is nog niet aangebroken (vandaag {})".format(
            pagina.publicatiedatum.isoformat(), vandaag.isoformat()
        )
    return True, ""


# ───────────────────────────── HTML bouwen ─────────────────────────────


def kruimelpad_html(pagina: Page) -> str:
    delen = ['<a href="/">Start</a>']
    sectie = SECTIES.get(pagina.sectie, {})
    if sectie.get("index"):
        delen.append('<a href="{}">{}</a>'.format(sectie["index_url"], esc(sectie["label"])))
    delen.append("<span aria-current=\"page\">{}</span>".format(esc(pagina.title)))
    return '<nav class="kruimels" aria-label="Kruimelpad">{}</nav>'.format(
        '<span class="kruimel-sep" aria-hidden="true">›</span>'.join(delen)
    )


def kruimelpad_jsonld(pagina: Page) -> Dict[str, Any]:
    items = [{"@type": "ListItem", "position": 1, "name": "Start", "item": SITE_URL + "/"}]
    sectie = SECTIES.get(pagina.sectie, {})
    if sectie.get("index"):
        items.append(
            {
                "@type": "ListItem",
                "position": 2,
                "name": sectie["label"],
                "item": SITE_URL + sectie["index_url"],
            }
        )
    items.append(
        {"@type": "ListItem", "position": len(items) + 1, "name": pagina.title, "item": pagina.url}
    )
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


def artikel_jsonld(pagina: Page) -> Dict[str, Any]:
    organisatie = {"@type": "Organization", "name": SITE_NAAM, "url": SITE_URL + "/"}
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": pagina.title,
        "description": pagina.description,
        "inLanguage": "nl-NL",
        "url": pagina.url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": pagina.url},
        "datePublished": pagina.publicatiedatum.isoformat(),
        "dateModified": pagina.laatst_gewijzigd.isoformat(),
        "isAccessibleForFree": True,
        "author": organisatie,
        "publisher": organisatie,
    }


def faq_jsonld(pagina: Page, antwoorden_html: List[str]) -> Dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "inLanguage": "nl-NL",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["vraag"],
                "acceptedAnswer": {"@type": "Answer", "text": antwoord},
            }
            for item, antwoord in zip(pagina.faq, antwoorden_html)
        ],
    }


def faq_html(pagina: Page, antwoorden_html: List[str]) -> str:
    if not pagina.faq:
        return ""
    items = "".join(
        "<details class=\"faq-item\">"
        "<summary>{}</summary>"
        '<div class="faq-antwoord">{}</div>'
        "</details>".format(esc(item["vraag"]), antwoord)
        for item, antwoord in zip(pagina.faq, antwoorden_html)
    )
    return (
        '<section class="faq" aria-labelledby="faq-titel">'
        '<h2 class="faq-titel" id="faq-titel">Veelgestelde vragen</h2>'
        "{}"
        "</section>"
    ).format(items)


def bronnen_html(pagina: Page) -> str:
    if not pagina.bronnen:
        return ""
    regels = []
    for bron in pagina.bronnen:
        if bron["url"]:
            regels.append(
                '<li><a href="{}" rel="noopener">{}</a></li>'.format(esc(bron["url"]), esc(bron["titel"]))
            )
        else:
            regels.append("<li>{}</li>".format(esc(bron["titel"])))
    return (
        '<section class="bronnen" aria-labelledby="bronnen-titel">'
        '<h2 class="bronnen-titel" id="bronnen-titel">Bronnen</h2>'
        "<ul>{}</ul>"
        "</section>"
    ).format("".join(regels))


def meta_regel_html(pagina: Page) -> str:
    minuten = max(1, round(aantal_woorden(pagina.body_md) / 200))
    delen = [
        'Gepubliceerd op <time datetime="{}">{}</time>'.format(
            pagina.publicatiedatum.isoformat(), esc(nl_datum(pagina.publicatiedatum))
        )
    ]
    if pagina.bijgewerkt and pagina.bijgewerkt != pagina.publicatiedatum:
        delen.append(
            'bijgewerkt op <time datetime="{}">{}</time>'.format(
                pagina.bijgewerkt.isoformat(), esc(nl_datum(pagina.bijgewerkt))
            )
        )
    delen.append("leestijd ongeveer {} minuten".format(minuten))
    return " · ".join(delen)


def bouw_pagina_html(pagina: Page, base: str, artikel: str) -> Tuple[str, List[str]]:
    """Render één contentpagina. Geeft de HTML terug plus extra waarschuwingen."""
    waarschuwingen: List[str] = []
    body = markdown_naar_html(pagina.body_md)

    interne_links = len(re.findall(r'href="/', body))
    if interne_links < MIN_INTERNE_LINKS:
        waarschuwingen.append(
            "{} interne link(s) in de tekst (richtlijn ≥{}: satelliet ↔ pijler ↔ tool)".format(
                interne_links, MIN_INTERNE_LINKS
            )
        )

    antwoord_blok = ""
    if pagina.antwoord:
        antwoord_blok = (
            '<aside class="antwoord" aria-label="Kort antwoord">{}</aside>'.format(
                markdown_naar_html(pagina.antwoord)
            )
        )

    faq_antwoorden = [markdown_naar_html(item["antwoord"]) for item in pagina.faq]

    scripts = [json_ld(artikel_jsonld(pagina)), json_ld(kruimelpad_jsonld(pagina))]
    if pagina.faq:
        scripts.append(json_ld(faq_jsonld(pagina, faq_antwoorden)))

    kicker = ""
    if pagina.cluster:
        kicker = '<p class="page-kicker">{}</p>'.format(esc(pagina.cluster))

    inhoud = render(
        artikel,
        {
            "breadcrumb": kruimelpad_html(pagina),
            "kicker": kicker,
            "title": esc(pagina.title),
            "lead": esc(pagina.description),
            "meta": meta_regel_html(pagina),
            "antwoord": antwoord_blok,
            "body": body,
            "faq": faq_html(pagina, faq_antwoorden),
            "bronnen": bronnen_html(pagina),
        },
        pagina.rel,
    )

    return (
        render(
            base,
            {
                "title_tag": esc(pagina.seo_title),
                "description": esc(pagina.description),
                "canonical": esc(pagina.url),
                "og_type": "article",
                "og_title": esc(pagina.title),
                "css_url": CSS_URL,
                "jsonld": "\n".join(scripts),
                "main": inhoud,
            },
            pagina.rel,
        ),
        waarschuwingen,
    )


def bouw_gids_index_html(gidsen: List[Page], base: str, sjabloon: str) -> str:
    url = SITE_URL + SECTIES["gids"]["index_url"]

    if gidsen:
        kaarten = "".join(
            '<li class="kaart">'
            '<a class="kaart-link" href="{url}">'
            '<span class="kaart-kicker">{cluster}</span>'
            '<span class="kaart-titel">{titel}</span>'
            '<span class="kaart-tekst">{omschrijving}</span>'
            '<span class="kaart-meer">Lees de gids</span>'
            "</a></li>".format(
                url=esc(pagina.url_pad),
                cluster=esc(pagina.cluster),
                titel=esc(pagina.title),
                omschrijving=esc(pagina.description),
            )
            for pagina in gidsen
        )
        lijst = '<ul class="kaart-grid">{}</ul>'.format(kaarten)
    else:
        lijst = '<p class="leeg">Er staan nog geen gidsen online. Ze verschijnen hier zodra ze klaar zijn.</p>'

    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": GIDS_INDEX_TITEL,
        "description": GIDS_INDEX_BESCHRIJVING,
        "url": url,
        "inLanguage": "nl-NL",
        "isPartOf": {"@type": "WebSite", "name": SITE_NAAM, "url": SITE_URL + "/"},
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(gidsen),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": nummer,
                    "name": pagina.title,
                    "url": pagina.url,
                }
                for nummer, pagina in enumerate(gidsen, start=1)
            ],
        },
    }

    inhoud = render(
        sjabloon,
        {
            "title": esc(GIDS_INDEX_TITEL),
            "lead": esc(GIDS_INDEX_BESCHRIJVING),
            "aantal": "{} {}".format(len(gidsen), "gids" if len(gidsen) == 1 else "gidsen"),
            "items": lijst,
        },
        "gids-index.html",
    )

    return render(
        base,
        {
            "title_tag": esc(GIDS_INDEX_TITEL),
            "description": esc(GIDS_INDEX_BESCHRIJVING),
            "canonical": esc(url),
            "og_type": "website",
            "og_title": esc(GIDS_INDEX_TITEL),
            "css_url": CSS_URL,
            "jsonld": json_ld(schema),
            "main": inhoud,
        },
        "gids-index.html",
    )


def bouw_sitemap(urls: List[Tuple[str, dt.date]], sjabloon: str) -> str:
    regels = "\n".join(
        "  <url>\n    <loc>{}</loc>\n    <lastmod>{}</lastmod>\n  </url>".format(
            esc(url), datum.isoformat()
        )
        for url, datum in urls
    )
    return render(sjabloon, {"urls": regels}, "sitemap-content.xml")


# ───────────────────────────── build ─────────────────────────────


def leeg_uitvoermap(uit: Path) -> None:
    """Verwijder een eerdere build, zodat er geen verweesde pagina's blijven staan."""
    if uit.resolve() in (ROOT.resolve(), *ROOT.resolve().parents):
        raise BuildError("Weiger te bouwen naar {}: kies een eigen uitvoermap".format(uit))
    if uit.exists():
        shutil.rmtree(uit)


def schrijf(pad: Path, inhoud: str) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(inhoud, encoding="utf-8", newline="\n")


def build(uit: Path, vandaag: dt.date) -> int:
    base = lees_template("base.html")
    artikel = lees_template("page.html")
    gids_index = lees_template("gids-index.html")
    sitemap = lees_template("sitemap-content.xml")

    paginas = lees_alle_paginas()

    print("{} — statische sitebuild".format(SITE_NAAM))
    print("  bron     {}".format(CONTENT_DIR))
    print("  uitvoer  {}".format(uit))
    print("  datum    {}".format(vandaag.isoformat()))
    print("")

    leeg_uitvoermap(uit)

    gebouwd: List[Page] = []
    overgeslagen = 0
    waarschuwingen = 0

    for pagina in paginas:
        mag, reden = publiceerbaar(pagina, vandaag)
        if not mag:
            overgeslagen += 1
            print("  overgeslagen  {:<34} {}".format(pagina.rel, reden))
            continue

        html_uit, extra = bouw_pagina_html(pagina, base, artikel)
        schrijf(uit / pagina.uitvoerpad, html_uit)
        gebouwd.append(pagina)
        print("  gebouwd       {:<34} → {}".format(pagina.rel, pagina.url_pad))
        for melding in pagina.waarschuwingen + extra:
            waarschuwingen += 1
            print("    let op      {}".format(melding))

    gidsen = sorted(
        (pagina for pagina in gebouwd if pagina.sectie == "gids"), key=lambda p: p.title.lower()
    )
    schrijf(uit / "gids" / "index.html", bouw_gids_index_html(gidsen, base, gids_index))
    print("")
    print("  gids/index.html          overzicht met {} gids(en)".format(len(gidsen)))

    sitemap_urls: List[Tuple[str, dt.date]] = [
        (SITE_URL + SECTIES["gids"]["index_url"], max([p.laatst_gewijzigd for p in gidsen] or [vandaag]))
    ]
    sitemap_urls += [(pagina.url, pagina.laatst_gewijzigd) for pagina in gebouwd]
    schrijf(uit / "sitemap-content.xml", bouw_sitemap(sitemap_urls, sitemap))
    print("  sitemap-content.xml      {} URL's".format(len(sitemap_urls)))

    if STATIC_DIR.is_dir():
        doel = uit / STATIC_URL.strip("/")
        shutil.copytree(STATIC_DIR, doel, dirs_exist_ok=True)
        bestanden = sorted(pad.name for pad in doel.rglob("*") if pad.is_file())
        print("  {:<24} {}".format(STATIC_URL.strip("/") + "/", ", ".join(bestanden)))
    else:
        print("  let op: {} bestaat niet; er is geen CSS meegekopieerd".format(STATIC_DIR))

    if REDIRECTS_FILE.is_file():
        shutil.copyfile(REDIRECTS_FILE, uit / "_redirects")
        print("  _redirects               gekopieerd (Netlify-proxy naar de backend)")
    else:
        print("  let op: {} ontbreekt; Netlify proxyt dan niets naar de backend".format(REDIRECTS_FILE))

    print("")
    print(
        "  {} bestand(en) gelezen · {} gebouwd · {} overgeslagen · {} waarschuwing(en)".format(
            len(paginas), len(gebouwd), overgeslagen, waarschuwingen
        )
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bouwt de statische contentlaag van Beplantingswijzer naar site/_site/."
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help="uitvoermap (standaard: site/_site)"
    )
    parser.add_argument(
        "--today",
        default=None,
        metavar="JJJJ-MM-DD",
        help="doe alsof het deze datum is; handig om een geplande publicatie vooraf te bekijken",
    )
    args = parser.parse_args(argv)

    try:
        vandaag = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    except ValueError:
        print("Fout: --today verwacht een datum als 2026-09-01", file=sys.stderr)
        return 2

    try:
        return build(args.out, vandaag)
    except BuildError as exc:
        print("\nBuild gestopt: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# PlantWijs — Plan "compleet & werkbaar pakket" (aug 2026)

## Status (bijgewerkt 10 augustus 2026)

| WP | Onderwerp | Status | Waar het staat |
|----|-----------|--------|----------------|
| 1 | Backend-refactor naar package | **Af** | `plantwijs/{config,main}.py`, `plantwijs/routers/`, `plantwijs/services/`; `api.py` is nog slechts een compat-shim. Oude UI leeft op `/legacy`. |
| 2a | Kennislaag-content (NL) | **Af** | `content/context_descriptions.yaml`, `maatregelen.yaml`, `wortelbare_diepte.yaml`, met `content/README.md` als redactiehandleiding. |
| 2b | Services context/wortel/advies | **Af** | `plantwijs/services/{context,wortel,advies}.py`; `/advies/geo` levert `landschap`, `wortelbare_diepte` en `aanbevolen_beplanting`; `/api/context` bestaat. |
| 3 | Nieuwe frontend | **Af** | `static/index.html` + `static/css/app.css` + `static/js/*` (vanilla JS, geen build-step). |
| 4 | PDF-locatierapport | **Af** | `plantwijs/services/report.py`, endpoint `/advies/pdf` in `plantwijs/routers/export.py`. |
| 6 | AI- en machine-toegankelijkheid | **Af** | `plantwijs/services/geocode.py` (adres → coördinaten), `services/rapport_md.py` (`format=md`), `routers/seo.py` (`/llms.txt`, `/robots.txt`, `/sitemap.xml`), NL-omschrijvingen in de OpenAPI. |
| 5 | Documentatie, opruimen, deploy-gereedheid | **Af** | `README.md`, `docs/DEPLOY.md`, `render.yaml`, `scripts/` (zie hieronder), aangevulde `.gitignore`. Testsuite: 179 tests in `tests/`. |
| QA | End-to-end browsertest + fixronde | **Af** | Fixronde 1 uitgevoerd (bodemfilter-canonicalisatie, rapport-defaults, petgaten/leemarm-herkenning, gewogen vormen-scoring, pdf-vlag in /api/health, dataset-ondergrens). Testsuite: 229 groen. |

Wat er bij WP5 concreet is verplaatst: `Scraper/` → `scripts/scraper/`, en `build_dataset.py` +
`normalize_treeebb_csv.py` → `scripts/`. Alle harde paden (`C:\PlantWijs`, `C:\Rob\...`) in die
bestanden zijn vervangen door projectroot-detectie, zodat de tools werken vanuit elke map en op elke
schijf. De applicatie verwijst nergens naar deze scripts.

Nog open buiten QA: het `Backup/`-archief en de map `Git repo/` (leeg) zijn niet opgeruimd, en de
Ellenberg-herkoppeling uit `scripts/build_dataset.py` staat nog steeds op fase 2.

## Doel
Bewoners klikken op de kaart (of zoeken hun adres) en krijgen:
1. **Locatieprofiel** — FGR, bodem (BRO), grondwatertrap→vochtklasse, AHN-hoogte, geomorfologie (GMM), Natuurlijk Systeem Nederland (NSN/BKNSN).
2. **Landschapsverhaal** — hoe dit landschap is ontstaan en hoe je het als bewoner kunt versterken.
3. **Concreet advies** — passende beplantingsvormen (houtwal, heg, boomgaard, …) en een soortenlijst op maat (1644 soorten, TreeEbb + SL2020-status), te filteren en te exporteren (CSV/Excel/**PDF-rapport**).

## Uitgangssituatie
- Werkende basis: `Plantwijs/api.py` (v3.9.7, 2715 regels, FastAPI + embedded HTML/JS/Leaflet).
- Nieuwste experiment: `Backup/api 202512151837 pdf3.py` — bevat PDF-rapport (reportlab) en een `context_descriptions.yaml`-loader; dat YAML-bestand is **nooit gemaakt**.
- `wortelbare_diepte.yaml` (kennisregels bodem+Gt+NSN → wortelbare diepte) ligt klaar in de projectroot, nog niet aangesloten.
- Venv bevatte alleen nog scraper-pakketten; app-dependencies zijn opnieuw geïnstalleerd (incl. pyyaml, reportlab, pillow, pytest, httpx).
- Veiligheidskopie huidige code: `Backup/api 20260810 voor grote refactor.py`.

## Doelarchitectuur
```
Plantwijs/
  api.py                 # compat-shim: from plantwijs.main import app
  plantwijs/
    config.py            # paden, env, constanten
    main.py              # create_app(), lifespan (NSN-warmup), routers, /static mount
    services/
      dataset.py         # CSV laden/normaliseren/cachen
      pdok.py            # FGR (WFS), bodem, Gt/GHG/GLG, AHN, GMM (WMS GetFeatureInfo)
      nsn.py             # NSN-bron (zip/geojson) + SQLite R-tree index + lookup
      context.py         # content/context_descriptions.yaml → landschapsverhaal
      wortel.py          # content/wortelbare_diepte.yaml → bandbreedte wortelbare diepte
      advies.py          # locatieprofiel + kennislaag + soortfilter samenvoegen
      report.py          # PDF-locatierapport (reportlab; basis: pdf3-backup)
      geocode.py         # adres → coördinaten via PDOK Locatieserver (WP6)
      rapport_md.py      # hetzelfde advies als Markdown-rapport (format=md, WP6)
    routers/
      pages.py           # / (nieuwe frontend), /legacy (oude UI)
      plants.py          # /api/plants, /api/wms_meta, /api/diag/*, /api/health, /api/nsn, /api/admin/reload
      advies.py          # /advies/geo, /api/context
      export.py          # /export/csv, /export/xlsx, /advies/pdf
      seo.py             # /llms.txt, /robots.txt, /sitemap.xml (WP6)
  static/                # nieuwe frontend (vanilla JS + Leaflet via CDN, geen build-step)
  content/               # kennislaag (YAML): context_descriptions, maatregelen, wortelbare_diepte
  data/                  # ongewijzigd (treeebb CSV, LBK_BKNSN_2023.zip, SL2020 xlsx)
  scripts/               # dataset-tools: build_dataset.py, normalize_treeebb_csv.py
    scraper/             # TreeEbb-scraper + SL2020-verrijking (verplaatst uit Scraper/)
  tests/                 # pytest
  docs/                  # PLAN.md, API.md, FRONTEND.md, DEPLOY.md
  README.md              # instructie voor eigenaar en vrijwilligers
  render.yaml            # Render Blueprint (web service, free plan)
```

## Werkpakketten (uitvoering door Opus-agents)
| WP | Inhoud | Eigenaar-bestanden |
|----|--------|--------------------|
| 1 | Backend-refactor naar package; gedrag identiek; bekende bugs fixen; oude UI naar `/legacy` | `plantwijs/`, `api.py`, `requirements*.txt`, `start.bat`, `.gitignore` |
| 2a | Kennislaag-content schrijven (NL): context per FGR/bodem/vocht/GMM/NSN, beplantingsvormen-catalogus | `content/` |
| 2b | Services `context.py`, `wortel.py`, `advies.py` + verrijkt `/advies/geo` + `/api/context` | `plantwijs/services/{context,wortel,advies}.py`, `plantwijs/routers/advies.py`, `tests/` |
| 3 | Nieuwe frontend (dé polish): flow, huisstijl, mobiel, toegankelijkheid | `static/` |
| 4 | PDF-locatierapport op basis van pdf3-backup + kennislaag | `plantwijs/services/report.py`, `plantwijs/routers/export.py` |
| 5 | Tests afronden, README/DEPLOY, scripts opruimen, Render-config | `tests/`, `README.md`, `docs/`, `scripts/`, `render.yaml` |
| 6 | AI-toegankelijkheid: adres-geocoding in `/advies/geo`, `format=md`, `/llms.txt`, `robots.txt`, sitemap, OpenAPI-metadata | `plantwijs/routers/`, `plantwijs/services/geocode.py`, `static/robots.txt` e.d. |
| QA | End-to-end browsertest (desktop+mobiel), fixronde | n.t.b. |

Volgorde: WP1 ∥ WP2a → WP3 ∥ WP2b → WP4 ∥ WP6 → WP5 → QA.

## WP6 — AI- en machine-toegankelijkheid (toegevoegd 10 aug)
Doel: een AI-agent (ChatGPT/Claude/Perplexity met web-toegang) kan met één URL-fetch het complete locatie-advies lezen, zonder API-sleutels of MCP.
- `/advies/geo` accepteert ook `adres=` (server-side geocoding via PDOK Locatieserver; response bevat gevonden adres + coördinaten).
- `format=md` ⇒ volledig rapport als `text/markdown` (profiel, landschapsverhaal, wortelruimte, aanbevolen vormen, soortenlijst-top + verwijzing naar CSV-export).
- `/llms.txt` met gebruiksuitleg en voorbeeld-URL's; `robots.txt` die AI-crawlers toestaat; `sitemap.xml`; JSON-LD op de landingspagina (WP3); OpenAPI-titels/omschrijvingen netjes (gratis `/docs`).
- Eerlijke verwachting: vindbaarheid hangt af van indexering/verwijzingen; dit pakket maximaliseert de kans en maakt de site volledig zelfbedienend zodra een agent hem kent.

## Kwaliteitseisen
- Bestaande endpoints blijven backwards-compatible (zie docs/API.md); nieuwe velden zijn additief.
- Elke PDOK-bron kan uitvallen zonder dat de rest breekt; per bron een status in de response.
- Frontend: Nederlands, mobile-first, licht/donker, WCAG AA-contrast, skeleton-loaders, nette lege/fout-staten.
- Kennisteksten: feitelijk conservatief, "indicatief" waar het kaartinterpretatie betreft, geen verzonnen soortenclaims (soortsuggesties bestaan in de dataset).
- Tests: unit (vochtklasse-mapping, bodem-canonicalisatie, wortelregels, contextmatching) + API-smoke met gemockte PDOK.

## Bewust buiten scope (fase 2, zie "Nog doe.txt")
- Echte database (CSV volstaat bij 1644 rijen), eigen domein/hosting-migratie, Google/SEO-campagne (basis-metatags doen we wél), native app.
- Ellenberg-herkoppeling aan de TreeEbb-set (oude pipeline `build_dataset.py` blijft beschikbaar in `scripts/`).

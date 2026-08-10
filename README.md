# Beplantingswijzer

*Productnaam: Beplantingswijzer (voorheen PlantWijs); de technische pakketnaam `plantwijs` en de repo-naam blijven ongewijzigd.*

Beplantingswijzer geeft voor elke plek in Nederland een beplantingsadvies op maat. Je klikt op de kaart of
vult een adres in, en de applicatie haalt bij PDOK het locatieprofiel op — fysisch-geografische
regio, bodemtype, grondwatertrap en de daaruit afgeleide vochtklasse, maaiveldhoogte (AHN),
geomorfologie en het natuurlijk systeem (BKNSN 2023). Dat profiel wordt gecombineerd met een
kennislaag in `content/`: een landschapsverhaal (hoe dit landschap is ontstaan en hoe je het met
beplanting kunt versterken), een indicatie van de bewortelbare diepte, en passende
beplantingsvormen zoals houtwal, heg of boomgaard. Daarbij hoort een soortenlijst van 1644 bomen en
struiken (TreeEbb, verrijkt met de status inheems/ingeburgerd/exoot uit de Standaardlijst Flora
2020), gefilterd op de standplaats en te exporteren als CSV, Excel of PDF-rapport.

## Features

- **Locatieprofiel** uit live PDOK-services; valt een bron uit, dan blijft de rest werken en meldt
  `bronnen_status` per bron wat er misging.
- **Landschapsverhaal en maatregelen** uit de kennislaag (`content/*.yaml`), in het Nederlands,
  geschreven voor bewoners zonder voorkennis.
- **Indicatieve bewortelbare diepte** op basis van bodem + grondwatertrap + natuurlijk systeem.
- **Soortenlijst met filters** op licht, vocht, bodem, beplantingstype en status; invasieve soorten
  standaard uitgesloten.
- **Exports**: CSV, XLSX en een PDF-locatierapport.
- **Kaart-frontend** (Leaflet, vanilla JS, geen build-step) met WMS-overlays van de gebruikte
  kaartlagen.
- **Machineleesbaar**: alles via GET zonder sleutel of account, met `format=md`, `/llms.txt` en een
  OpenAPI-beschrijving op `/docs`.

## Mappenstructuur

| Pad | Inhoud |
|---|---|
| `api.py` | Compat-shim: `uvicorn api:app` blijft werken; de app zelf zit in `plantwijs/`. |
| `plantwijs/` | De applicatie: `config.py` (paden/env), `main.py` (app-factory), `routers/` (endpoints), `services/` (dataset, PDOK, NSN, kennislaag, rapporten). |
| `static/` | Frontend: `index.html`, `css/`, `js/`, `assets/`. `legacy.html` is de oude UI, bereikbaar via `/legacy`. |
| `content/` | Kennislaag in YAML (landschapsverhalen, beplantingsvormen, wortelregels). Zie `content/README.md`. |
| `data/` | Brondata: TreeEbb-CSV, SL2020-checklist, BKNSN-zip. |
| `out/` | Uitvoer van `scripts/build_dataset.py` (oude Ellenberg-pipeline). |
| `scripts/` | Onderhoudstools: `scraper/` (TreeEbb ophalen en verrijken), `build_dataset.py`, `normalize_treeebb_csv.py`. Draaien niet mee in de webapp. |
| `tests/` | Pytest-suite (unit + API-smoke met gemockte PDOK). |
| `docs/` | `PLAN.md` (plan en status), `API.md` (contract), `FRONTEND.md`, `DEPLOY.md`. |

## Lokaal draaien

Vereist: Python 3.11 (zie `runtime.txt`).

```powershell
cd C:\Rob\Beplantingswijzer\Plantwijs
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Starten kan op twee manieren:

```powershell
start.bat
```

of handmatig, met de venv actief:

```powershell
python -m uvicorn api:app --reload --port 9000
```

Daarna: <http://127.0.0.1:9000> (kaart), <http://127.0.0.1:9000/docs> (API-documentatie),
<http://127.0.0.1:9000/api/health> (statuscheck).

De eerste start bouwt een index op de BKNSN-data; dat duurt eenmalig een minuut of wat en de index
wordt in de tijdelijke map van het systeem bewaard. Daarna gaat opstarten meteen.

Optionele omgevingsvariabelen:

| Variabele | Betekenis |
|---|---|
| `PLANTWIJS_CSV` | Pad naar een andere soorten-CSV; gaat vóór de bestanden in `data/` en `out/`. |
| `PLANTWIJS_ONLINE_CSV_URL` | Alternatieve online CSV, alleen gebruikt als er lokaal niets gevonden wordt. |
| `PLANTWIJS_ADMIN_KEY` | Sleutel voor `/api/admin/reload`; zonder deze variabele is dat endpoint dicht. |

## Data-bestanden en hoe je ze ververst

In `data/` staan:

| Bestand | Wat het is |
|---|---|
| `treeebb_planten_allfields.csv` | De soortenlijst waar de app op draait (1644 rijen). |
| `SL2020 Checklist Flora NL.xlsx` | Standaardlijst Flora NL 2020: NSR-status en Nederlandse namen. |
| `LBK_BKNSN_2023.zip` | Natuurlijk Systeem Nederland (32 MB); de app leest de GeoJSON rechtstreeks uit de zip. |
| `treeebb_urls.txt` | URL-cache van de scraper, zodat een herhaalde run niet opnieuw hoeft te crawlen. |

De soortenlijst ververs je in drie stappen vanuit de projectroot, met de venv actief. De scraper
haalt ~1650 pagina's op en draait ruim een half uur.

1. **Scrapen** — `scripts\scraper\START_TreeEbb_Scrape.bat` (dubbelklikken kan ook). Schrijft
   `data\treeebb_planten_allfields.csv` en ververst `data\treeebb_urls.txt`.
2. **Verrijken** — `python scripts\scraper\verrijk_treeebb_met_sl2020.py`. Voegt de kolommen
   `nsr_status` en `status_nl` toe op basis van de SL2020-checklist. Maakt eerst een `.bak`.
3. **Normaliseren (optioneel)** — `python scripts\normalize_treeebb_csv.py`. Maakt multi-waardes
   consistent (` / ` als scheidingsteken). Maakt eerst een `.bak`.

De CSV blijft op zijn plek in `data/`; er is geen extra kopieerstap. Herstart daarna de server, of
roep `/api/admin/reload?key=...` aan om de cache te legen zonder herstart. Details over de scraper
staan in `scripts/scraper/README.txt`.

`scripts/build_dataset.py` is de oudere pipeline die de verspreidingsatlas met Ellenberg-waarden
koppelt en naar `out/` schrijft. De app gebruikt die uitvoer alleen als terugvaloptie; het script is
bewaard voor als de Ellenberg-koppeling weer opgepakt wordt.

## De kennislaag bewerken

Alle teksten en kennisregels staan als YAML in `content/`: `context_descriptions.yaml`
(landschapsverhalen per kaartwaarde), `maatregelen.yaml` (catalogus beplantingsvormen) en
`wortelbare_diepte.yaml` (regels voor de bewortelbare diepte). Je hebt geen programmeerkennis nodig
om ze aan te passen. Lees eerst **`content/README.md`**: daar staan de matchconventies, de velden per
entry, de schrijfregels en hoe je je wijziging controleert.

## De API in het kort

Alle endpoints zijn GET en hebben geen sleutel nodig (behalve `/api/admin/reload`).

| Endpoint | Doel |
|---|---|
| `/advies/geo?lat=..&lon=..` of `?adres=..` | Volledig advies voor één locatie. |
| `/advies/pdf` | Hetzelfde advies als PDF-rapport. |
| `/api/plants` | Soortenlijst met filters. |
| `/api/context` | Eén landschapsverhaal op categorie + kaartwaarde. |
| `/export/csv`, `/export/xlsx` | Gefilterde soortenlijst als bestand. |
| `/api/wms_meta` | URL's en laagnamen van de WMS-overlays voor de kaart. |
| `/api/health` | Statuscheck: aantal rijen, databron, NSN-status, versie. |

De interactieve documentatie staat op `/docs`. Het volledige contract — inclusief alle velden en
foutgedrag — staat in [`docs/API.md`](docs/API.md).

## AI-toegang

Beplantingswijzer is zo gebouwd dat een AI-agent of script het advies met één HTTP-GET kan lezen, zonder
sleutel, account of MCP-server. `GET /llms.txt` beschrijft in gewoon tekstformaat wat de site doet en
welke URL's je gebruikt, met voorbeelden. Zet je `&format=md` achter een `/advies/geo`-aanroep, dan
komt het complete advies terug als Markdown-rapport (`text/markdown`) in plaats van JSON: profiel,
landschapsverhaal, wortelruimte, passende beplantingsvormen en een soortentabel. Verder zijn er
`/robots.txt` (AI-crawlers expliciet toegestaan), `/sitemap.xml` en een OpenAPI-beschrijving met
Nederlandse omschrijvingen op `/openapi.json`.

## Tests draaien

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

De tests doen geen netwerk-calls: PDOK wordt gemockt. Draai ze voordat je iets in `plantwijs/` of
`content/` wijzigt en nadat je klaar bent.

## Deployen

De applicatie draait als één web-service (`uvicorn api:app`) en heeft geen database nodig. Het
stappenplan voor Render — build- en startcommando, welke databestanden mee moeten, omgevings-
variabelen, koude start en geheugengebruik — staat in [`docs/DEPLOY.md`](docs/DEPLOY.md). De
bijbehorende service-definitie staat in `render.yaml` in deze map.

# Beplantingswijzer deployen (Render)

*Productnaam: Beplantingswijzer (voorheen PlantWijs); de technische pakketnaam `plantwijs` en de repo-naam blijven ongewijzigd.*

Beplantingswijzer is één web-service: een FastAPI-app die door uvicorn wordt gedraaid. Er is geen database,
geen achtergrondworker en geen build-step voor de frontend. Alles wat de app nodig heeft staat in de
repo of wordt live bij PDOK opgehaald. Deze handleiding beschrijft Render, maar elk platform dat een
Python-webservice kan draaien (Fly.io, Railway, een eigen VPS met systemd) werkt met dezelfde build-
en startcommando's.

## 1. Wat er in de repo moet staan

| Nodig | Pad | Toelichting |
|---|---|---|
| Ja | `api.py`, `plantwijs/` | De applicatie. |
| Ja | `static/` | Frontend; wordt gemount op `/static` en geserveerd op `/`. |
| Ja | `content/` | Kennislaag (YAML). Zonder deze map blijven `landschap`, `wortelbare_diepte` en `aanbevolen_beplanting` leeg. |
| Ja | `requirements.txt` | Build-invoer. |
| Ja | `render.yaml` | Service-definitie (Blueprint); zie stap 2b. |
| Ja | `runtime.txt` | Pint Python 3.11.9 voor platforms die dit bestand lezen. |
| Zie §3 | `data/treeebb_planten_allfields.csv` | De soortenlijst (≈0,9 MB). |
| Zie §3 | `data/SL2020 Checklist Flora NL.xlsx` | Nederlandse namen bij de wetenschappelijke namen (0,2 MB). Ontbreekt hij, dan blijven Nederlandse namen leeg; de app draait door. |
| Zie §4 | `data/LBK_BKNSN_2023.zip` | Natuurlijk Systeem Nederland, **32 MB**. Ontbreekt hij, dan is het NSN-veld leeg; de rest werkt gewoon. |
| Nee | `.venv/`, `__pycache__/`, `out/`, `scripts/`, `tests/`, `docs/`, `Backup/` | Niet nodig om te draaien. `scripts/`, `tests/` en `docs/` mogen mee (paar honderd kB) maar worden op de server niet gebruikt; `.venv/` en `out/` horen niet in Git en staan in `.gitignore`. |

## 2. Service aanmaken

### 2a. Handmatig, via het dashboard

1. New → Web Service → koppel de GitHub-repo `Rroobbbb/plantwijs`.
2. Region: **Frankfurt** (dichtst bij de gebruikers en bij PDOK).
3. Runtime: **Python 3**.
4. Build Command:
   ```
   pip install -r requirements.txt
   ```
5. Start Command:
   ```
   uvicorn api:app --host 0.0.0.0 --port $PORT
   ```
   `$PORT` wordt door Render gezet; hardcode nooit 9000. `--reload` mag hier niet mee: dat is
   alleen voor lokaal.
6. Health Check Path: `/api/health`. Dat endpoint doet geen netwerk-calls en bouwt geen NSN-index,
   dus het antwoordt snel.
7. Instance Type: **Free**.
8. Environment Variables: zie §5. Zet in elk geval `PYTHON_VERSION` op `3.11.9`.

### 2b. Via `render.yaml` (aanbevolen)

`render.yaml` in de projectroot bevat dezelfde instellingen. Kies in Render voor New → Blueprint en
wijs de repo aan; Render leest het bestand en maakt de service aan. Voordeel: de configuratie staat
in versiebeheer en een nieuwe omgeving is met één klik gelijk. Bij de eerste deploy vraagt Render om
een waarde voor `PLANTWIJS_ADMIN_KEY` (die staat op `sync: false` en zit dus niet in de repo).

## 3. De soortenlijst op de server krijgen — drie routes

`plantwijs/config.py` zoekt de CSV in vaste volgorde en stopt bij de eerste die laadt. Je hoeft er
dus maar één te regelen.

1. **`PLANTWIJS_CSV` (env-var).** Absoluut of relatief pad naar een CSV. Gaat vóór alles. Handig als
   je de dataset buiten Git houdt, bijvoorbeeld op een Render Disk (betaald plan) of een pad dat je
   in de build-stap vult.
2. **Bestand in de repo (standaard).** `data/treeebb_planten_allfields.csv`, en als terugval
   `out/treeebb_planten_allfields.csv`, `out/plantwijs_full_semicolon.csv`,
   `out/plantwijs_full.csv`. Dit is de eenvoudigste route: 0,9 MB, prima in Git, en de app start
   zonder externe afhankelijkheid.
3. **Online fallback (GitHub raw).** Vindt de app lokaal niets, dan haalt hij de CSV op via
   `https://raw.githubusercontent.com/Rroobbbb/plantwijs/main/data/treeebb_planten_allfields.csv`
   (en dezelfde `out/`-varianten als terugval). Met `PLANTWIJS_ONLINE_CSV_URL` wijs je een andere
   URL aan. Let op: dit werkt alleen bij een publieke repo, kost bij elke koude start een download,
   en de gedownloade CSV wordt niet op schijf bewaard. Bedoeld als vangnet, niet als hoofdroute.

`/api/health` laat in `dataset.source` zien welke route gewonnen heeft (`file` of `online`) en in
`dataset.rows` hoeveel rijen geladen zijn — bij een gezonde deploy 1644.

## 4. Het NSN-bestand (32 MB) — meenemen of niet

`data/LBK_BKNSN_2023.zip` bevat de kaart Natuurlijk Systeem Nederland. De app leest de GeoJSON
rechtstreeks uit de zip; uitpakken is niet nodig en niet gewenst.

- **Meenemen in de repo.** 32 MB blijft ruim onder GitHub's waarschuwingsgrens van 50 MB en de harde
  limiet van 100 MB per bestand, dus Git LFS is niet nodig. Elke `git clone` en elke Render-build
  sleept die 32 MB wel mee. Dit is de eenvoudigste werkende opzet.
- **Weglaten.** Zonder het bestand meldt de log `[NSN] bron: niet gevonden`, geeft `/api/health`
  `nsn.status = "ontbreekt"`, blijft het veld `nsn` in `/advies/geo` leeg en zegt `bronnen_status.nsn`
  `ontbreekt`. Alle andere bronnen (FGR, bodem, Gt, AHN, GMM) en de soortenlijst werken normaal. Je
  verliest het NSN-landschapsverhaal.
- **Alternatief.** Een losse `data/nsn_natuurlijk_systeem.geojson` wordt ook herkend en gaat vóór de
  zip. Die is veel groter en dus juist minder geschikt voor Git. Elke andere `.zip` met een
  `.geojson` erin in `data/` wordt ook gevonden.

## 5. Omgevingsvariabelen

| Variabele | Verplicht | Waarde / betekenis |
|---|---|---|
| `PYTHON_VERSION` | Aanbevolen | `3.11.9`. Render kiest anders zijn eigen standaardversie. `runtime.txt` staat er voor platforms die die conventie volgen. |
| `PLANTWIJS_ADMIN_KEY` | Nee | Zelfgekozen geheime string. Alleen daarmee werkt `GET /api/admin/reload?key=...`, waarmee je de dataset-cache leegt zonder redeploy. Zonder deze variabele geeft dat endpoint altijd 401 — dat is de veilige standaard. Zet hem nooit in de repo. |
| `PLANTWIJS_CSV` | Nee | Pad naar een alternatieve soorten-CSV (§3, route 1). |
| `PLANTWIJS_ONLINE_CSV_URL` | Nee | Alternatieve URL voor de online fallback (§3, route 3). |
| `PORT` | Nee | Wordt door Render gezet en door het startcommando gebruikt. Zelf niet invullen. |

De kennislaag heeft geen env-var: `plantwijs/services/{context,wortel,advies}.py` en
`report.py` lezen `content/` altijd relatief aan de projectmap. Wil je die map elders kunnen
neerzetten (bijvoorbeeld een `CONTEXT_DESC_PATH`), dan is dat een codewijziging in
`plantwijs/config.py`; op dit moment bestaat die variabele niet.

## 6. Koude start en de NSN-index in `/tmp`

Bij het opstarten roept de lifespan-hook `warm_nsn()` aan. Die zoekt de NSN-bron en bouwt zo nodig
een SQLite R-tree-index in de tijdelijke map van het systeem
(`/tmp/plantwijs_nsn/nsn_index.sqlite`, lokaal `%TEMP%\plantwijs_nsn\`). Aandachtspunten:

- De index is ongeveer **100 MB op schijf** en het bouwen duurt bij een koude start **enkele
  minuten**. Zolang hij bouwt geeft `/api/health` `nsn.status = "index_bouwt"` en valt een
  NSN-lookup terug op een trage stream-scan van de zip.
- `/tmp` is **efemeer**. Bij elke deploy, herstart en — op het gratis plan — bij elke spin-up na
  inactiviteit is de index weg en wordt hij opnieuw gebouwd. Op het gratis plan valt de service na
  ongeveer een kwartier zonder verkeer stil; de eerste bezoeker daarna wacht dus op de koude start.
- Render start de health check pas nadat de app boot; duurt het indexeren te lang, dan kan de
  eerste deploy als "unhealthy" worden gemarkeerd. Twee uitwegen: het NSN-bestand weglaten (§4), of
  een betaald plan met een persistente Disk nemen en de index daarop laten landen (dat laatste
  vraagt wel een aanpassing van `NSN_INDEX_DIR` in `plantwijs/config.py`).
- De index wordt gevalideerd op een signatuur van de bron; vervang je de zip, dan bouwt hij zichzelf
  automatisch opnieuw.

## 7. Geheugen (512 MB op het gratis plan)

Het gratis plan geeft 512 MB RAM. Daar past Beplantingswijzer in, maar met beperkte marge:

- De NSN-data wordt **nooit volledig in RAM geladen**; features worden per stuk uit de zip gelezen
  en in SQLite gezet, en lookups gaan via de on-disk index. Dat is precies waarom die index bestaat.
- De soorten-CSV (1644 rijen) staat wel als pandas-DataFrame in het geheugen. Dat is enkele MB's.
- Draai **één worker**. Het startcommando doet dat al: geen `--workers 2` toevoegen, want elke
  worker is een eigen proces met een eigen DataFrame-kopie.
- `reportlab` en `pillow` worden pas bij `/advies/pdf` echt aangesproken; een groot rapport is de
  zwaarste request die de service kent.
- Loopt de service tegen het geheugenplafond (Render meldt "Out of memory" en herstart), kijk dan
  eerst naar het aantal workers en daarna naar gelijktijdige PDF-requests.

## 8. Eigen domein en HTTPS

1. Render → de service → Settings → Custom Domains → domein toevoegen (bijvoorbeeld
   `beplantingswijzer.nl` en `www.beplantingswijzer.nl`).
2. Bij je DNS-provider de door Render getoonde records zetten: een `CNAME` voor `www` naar de
   `onrender.com`-hostnaam, en voor het kale domein een `ALIAS`/`ANAME` als je provider dat
   ondersteunt, anders de A-records die Render opgeeft.
3. Render vraagt daarna automatisch een Let's Encrypt-certificaat aan en vernieuwt het; HTTP wordt
   naar HTTPS geleid. Reken op vijf minuten tot een uur voordat DNS is doorgedrongen.
4. Controleer na afloop dat `/llms.txt`, `/robots.txt` en `/sitemap.xml` op het nieuwe domein de
   juiste absolute URL's tonen: die worden afgeleid van de aanvraag-URL, dus dat gaat vanzelf goed
   zodra het domein actief is.

## 9. Controle na een deploy

| Check | Verwachting |
|---|---|
| `GET /api/health` | `ok: true`, `dataset.rows: 1644`, `nsn.status: ok` (of `index_bouwt` vlak na een start). |
| `GET /` | De kaart laadt. |
| `GET /advies/geo?adres=Beekbergen&format=md` | Markdown-rapport met profiel, landschapsverhaal en soortentabel. |
| `GET /docs` | OpenAPI-documentatie met Nederlandse omschrijvingen. |
| `GET /llms.txt` | Plain-text uitleg met absolute URL's op het juiste domein. |
| Logs bij de start | `[NSN] bron: ZIP LBK_BKNSN_2023.zip` en daarna `[NSN] index klaar`. |

## 10. Veelvoorkomende problemen

| Symptoom | Oorzaak en oplossing |
|---|---|
| Deploy faalt op `pyproj` of `pandas` | Verkeerde Python-versie. Zet `PYTHON_VERSION` op `3.11.9`. |
| `Geen dataset gevonden` in de log | CSV ontbreekt én de online fallback kon niet worden opgehaald (repo privé of geen uitgaand verkeer). Zie §3. |
| `nsn: null` in elk advies | Het NSN-bestand ontbreekt of de index is nog niet klaar. Zie §4 en §6. |
| Eerste bezoek duurt heel lang | Spin-up van het gratis plan plus het opnieuw bouwen van de NSN-index. Zie §6. |
| Nederlandse namen ontbreken | `data/SL2020 Checklist Flora NL.xlsx` staat niet in de repo. |
| Advies zonder landschapsverhaal | `content/` ontbreekt in de deploy. |
| Nieuwe CSV geüpload, app toont oude data | Cache. Roep `/api/admin/reload?key=...` aan (vereist `PLANTWIJS_ADMIN_KEY`) of herstart de service. |

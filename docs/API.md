# Beplantingswijzer API-contract (v4)

*Productnaam: Beplantingswijzer (voorheen PlantWijs); de technische pakketnaam `plantwijs` en de repo-naam blijven ongewijzigd.*

Alle endpoints zijn GET. Bestaande endpoints en hun parameters/velden blijven ongewijzigd; alles onder "NIEUW" is additief. Frontend (WP3) bouwt tegen dít contract; backend (WP1/2b/4) implementeert het exact.

## GET /api/plants
Query: `q`, `toon_inheems`, `toon_ingeburgerd`, `toon_exoot` (bool), `exclude_invasief` (bool, default true), `licht` (multi: schaduw|halfschaduw|zon), `vocht` (multi: zeer droog|droog|vochtig|nat|zeer nat), `bodem` (multi: zand|klei|leem|veen), `beplantingstype` (multi: boom|heester), `sort`, `desc`.

Response: `{ "count": int, "items": [ { "naam", "wetenschappelijke_naam", "beplantingstype", "status_nl", "invasief", "standplaats_licht", "vocht", "bodem"?, "grondsoorten", "hoogte", "breedte", "winterhardheidszone", ... } ] }`

## GET /advies/geo
Query: `lat`, `lon` (verplicht) + dezelfde status/invasief-params als /api/plants.

Response (bestaande velden ongewijzigd):
```jsonc
{
  "fgr": "Hogere zandgronden",        // of "Onbekend"
  "bodem": "zand",                     // gecanoniseerd (zand|klei|leem|veen) of ruwe naam
  "bodem_detail": "Petgaten",          // ruwe bodemkaart-term als die afwijkt van `bodem`, anders null
  "bodem_bron": "BRO Bodemkaart WMS",
  "gt_code": "VIo",                    // Gt-code of null
  "vocht": "droog",                    // vochtklasse of null
  "vocht_bron": "BRO Gt/GLG WMS",
  "ahn": "12.34",                      // hoogte in m (string, 2 dec) of null
  "ahn_bron": "PDOK AHN WMS (DTM 0.5m)",
  "gmm": "Dekzandrug",                // omschrijving landvorm of null
  "gmm_bron": "BRO Geomorfologische kaart (GMM) WMS",
  "nsn": "Droog zandlandschap — ...",  // NSN/BKNSN-label of null
  "advies": [ /* plantenrijen, zelfde vorm als /api/plants items */ ],
  "elapsed_ms": 1234,

  // ── NIEUW (additief) ──
  "landschap": {                       // per categorie een verhaal of null
    "fgr":   { "titel": str, "ontstaan": str, "versterken": [str], "bron": str },
    "nsn":   { ... } | null,
    "gmm":   { ... } | null,
    "bodem": { ... } | null,
    "vocht": { ... } | null
  },
  "wortelbare_diepte": {
    "klasse": "matig", "band_cm": "60-100",
    "indicatie": str, "toelichting": str
  } | null,
  "aanbevolen_beplanting": [
    { "vorm": "Houtwal", "omschrijving": str, "waarom_hier": str, "voorbeeldsoorten": [str] }
  ],
  "bronnen_status": { "fgr": "ok|leeg|fout", "bodem": "...", "gwt": "...", "ahn": "...", "gmm": "...", "nsn": "ok|leeg|fout|ontbreekt" }
}
```

## GET /api/context  (NIEUW)
Query: `category` (fgr|nsn|gmm|bodem|vocht), `value` (ruwe kaartwaarde).
Response: `{ "titel", "ontstaan", "versterken": [], "bron" }` of `404 {"error":"not_found"}`.

## GET /advies/pdf  (NIEUW)
Query: zelfde als /advies/geo, plus optioneel `licht`/`vocht`/`bodem`/`beplantingstype` filters.
Response: `application/pdf` (attachment `beplantingswijzer_rapport.pdf`). Zolang WP4 niet klaar is: `501 {"error":"pdf_nog_niet_beschikbaar"}`.

## GET /export/csv en /export/xlsx
Ongewijzigd; zelfde query-params als /api/plants.

## GET /api/wms_meta
Ongewijzigd: `{ fgr|bodem|gt|ghg|glg|ahn|gmm: { "url", "layer", "title" } }` — frontend bouwt hiermee de WMS-overlays.

## GET /api/health  (NIEUW)
`{ "ok": true, "dataset": { "rows": int, "source": str }, "nsn": { "status": "ok|index_bouwt|ontbreekt" }, "pdf_beschikbaar": bool, "versie": str }`

`pdf_beschikbaar` is true zodra de server `services.report` kan importeren (reportlab + Pillow aanwezig). De frontend zet hiermee de PDF-knop aan of uit; er wordt geen testrequest op /advies/pdf meer gedaan.

## AI-toegang (WP6, additief)
- `/advies/geo` accepteert `adres=` als alternatief voor `lat`/`lon` (server-side geocoding, PDOK Locatieserver `free`-endpoint, beste match). Response krijgt extra veld `"locatie": { "adres_gevonden": str|null, "lat": float, "lon": float }`. Geen match ⇒ `404 {"error":"adres_niet_gevonden"}`.
- `/advies/geo?...&format=md` ⇒ `text/markdown; charset=utf-8`: volledig rapport in secties (Jouw plek / Jouw landschap / Wortelruimte / Wat kun jij doen / Passende soorten als tabel, max 40 rijen + verwijzing naar `/export/csv`). `format=json` (default) ongewijzigd.
- Rapporten (`format=md` en `/advies/pdf`) volgen zonder `toon_*`-parameters de standaardkeuze van de website: inheems + ingeburgerd aan, exoot uit. Expliciete `toon_*` winnen. `format=json` en `/api/plants` blijven ongewijzigd: niets meegegeven = alles tonen. Beide rapporten vermelden het toegepaste statusfilter.
- `GET /llms.txt` — plain text: wat de site is, welke URL's een agent gebruikt, voorbeelden. `GET /robots.txt` — sta AI-crawlers expliciet toe. `GET /sitemap.xml` — minimaal (/, /llms.txt, /docs).
- OpenAPI (`/openapi.json`, `/docs`) met nette NL-omschrijvingen per endpoint.

## Gedragsafspraken
- Elke PDOK-bron die faalt of leeg is ⇒ veld `null` + `bronnen_status` zegt waarom; nooit een 500 door één kapotte bron.
- `/advies/geo` kan bij allereerste NSN-indexbouw lang duren; daarna < ~3 s. Frontend toont skeleton/progresmelding.
- Alle teksten NL; `Cache-Control: no-store` op HTML, normale caching op /static assets.

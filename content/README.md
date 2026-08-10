# content/ — de kennislaag van PlantWijs

Deze map bevat de **inhoud** van PlantWijs: de Nederlandse teksten en de kennisregels.
Er staat geen applicatiecode in. De services in `plantwijs/services/` lezen deze
bestanden in en zetten ze om naar de velden `landschap`, `wortelbare_diepte` en
`aanbevolen_beplanting` uit `docs/API.md`.

Alle teksten zijn geschreven voor bewoners zonder voorkennis (taalniveau B1) en zijn
feitelijk conservatief: algemeen geldende landschapsvorming, geen lokale claims.

## Bestanden

| Bestand | Wat het is |
|---|---|
| `context_descriptions.yaml` | Landschapsverhalen per kaartwaarde: hoe het landschap is ontstaan en hoe je het met beplanting kunt versterken. Gegroepeerd in vijf categorieën: `fgr`, `bodem`, `vocht`, `gmm`, `nsn`. |
| `maatregelen.yaml` | Catalogus van beplantingsvormen voor bewoners en erven (houtwal, heg, boomgaard, griend, …), met per vorm bij welk landschap en welke vochtklasse hij past. |
| `wortelbare_diepte.yaml` | Kennisregels bodem + Gt + NSN → indicatieve wortelbare diepte. **Verbatim gekopieerd** uit de projectroot; niet inhoudelijk bewerkt. |
| `_inventaris_nsn.txt` | Werkdocument: alle waarden die in `data/LBK_BKNSN_2023.zip` voorkomen, met aantallen. Referentie bij het onderhouden van de `nsn`-categorie. Wordt niet door de applicatie ingelezen. |

## Matchconventie

Elke entry heeft twee sleutels waarmee een kaartwaarde aan een verhaal wordt gekoppeld:

- **`match_exact`** — volledige kaartwaarden, in kleine letters. Wordt vergeleken op gelijkheid.
- **`match`** — deelteksten, in kleine letters. Wordt vergeleken met "komt voor in".

De aanbevolen volgorde voor de matcher:

1. Normaliseer de kaartwaarde: trim, kleine letters, meervoudige spaties samenvoegen.
2. Is de waarde leeg of `null`? Gebruik direct de fallback.
3. Loop alle entries in de categorie af en vergelijk op `match_exact` (gelijkheid). Eerste treffer wint.
4. Geen treffer? Loop de entries **in bestandsvolgorde** af en vergelijk op `match` (deeltekst). Eerste treffer wint.
5. Nog steeds geen treffer? Gebruik de entry met lege `match` én lege `match_exact`: de fallback.

```python
def norm(s):
    return " ".join(str(s or "").strip().lower().split())

def zoek(entries, waarde):
    v = norm(waarde)
    fallback = next((e for e in entries if not e["match"] and not e["match_exact"]), None)
    if not v:
        return fallback
    for e in entries:
        if any(norm(m) == v for m in e["match_exact"]):
            return e
    for e in entries:
        if any(norm(m) in v for m in e["match"] if norm(m)):
            return e
    return fallback
```

### Waarom de volgorde in het bestand uitmaakt

`match` werkt op deeltekst, dus een korte term kan per ongeluk in een langere
kaartwaarde vallen. Daarom staan **specifieke entries altijd boven algemene**.
Voorbeelden uit `nsn`:

- `ontgonnen_hoogveen` staat boven `hoogveen`, anders vangt `hoogveen` allebei.
- `beekdal_veen` en `beekdal_zand_leem` staan boven `beekdal`.
- `pingoruine` staat boven `depressie`, want het label bevat het woord "laagten".
- `es` staat vrijwel onderaan, want "es" komt als deeltekst voor in "depressie",
  "restgeul", "veenrest" en "vlaktes".
- `water` staat onder `zoetwatergetijdenafzetting` en `zoutwatergetijdenafzetting`.

Beide strategieën (met en zonder `match_exact`) leveren voor alle 49 voorkomende
NSN-waarden hetzelfde resultaat. Verplaats entries dus niet zonder de dekking
opnieuw te controleren.

## Een entry toevoegen of wijzigen

1. Zoek de juiste categorie in `context_descriptions.yaml` onder `categorieen:`.
2. Voeg een entry toe met **alle** velden: `id`, `match_exact`, `match`, `titel`,
   `ontstaan`, `versterken`, `bron`.
   - `id` — stabiele sleutel in kleine letters met underscores. Wordt gebruikt door
     `past_bij` in `maatregelen.yaml`; hernoemen betekent daar ook aanpassen.
   - `ontstaan` — 3 tot 6 zinnen over hoe dit landschap is ontstaan.
   - `versterken` — 4 tot 6 concrete maatregelen die een bewoner zelf kan nemen.
   - `bron` — waar de kaartwaarde vandaan komt.
3. Zet de entry **op de juiste plek in de volgorde**: boven elke entry waarvan de
   `match`-termen een deeltekst van jouw kaartwaarde zijn.
4. Gebruik `>-` voor lange teksten (gevouwen blok, geen afsluitende newline) en
   houd de inspringing van het bestand aan.
5. Valideer:

```powershell
.venv\Scripts\python.exe -c "import yaml; yaml.safe_load(open(r'content\context_descriptions.yaml', encoding='utf-8')); print('OK')"
```

## Soortnamen

In `maatregelen.yaml` staat elke voorbeeldsoort als **`Nederlandse naam (Wetenschappelijke naam)`**,
bijvoorbeeld `Zomereik (Quercus robur)`.

Dat is bewust: de dataset `data/treeebb_planten_allfields.csv` heeft in de kolom `naam`
uitsluitend **wetenschappelijke** namen en geen Nederlandse. Door beide te noteren is de
tekst leesbaar voor bewoners én machinaal koppelbaar aan de soortenlijst. De
wetenschappelijke naam tussen haakjes komt letterlijk voor in die kolom; uitlezen kan met
een regex op de tekst tussen haakjes.

**Elke soortnaam die je toevoegt — ook in lopende tekst — moet in de dataset bestaan.**
Controleren:

```powershell
.venv\Scripts\python.exe -c "import pandas as pd; d=pd.read_csv(r'data\treeebb_planten_allfields.csv', sep=',', dtype=str); print('Quercus robur'.lower() in set(d['naam'].str.lower()))"
```

Let op: de CSV is **komma**-gescheiden, niet puntkomma.

## Stijlafspraken

- Nederlands, B1-niveau: korte zinnen, gewone woorden, actieve vorm. Vaktermen zoals
  podzol, kwel of graft mogen, maar leg ze in dezelfde zin uit.
- Warm maar zakelijk. Geen emoji, geen uitroeptekens, geen marketing-superlatieven.
- Feitelijk conservatief. Algemeen geldende landschapsvorming is prima; twijfel je over
  een detail, laat het weg of formuleer algemener. Geen lokale of historische claims die
  je niet kunt onderbouwen.
- Elke categorie heeft een `onbekend`-fallback met lege `match` én lege `match_exact`.

## Bronnen van de kaartwaarden

| Categorie | Bron | Voorbeeldwaarden |
|---|---|---|
| `fgr` | Fysisch-Geografische Regio's (PDOK WFS, property `fgr`) | Hogere Zandgronden, Heuvelland, Rivierengebied |
| `bodem` | BRO Bodemkaart (PDOK WMS), gecanoniseerd door de backend | zand, klei, leem, veen |
| `vocht` | BRO Grondwatertrappen Gt (PDOK WMS), omgezet naar vochtklasse | zeer nat, nat, vochtig, droog, zeer droog |
| `gmm` | BRO Geomorfologische kaart (PDOK WMS), veld met de omschrijving | Dekzandrug, Oeverwal, Uiterwaard |
| `nsn` | BKNSN 2023, `data/LBK_BKNSN_2023.zip`, property `Subtype_na` | Dekzandrug, Beekdal zand/leem, Kreekrug |

### Aandachtspunten bij de NSN-bron

- De properties in de GeoJSON heten `BKNSN_code` en `Subtype_na`, **met hoofdletters**.
  Een property `subtype_na` in kleine letters bestaat niet in dit bestand.
- Het label `Kl3` staat in de brondata als `:ingoruines en periglaciale laagten`; het
  eerste teken is in de bron beschadigd. Bedoeld is `Pingoruines`. De entry `pingoruine`
  matcht op beide schrijfwijzen.
- Sommige `Subtype_na`-waarden komen onder meerdere codes voor en zijn zonder die code
  dubbelzinnig: `Es` (Dz4, Sw5), `Droogdal` (Lg6, Sw4), `Restgeul` (Rg5, Rt4),
  `Kreekrug` (Dr2, Zk3), `Laagveenvlakte` (Dz9, Lv1), `Depressie` (Hv3). De teksten zijn
  zo geschreven dat ze voor beide herkomsten kloppen.

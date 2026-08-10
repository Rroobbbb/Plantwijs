# Beplantingswijzer.nl — SEO- en contentplan

*Versie 1.0 — 10 augustus 2026. Datagrondslag: docs/SEO_KEYWORDS.md (DataForSEO, 15 calls, NL/nl).
Alle content Nederlandstalig. Uitvoering: schrijf- en verificatie-agents; releases geautomatiseerd via Netlify.*

## 1. Strategie in één alinea

Google's eigen AI Overview op "inheemse bomen" eindigt met de vraag om **grondsoort, zon/schaduw en tuingrootte** — het bewijs dat heel dit contentveld blijft steken bij landelijke lijstjes, terwijl de zoeker een antwoord voor zíjn plek wil. Dat antwoord kan alleen Beplantingswijzer geven. Elke pagina die we publiceren volgt daarom hetzelfde patroon: **een inhoudelijk sterk, feitelijk geverifieerd antwoord op de generieke vraag, plus de brug die niemand anders heeft: "check wat er op jouw adres groeit" → de tool.** De concurrentie bestaat uit webshops (verkoopintentie), provinciale stichtingen (regionaal) en RVO-regelgeving (voor agrariërs); wij zijn de enige landelijke, neutrale, locatiebewuste bron.

## 2. Wat de cijfers zeggen (kern uit docs/SEO_KEYWORDS.md)

- **Sterkste cluster: "inheemse × plant/boom/struik/haag"** — ±7.500 zoekopdrachten/mnd, keyword difficulty 1–9. `inheemse planten` + `inheemse plantenlijst` = 2× 1900/mnd bij KD 1.
- **Beste SERP-gat: `struweelhaag`** (590/mnd, LOW) — top-10 vol provinciale stichtingen en subsidieregels; geen landelijke consumentenbron. Acht gerelateerde zoekopdrachten = kant-en-klare subpagina's.
- **Zwakste SERP: `planten voor kleigrond`** (210 + omliggend) — webshop-zoekpagina op #4, PDF op #5, featured snippet uit 2020. Triviaal te verslaan, en het snijvlak "inheemse planten op kleigrond" staat al in Googles gerelateerde zoekopdrachten.
- **Programmatisch goud: `[plant] grondsoort`** (lavendel 110, hortensia 50, ±12 instanties) — het enige contenttype waarvan het antwoord per gebruiker verschilt; principieel niet kopieerbaar door concurrenten.
- **Valkuilen**: `houtwal` is 95% parkeer-/campingverkeer (echt volume ±150, niet 5400); `grondsoort` solo is half kruiswoordpuzzel; **landschapstype-namen hebben géén zoekvolume** (dekzandlandschap, coulisselandschap, …: allemaal <40/mnd).
- **Seizoen**: publiceren 6–8 weken vóór plantseizoen. Het is nu augustus → **het najaarsseizoen (sep–nov) is precies het venster; direct beginnen.**

## 3. Sitestructuur en paginatypen

```
beplantingswijzer.nl/            → de tool (bestaande app; blijft de held)
beplantingswijzer.nl/gids/       → contenthub (statisch, Netlify)
  /gids/inheemse-planten/            pijler #1 (1900+1900, KD 1) — met doorzoekbare soortenlijst uit eigen data
  /gids/inheemse-struiken/           satelliet (590, +180% YoY op "…nederland")
  /gids/inheemse-bomen/              satelliet, AIO-gericht (480): expliciet gestructureerd op grondsoort × licht × grootte
  /gids/struweelhaag/                hub #2 (590, LOW) + 8 subpagina's (soorten, plantafstand, breedte, snoeien, aanleg, subsidie, kopen-alternatief, vs. geschoren heg)
  /gids/haag-kiezen/                 keuzevraag (390, KD 3) — incl. meidoorn (1600!) en veldesdoorn (480, +50%) als inheemse antwoorden op commercieel volume
  /gids/grondsoort/klei|zand|veen|loess/   per grondsoort: herkennen, verbeteren, soortenlijst (210+260+…)
  /gids/plant/<soort>-grondsoort/    programmatische reeks (lavendel, hortensia, magnolia, camelia, …)
  /gids/elzensingel|hoogstamboomgaard|knotbomen|geriefbosje/   landschapselementen-reeks (laag volume, LOW comp, past bij missie)
  /gids/vogelvriendelijke-tuin/      top-of-funnel (140, KD 5)
beplantingswijzer.nl/blog/       → actualiteit/seizoen (plantseizoen, Tegelwippen-moment +133%, subsidienieuws 70/mnd +29%)
```

**Regels:**
- Landschapstypen (stuwwal, beekdal, …) zijn *inhoud* op de grondsoort-/vormpagina's en in de tool — nooit een URL-doelwit.
- Elke gidspagina krijgt: (a) een direct, citeerbaar antwoordblok bovenaan (featured-snippet/AIO-kandidaat), (b) soortentabellen **uit onze eigen dataset** (incl. Ellenberg/vocht/licht — data die niemand anders toont), (c) de locatie-CTA ("Werkt dit op jouw grond? Voer je adres in"), (d) FAQ-blok op de People-Also-Ask-vragen, (e) interne links: satelliet → pijler → tool.
- Nooit een pagina op het kale woord "inheems" of "grondsoort" (disambiguatie-ruis).

## 4. Techniek en hosting (Netlify + bestaande backend)

De app is Python/FastAPI en kan niet óp Netlify draaien; Netlify wordt de **voordeur** van het domein:

1. **DNS**: beplantingswijzer.nl → Netlify (site "beplantingswijzer").
2. **Netlify serveert statisch**: `/gids/*`, `/blog/*`, sitemap-index, en de assets daarvan.
3. **Alles daarbuiten wordt geproxied** naar de FastAPI-backend op Render via `_redirects` (status 200 = proxy, geen redirect):
   ```
   /gids/*   → statisch (Netlify zelf)
   /blog/*   → statisch
   /*        → https://<render-service>.onrender.com/:splat   200!
   ```
   Eén domein voor tool én content ⇒ alle autoriteit landt op hetzelfde host — belangrijk, want de gidsen bouwen de autoriteit die de tool laat ranken.
4. **Sitemap-index** op Netlify: verwijst naar de statische content-sitemap én naar de bestaande app-sitemap (`/sitemap.xml` van de backend). `robots.txt` blijft van de backend komen (staat AI-crawlers al toe); Netlify-laag voegt niets blokkeerends toe.
5. Eenvoudiger alternatief (genoteerd voor eerlijkheid): de gidsen gewoon door FastAPI laten serveren en Netlify weglaten. Gekozen is Netlify omdat de eigenaar dat wil, het de release-pipeline van de backend loskoppelt, en statische pagina's gegarandeerd maximale Core-Web-Vitals halen.

## 5. Release-pipeline (geautomatiseerd, "om de paar dagen")

- **Bron**: map `site/` in deze repo — `site/content/*.md` (frontmatter: title, description, slug, cluster, status: concept|geverifieerd|live), `site/templates/`, `site/build.py` (kleine Python-SSG, geen Node nodig: markdown → HTML met huisstijl-CSS, schema.org Article + FAQPage, canonical, interne-linkblokken).
- **GitHub Actions** (`.github/workflows/site.yml`):
  - trigger: push naar master (map `site/**`) **én** cron elke 3 dagen 06:00;
  - stappen: build → `netlify deploy --prod` (secrets: `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID`).
  - De cron-run publiceert artikelen waarvan de frontmatter-`publicatiedatum` is aangebroken — zo schrijven we in batches en druppelt de site vanzelf elke paar dagen een nieuw stuk (natuurlijk publicatieritme).
- **Dataverversing**: dezelfde workflow draait maandelijks de verrijkingsscripts-check zodat soortentabellen in de gidsen synchroon blijven met de dataset.

## 6. Contentworkflow met agents (schrijven → verifiëren → publiceren)

Per artikel, alles Nederlands, B1-niveau:

1. **Schrijf-agent** (opus) krijgt: het doelkeyword-cluster + SERP-notities uit docs/SEO_KEYWORDS.md, de paginatemplate, en query-toegang tot de eigen dataset/kennislaag (soortenlijsten, Ellenberg, vocht/licht/bodem) — cijfers en soortclaims komen úit die data, niet uit het hoofd.
2. **Verificatie-agent** (opus) checkt elke feitelijke claim tegen de vaste bronnenlijst (WUR/bodemdata.nl, BRO, natuurkennis.nl/OBN, Ecopedia/INBO, FLORON/verspreidingsatlas, RCE, BIJ12/RVO voor subsidieclaims — **geen blogs of webshops**) en tegen de eigen kennislaag; oordeel per claim, correcties verplicht vóór publicatie. Soortnamen moeten in de dataset bestaan.
3. **SEO-controle** (checklist, zelfde agent of aparte pass): title ≤60 tekens met keyword, meta description, één H1, antwoordblok ≤50 woorden bovenaan, FAQ uit PAA-vragen, ≥3 interne links (satelliet↔pijler↔tool), alt-teksten, schema.org valide.
4. **Publicatie**: status → `geverifieerd`, publicatiedatum ingepland, merge naar master; de pipeline doet de rest.

Cadans: **2 artikelen per week** (≈ elke 3–4 dagen één live). Kwartaalritme: maand 1–2 = pijlers #1–#5 uit de prioriteitenlijst; maand 3 = programmatische `[plant] grondsoort`-reeks + landschapselementen; daarna bijsturen op Search Console-data.

## 7. Prioriteitenlijst eerste 12 publicaties

| # | Pagina | Doelkeyword(s) | Volume | Waarom eerst |
|---|--------|----------------|--------|--------------|
| 1 | Pijler: Inheemse planten (met soortzoeker) | inheemse planten(lijst) | 2×1900, KD 1 | grootste kans van het onderzoek |
| 2 | Hub: Struweelhaag | struweelhaag + 8 subvragen | 590, LOW | beste SERP-gat; landelijk niemand |
| 3 | Inheemse struiken | inheemse struiken (nederland) | 590+140 | +180% YoY-momentum |
| 4 | Inheemse bomen: welke past bij jouw grond? | inheemse bomen (nederland) | 480+170 | AIO vraagt om onze assen |
| 5 | Planten voor kleigrond | planten voor kleigrond; inheemse planten op kleigrond | 210+ | zwakste SERP; snippet uit 2020 |
| 6 | Kleigrond verbeteren | kleigrond verbeteren | 260 | koppelt aan #5 |
| 7 | Welke haag kies je? | haag soorten; inheemse haag | 390+110, KD 3 | brug naar meidoorn (1600) |
| 8 | Bomen voor een kleine tuin | (kleine) bomen voor kleine tuin | 1600+260, KD 2 | volume + inheems-subvraag |
| 9 | Planten voor zandgrond | planten voor zandgrond; bomen zandgrond | 70+20 | completeert grondsoortreeks |
| 10 | Grondsoortenkaart: welke grond heb ik? | grondsoortenkaart; grondsoort nederland (kaart) | 90+210+140, KD 4–17 | hoogste tool-conversie |
| 11 | Lavendel en jouw grondsoort (start reeks) | lavendel grondsoort | 110 | bewijs programmatisch model |
| 12 | Elzensingel | elzensingel | 260, LOW | missie + LOW comp |

## 8. Autoriteit en vindbaarheid buiten content

- **Search Console + Bing Webmaster** direct na DNS-koppeling (actie eigenaar); sitemap-index aanmelden.
- **Linkwaardige assets**: de tool zelf (uniek), de gratis PDF-rapporten, en de gidsen — actief aanbieden aan: provinciale landschapsstichtingen (die linken graag naar een landelijke aanvulling op hun regiowerk), gemeentelijke groenpagina's, IVN/KNNV-afdelingen, Steenbreek/NK Tegelwippen (moment: +133%), moestuin-/tuinverenigingen.
- **AI-vindbaarheid** meeliften: /llms.txt bestaat al; elke gidspagina krijgt dezelfde heldere, citeerbare structuur die ook AI Overviews citeren.
- Subsidie-invalshoek (70/mnd, +29%, CPC €2,93 — adverteerders zien er waarde in): één actuele pagina over aanplantsubsidies per provincie, jaarlijks agent-onderhouden.

## 9. Meten en bijsturen

- KPI's per maand: vertoningen/klikken per cluster (GSC), posities top-12, tool-sessies vanaf gidspagina's (interne verwijzing loggen), PDF-downloads, AIO-/snippet-citaties (handmatige steekproef).
- Kwartaalreview: winnaars uitbouwen (meer satellieten), verliezers herschrijven of samenvoegen; keywordonderzoek jaarlijks herhalen (methode-notities in docs/SEO_KEYWORDS.md §9 — gebruik `keyword_suggestions`, niet `keyword_ideas`).

## 10. Wat we bewust NIET doen

- Geen pagina's op landschapstype-namen (geen zoekvolume), niet op kaal "houtwal"/"grondsoort"/"inheems" (verkeerde intentie), geen `klimaatadaptief`-jargon (-78% YoY).
- Geen AI-tekst zonder verificatieronde; geen soortadviezen die niet uit de eigen dataset komen; geen linkkoop of gastblogruil met webshops.

## 11. Benodigd van de eigenaar (eenmalig)

1. Netlify-account + site aanmaken, `NETLIFY_AUTH_TOKEN` en `NETLIFY_SITE_ID` als GitHub-secrets zetten.
2. DNS van beplantingswijzer.nl naar Netlify wijzen (en het Render-backend-adres doorgeven zodra de service bestaat).
3. Search Console-/Bing-verificatie (eigenaarschap domein).
4. Akkoord op dit plan; daarna bouwt een agent de `site/`-fundering (templates, build.py, workflow) en start de schrijfcadans.

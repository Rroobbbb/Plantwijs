# Beplantingswijzer — Frontend-ontwerpbrief (WP3)

*Productnaam: Beplantingswijzer (voorheen PlantWijs); de technische pakketnaam `plantwijs` en de repo-naam blijven ongewijzigd.*

Doelgroep: bewoners zonder voorkennis, NL-talig. Toon: uitnodigend, betrouwbaar, natuurlijk. Dit document is bindend voor WP3; API-contract in docs/API.md.

## Kernflow
1. **Startstaat** — kaart van Nederland + korte uitleg-overlay: "Klik op de kaart of zoek je adres om te zien welk landschap bij jouw plek hoort — en welke beplanting daar thuishoort." Zoekbalk (PDOK Locatieserver, bestaande endpoints) prominent.
2. **Na klik/zoekactie** — adviespaneel vult zich met, in deze volgorde:
   a. **Jouw plek** — chips met de gevonden kaartwaarden (FGR, bodem, Gt→vocht, hoogte, geomorfologie, NSN). Elke chip heeft een ℹ️-uitklap met bronvermelding. Bronnen die niets opleverden: grijze chip "niet gevonden" (uit `bronnen_status`).
   b. **Jouw landschap** — het verhaal (`landschap.*`): ontstaan (proza) + "Zo versterk je dit landschap" (bulletlijst). Prioriteit van tonen: nsn > fgr; gmm/bodem/vocht als compacte sub-blokken/accordeons.
   c. **Wortelruimte** — `wortelbare_diepte`: visuele band (0–200 cm schaal met gemarkeerde bandbreedte) + indicatietekst.
   d. **Wat kun jij doen** — kaartjes per aanbevolen beplantingsvorm (`aanbevolen_beplanting`): vorm, waarom hier, voorbeeldsoorten.
   e. **Passende soorten** — de tabel (zie onder) met filters.
   f. **Meenemen** — knoppenrij: CSV, Excel, PDF-rapport (`/advies/pdf`; disabled met tooltip zolang 501).
3. Nieuwe klik = paneel ververst; vorige selectie-marker verdwijnt.

## Lay-out
- **Desktop (≥900px)**: kaart links (~55%, sticky/vaste hoogte), adviespaneel rechts scrollbaar. Versleepbare splitter mag vervallen (simpeler > gimmick).
- **Mobiel**: kaart bovenaan (~55vh), adviespaneel als bottom-sheet die na een klik omhoog schuift (drag-handle, snap: peek/half/vol). Geen dubbele legenda-elementen meer (het oude ontwerp had er twee).
- Header: logo/naam "Beplantingswijzer" + ondertitel "Advies op maat voor jouw plek" + themaknop.

## Huisstijl
- CSS custom properties, licht + donker thema (localStorage, default: systeemvoorkeur).
- Palet licht: achtergrond warm off-white (#f7f6f2), panelen wit, tekst bijna-zwart (#1f2937), primair diep bosgroen (#1d5c3f), accent amber (#c77b3a) alléén voor CTA's, chipranden zacht. Donker: achtergrond #0e1512, panelen #16211b, primair #4caf82, zelfde accent.
- Typografie: system-ui-stack; headings gewicht 650, lichte negatieve letter-spacing. Basisgrootte 15–16px, regelafstand 1.55.
- Afgeronde hoeken 10–14px, subtiele schaduwen, geen glassmorphism/gradient-geweld.
- Iconen: inline SVG (Lucide-stijl, zelf embedden, géén icon-CDN). Leaflet mag via unpkg-CDN blijven (zoals nu).

## Soortentabel
- Paginering (50 per pagina) i.p.v. alles renderen; teller "X soorten gevonden".
- Kolommen: Naam (+🍃-badge voor inheems, als groen blad-SVG), Wetenschappelijke naam (cursief), Type, Licht, Vocht, Bodem, Hoogte, Status. Kolomkiezer behouden (localStorage).
- Kolomkop-filters behouden maar visueel netter (popover met checkboxen, "Toepassen/Wissen").
- Hoofd-filters boven de tabel als segmented chips: Licht (belangrijk! kaart weet dit niet — duidelijke hint), Status (inheems/ingeburgerd/exoot), Type (boom/heester), toggle "invasieve soorten uitsluiten"; "meer filters" voor vocht/bodem-override met uitleg dat dit de kaartwaarde overschrijft.
- Filterstatus-melding behouden (welke filters actief/ontbreken), als rustige infobalk.

## Kaart
- OSM-basiskaart; WMS-overlays uit `/api/wms_meta` in een nette lagen-picker met opacity-sliders (bestaand gedrag), standaard FGR aan op lage dekking.
- Zoekbalk linksboven; locatieknop (geolocatie); zoom rechtsonder op mobiel; schaalbalk.
- Klik-marker met subtiele druppel-animatie.

## Gedrag & kwaliteit
- `/advies/geo` kan 1–10 s duren (eerste NSN-indexbouw nog langer): skeleton-loaders per sectie + statustekstjes ("Kaartbronnen raadplegen…"). Requests aborten bij nieuwe klik (AbortController).
- Foutstaat per bron, nooit een leeg wit paneel; netwerkfout ⇒ vriendelijke melding + retry-knop.
- Toegankelijkheid: aria-labels, focus-visible ringen, toetsenbord-bereikbare filters, prefers-reduced-motion respecteren, contrast AA.
- SEO/meta: `<html lang="nl">`, title "Beplantingswijzer — beplantingsadvies op maat voor jouw plek", meta description, canonical naar https://beplantingswijzer.nl/, og-tags, favicon als inline-SVG-blaadje (data-URI), robots index.
- Techniek: vanilla ES-modules (`static/js/`), één `static/css/app.css`, geen framework, geen build-step, geen externe fonts/CDN's behalve Leaflet en OSM-tiles.
- Staat in URL: na klik `?lat=..&lon=..` (history.replaceState) zodat een locatie deelbaar is; bij laden met lat/lon direct advies ophalen.

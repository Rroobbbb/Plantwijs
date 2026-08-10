# Verificatie maatregelen & wortelregels — verantwoording

*10 augustus 2026. Werkwijze: drie diepgaande bronnenonderzoeken (graft; beheercycli van alle
elementtypen; grienden) uitgevoerd door onderzoeks-agents binnen de afgesproken brondiscipline
(WUR/Alterra, BRO/BIJ12, RCE, OBN/natuurkennis.nl, Ecopedia/INBO, provinciale regelgeving via
officiële bekendmakingen, ANLb-beheerpakketten; geen blogs of commerciële sites). De
verwerkingsagent viel uit; de integratie van de onderzoeksresultaten in `content/maatregelen.yaml`
is daarna door de hoofdsessie gedaan. Volledige bronvermeldingen staan onderaan.*

## Doorgevoerde correcties in content/maatregelen.yaml

| Vorm | Was | Is geworden | Grond |
|------|-----|-------------|-------|
| Hoogstamboomgaard | "honderd tot honderdvijftig bomen per hectare, dus acht tot tien meter tussen de bomen" | 50–150 bomen/ha; plantafstand ±6 m (peer/pruim), 10 m (appel), 12 m (kers) | Index N&L L01.09: dichtheid min. 50–max. 150/ha; SLG-informatieblad hoogstamboomgaard voor de afstanden per soort |
| Griend | "elke één tot drie jaar volledig afgezet" | snijgriend jaarlijks; hakgriend 2–5 jaar | BIJ12 Index N17.05 ("om de 2 tot 5 jaar"; intensief 1–2 jr), RCE (hakgriend 2–4 jr), WUR/Schepers 1989 |
| Graft (omschrijving) | "een van de effectiefste manieren om modderstromen te beperken" | kwalitatieve formulering: remt afspoelen van water en grond | Erosieremmende functie is kwalitatief goed onderbouwd (WUR/Breteler & Van den Broek 1968), maar er bestaan **geen kwantitatieve cijfers** voor graften; superlatief verwijderd |
| Graft (onderhoud) | cyclus 8–15 jaar | cyclus 6–15 jaar | Provincie Limburg, Nadere subsidieregels Landschapselementen 2025: "op het vaakst eens per 6 jaar, doch minimaal eens per 15 jaar" |
| Knotbomen | "knotten om de drie tot zes jaar" (alle soorten) | 3–6 jaar voor wilg/populier; es/els langer; knoteik veel langer | ANLb pakket 21 (4–6 jr), Landschapsbeheer Drenthe (3–5 jr wilg/populier/linde), Index-beheereis (3–8 jr; eik min. 15 jr), Ecopedia (eik 8–10 jr) |
| Struweelhaag (maat) | "één tot drie meter breed en twee tot vier meter hoog" | volgroeid al gauw 2–3 m breed en minstens even hoog | Geen officiële maat-eis; Landschap Overijssel: ca. 3 m breed, min. 3 m hoog (officiële minima gelden pas ná snoei: 1,0 m hoog / 0,8 m breed) |
| Struweelhaag (onderhoud) | terugzetten om de 5–10 jaar | om de 6–15 jaar | SLG (niet vaker dan 1×/6 jr; afzetten 6–15 jr); Index-pakket b: afzetten 12–25 jr |
| Elzensingel | hakhoutcyclus 6–15 jaar | 6–20 jaar | SVNL/Index L01.03: 6–21 jr; RCE: tot 25 jr; WUR-rekenmodellen: 10 of 20 jr |
| Houtsingel | "minstens drie tot zes meter breed" | "doorgaans drie tot zes meter breed" | Geen officiële minimumbreedte (L01.02 kent alleen max. 20 m); 3–6 m komt uit aanlegrichtlijnen (SLG, Landschap Overijssel) |

## Gecontroleerd en in orde bevonden

- **Houtwal**: omschrijving (opgeworpen wal, veekering, gebruikshout) klopt met RCE/SLG; cyclus 8–15 jr valt binnen de bandbreedte van alle bronnen (SVNL 6–15, SLG 10–12, LO 15–20, WUR 12, ANLb ~6 tussenkap/~25 eindkap) — ongewijzigd gelaten.
- **Knip- of scheerheg**: 1–2× per jaar knippen klopt met SLG/RCE-praktijkadvies (ANLb-minimum is 1× per 3 jaar); nestcontrole-advies staat er al in.
- **Graft-omschrijving (ontstaan)**: onze colluvium-lezing volgt de best onderbouwde WUR-lijn (Breteler & Van den Broek 1968; Renes). NB: RCE laat twee ontstaanstheorieën naast elkaar bestaan; OBN formuleert "aangelegd". Voor de graften dwars op droogdalen is aanleg wél aangetoond.
- **Gt→vochtklasse-mapping** (`plantwijs/services/pdok.py`): de indeling (Gt I–II zeer nat, III nat, IV–V vochtig, VI droog, VII–VIII zeer droog) is beoordeeld tegen de officiële Gt-definities (GHG/GLG-klassegrenzen, BRO-catalogus). Het is een bewuste vereenvoudiging die de hoofdlijn volgt; kanttekening: Gt V (natte winters, diepe zomerstand) is als "vochtig" een middeling. Niet gewijzigd; gedocumenteerd.
- **wortelbare_diepte.yaml**: de bandbreedtes (0–30 t/m 150–200 cm) en de opbouw bodem×Gt met NSN-modifiers zijn niet in strijd bevonden met de geraadpleegde bronnen, maar er bestaat geen landelijke normtabel om ze 1-op-1 aan te toetsen. De disclaimer "indicatief" in het bestand dekt dit; ongewijzigd.

## Belangrijke bevindingen voor de redactie (geen tekstwijziging nodig)

1. **De huidige Index Natuur en Landschap (BIJ12, 2024/2025) schrijft géén beheercycli meer voor** — die staan sinds de ANLb-overgang in de beheerpakketten (BoerenNatuur-overzicht 2025). Wie "de Index eist X jaar" zegt, citeert de vervallen 2015-versie; de getallen leven wel voort in provinciale SVNL-verordeningen.
2. **"Hoepelgriend" en "vloedgriend" zijn geen erkende vaktermen** — hoephout is een product van de hakgriend; doorgeschoten griend wordt zachthoutooibos (N14.01/H91E0_A). Onze teksten gebruikten die termen niet; genoteerd voor toekomstige content.
3. Bekende cijferclaims die we bewust **niet** gebruiken: "40–60% minder afstroming" (gaat over niet-kerende grondbewerking, niet over graften) en "2.300 graften / 210 km" (voetnoot leidt naar een privé-glossarium).
4. In de bronnen zelf zitten tegenstrijdigheden (o.a. knoteik "7–8 jaar" in de Index-beschrijving vs. "min. 15 jaar" in de Index-beheereis van hetzelfde document; griend "4–6 jaar" beschrijving vs. "min. 1×/5 jaar" pakketeis). Onze teksten kiezen steeds de breedst gedragen bandbreedte.

## Kernbronnen

Breteler & Van den Broek (1968), *Graften in Zuid-Limburg* (Stiboka) — edepot.wur.nl/110254 · Leenders (1993), Staring Centrum rapport 270 — edepot.wur.nl/303288 · Melman/De Waal/Renes, *Ecologie en cultuurhistorie Heuvelland* — edepot.wur.nl/181296 · Schepers (1989), *Een landelijk overzicht van de grienden* — edepot.wur.nl/266813 · WUR WOt-werkdocument 138 (2009), beheersintervallen — edepot.wur.nl/5102 · Index Natuur en Landschap versie 2015 (Zuid-Holland-uitgave) en versie okt-2024/mei-2025 (BIJ12) · Overzicht ANLb-Beheerpakketten 2025 (BoerenNatuur, 28-10-2024) · Nadere subsidieregels Landschapselementen 2025, Provincie Limburg (CVDR734978) · SVNL Gelderland 2016 (CVDR373398) · RCE kennisbank (houtsingel/houtwal, elzensingels, knotboom, heg en haag, griend, holle wegen) · BIJ12-landschapselementtypen L01.02/L01.08/L01.09 · natuurkennis.nl N17.05 en heuvellandschap · Ecopedia (knotbomen, graft, vloedbos) · SLG-informatiebladen (houtsingel, struweelhaag, hoogstamboomgaard, knip- en scheerheg, knotboom) · Landschap Overijssel (houtwal, houtsingel, struweelhaag) · Landschapsbeheer Drenthe (knotbomen).

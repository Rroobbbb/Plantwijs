---
# ─────────────────────────────────────────────────────────────────────────────
# VOORBEELDARTIKEL — sjabloon, geen echte content.
#
# Dit bestand demonstreert het frontmatter-schema en de artikelstructuur uit
# docs/SEO_PLAN.md §6. De status is `concept`, dus build.py slaat het over en er
# verschijnt niets op de site. Kopieer het naar een nieuwe naam en vervang alles
# tussen [vierkante haken].
#
# Statusflow: concept → geverifieerd → live (zie site/README.md).
# ─────────────────────────────────────────────────────────────────────────────

# H1 van de pagina. Begin in de tekst zelf dus bij "## ".
title: "[Doelkeyword als vraag of belofte, 50-60 tekens]"

# Optioneel: alleen nodig als de <title> in de zoekresultaten moet afwijken van
# de H1. Richtlijn: maximaal 60 tekens, met het doelkeyword vooraan.
seo_title: "[Doelkeyword + korte belofte, ≤60 tekens]"

# Meta description: 120-160 tekens, actief geschreven, met het doelkeyword.
description: >-
  [Wat leert de lezer hier, en waarom is dit antwoord beter dan het landelijke
  lijstje van de concurrentie? Maximaal 160 tekens.]

# Laatste deel van de URL. Deze wordt /blog/<slug>/ omdat het bestand in
# content/blog/ staat. Alleen kleine letters, cijfers en koppeltekens.
slug: voorbeeld-artikel

# Het keywordcluster uit docs/SEO_KEYWORDS.md waar dit stuk bij hoort.
# Verschijnt als bovenschrift boven de titel en op de gidskaartjes.
cluster: "[Clusternaam, bijvoorbeeld Struweelhaag]"

# concept = in bewerking · geverifieerd = feitencheck gedaan · live = mag online.
status: concept

# Alleen pagina's met status `live` én een publicatiedatum van vandaag of eerder
# worden gebouwd. Zet hier de geplande datum: de cron-run van de workflow
# publiceert het stuk vanzelf zodra die dag is aangebroken.
publicatiedatum: 2026-09-01

# Optioneel: datum van de laatste inhoudelijke herziening (dateModified).
# bijgewerkt: 2026-11-15

# Het citeerbare antwoordblok bovenaan: maximaal 50 woorden, direct antwoord op
# de zoekvraag. Dit is de kandidaat voor de featured snippet en de AI Overview.
antwoord: >-
  [Geef in maximaal 50 woorden het volledige antwoord op de zoekvraag. Noem de
  drie tot vijf belangrijkste opties of stappen, zonder slag om de arm. De
  nuance komt in de rest van het artikel; hier staat het antwoord dat een
  zoekmachine of AI-assistent letterlijk kan citeren.]

# FAQ uit de People-Also-Ask-vragen bij dit keyword. Wordt onderaan getoond en
# als schema.org FAQPage meegestuurd. Twee tot zes vragen werkt het beste.
faq:
  - vraag: "[PAA-vraag 1, letterlijk zoals Google hem toont]"
    antwoord: >-
      [Antwoord van twee tot vier zinnen. Zelfstandig leesbaar, want dit stukje
      kan los in een zoekresultaat verschijnen.]
  - vraag: "[PAA-vraag 2]"
    antwoord: >-
      [Antwoord van twee tot vier zinnen. In een antwoord mag je gewoon
      [linken](/gids/zo-werkt-het-advies/) naar een andere pagina.]

# Bronnenlijst. Alleen de vaste bronnen uit docs/SEO_PLAN.md §6: WUR en
# bodemdata.nl, BRO, natuurkennis.nl en OBN, Ecopedia en INBO, FLORON en de
# verspreidingsatlas, RCE, en BIJ12 of RVO voor subsidieclaims. Nooit blogs of
# webshops. Mag een lijst tekst zijn, of blokken met `titel` en `url`.
bronnen:
  - titel: "[Bronnaam, bijvoorbeeld: Bodemkaart van Nederland (BRO)]"
    url: "[https://volledige-url-naar-de-bron]"
  - "[Bron zonder link mag ook: alleen de naam als tekst]"
  - "[Vervang deze lijst vóór publicatie; de verificatie-agent controleert elke feitelijke claim hiertegen.]"
---

## [H2 met de kern van het antwoord, herhaalt het doelkeyword niet letterlijk]

[Twee tot vier alinea's die het antwoordblok uitwerken. Schrijf op B1-niveau:
korte zinnen, gewone woorden, actieve vorm. Vaktermen mogen, maar leg ze in
dezelfde zin uit. Geen emoji, geen uitroeptekens, geen superlatieven.]

[Verwijs vroeg in het stuk naar de tool, want dat is de brug die de concurrentie
niet heeft: bekijk op [de kaart](/) wat er op jouw eigen grond past.]

## [H2 met de soortentabel uit de eigen dataset]

[Soortclaims komen uit de eigen dataset, niet uit het hoofd. Neem per soort de
kolommen op die niemand anders toont: vocht, licht, bodem en de status inheems,
ingeburgerd of exoot. Elke soortnaam moet in `data/treeebb_planten_allfields.csv`
voorkomen; de wetenschappelijke naam is de sleutel.]

| Soort | Wetenschappelijke naam | Vocht | Licht | Bodem | Status |
|---|---|---|---|---|---|
| [Nederlandse naam] | [Genus soort] | [vochtklasse] | [licht] | [bodem] | [inheems] |
| [Nederlandse naam] | [Genus soort] | [vochtklasse] | [licht] | [bodem] | [inheems] |

## [H2 met de praktische stap: aanleg, onderhoud of keuzehulp]

[Wat moet de lezer nu doen? Geef concrete stappen, afstanden of maten. Blijf
feitelijk conservatief: alles wat je hier beweert, wordt in de verificatieronde
tegen de bronnenlijst hierboven gelegd.]

- [Stap of aandachtspunt 1]
- [Stap of aandachtspunt 2]
- [Stap of aandachtspunt 3]

## [H2 die naar de verwante pagina's leidt]

[Minimaal drie interne links per artikel, in de richting satelliet → pijler →
tool. Bijvoorbeeld: lees ook [Zo werkt het advies](/gids/zo-werkt-het-advies/)
voor de kaartlagen achter dit advies, of bekijk
[alle gidsen](/gids/) voor de rest van dit cluster.]

[Sluit af met één zin die de lezer naar de kaart stuurt. De vaste CTA-sectie
"Bekijk wat er op jouw adres past" staat automatisch onder elk artikel; die hoef
je hier niet te herhalen.]

# site/ — de contentlaag van beplantingswijzer.nl

Hier staan de gidsen en blogartikelen van Beplantingswijzer: Markdown in, statische HTML uit.
De app zelf (FastAPI, `plantwijs/`) staat hier volledig los van; deze map raakt geen applicatiecode
aan. Het plan achter deze laag staat in [`../docs/SEO_PLAN.md`](../docs/SEO_PLAN.md).

## Wat er in deze map staat

| Pad | Inhoud |
|---|---|
| `content/gids/*.md` | De gidsen. Eén bestand = één pagina op `/gids/<slug>/`. |
| `content/blog/*.md` | Blogartikelen, op `/blog/<slug>/`. `_voorbeeld-artikel.md` is het sjabloon. |
| `build.py` | De generator: leest de Markdown, past de templates toe, schrijft `_site/`. |
| `templates/` | `base.html` (casco), `page.html` (artikel), `gids-index.html` (overzicht), `sitemap-content.xml`. |
| `static/site.css` | De huisstijl, afgeleid van `static/css/app.css` van de app. |
| `requirements.txt` | Alleen `markdown` en `pyyaml`. Geen Node, geen framework, geen CDN. |
| `_redirects` | Netlify-regels: `/gids/*` en `/blog/*` statisch, de rest geproxied naar de backend. |
| `_site/` | Het bouwresultaat. Staat in `.gitignore`; nooit met de hand bewerken. |

## Lokaal bouwen

Vanuit de projectroot, met de venv van het project:

```powershell
.venv\Scripts\python.exe -m pip install -r site\requirements.txt
.venv\Scripts\python.exe site\build.py
```

De build meldt per bestand wat er is gebeurd, plus eventuele SEO-waarschuwingen. Bekijk het
resultaat met een lokale server (de CSS staat op een absoluut pad, dus `file://` werkt niet):

```powershell
cd site\_site
..\..\.venv\Scripts\python.exe -m http.server 8765
# open http://127.0.0.1:8765/gids/
```

Handige schakelaars:

| Schakelaar | Doel |
|---|---|
| `--today 2026-09-01` | Doe alsof het die dag is. Zo bekijk je een geplande publicatie vooraf. |
| `--out <map>` | Bouw naar een andere map dan `site/_site`. |

## Een artikel toevoegen

1. Kopieer `content/blog/_voorbeeld-artikel.md` naar `content/gids/<slug>.md` of
   `content/blog/<slug>.md`. Dat sjabloon bevat het volledige frontmatter-schema met uitleg per
   veld en de artikelstructuur uit SEO_PLAN §6.
2. Vul de frontmatter (zie de tabel hieronder) en schrijf de tekst. **De H1 komt uit `title`**;
   begin in de tekst zelf dus bij `## `.
3. Zet `status` op `concept` zolang je schrijft. De build slaat het bestand over, maar controleert
   de frontmatter wél — een typefout valt dus meteen op.
4. Laat de verificatieronde lopen (zie hieronder), zet daarna `status: live` met een
   `publicatiedatum`, en merge naar `master`.

### Frontmatter

| Veld | Verplicht | Betekenis |
|---|---|---|
| `title` | ja | De H1 en de standaard `<title>`. Richtlijn: ≤60 tekens, doelkeyword vooraan. |
| `seo_title` | nee | Alleen als de `<title>` moet afwijken van de H1. |
| `description` | ja | Meta description, 120–160 tekens. Wordt ook als lead onder de titel getoond. |
| `slug` | ja | Laatste deel van de URL. Kleine letters, cijfers, koppeltekens. |
| `cluster` | ja | Het keywordcluster uit `docs/SEO_KEYWORDS.md`. Zichtbaar als bovenschrift. |
| `status` | ja | `concept`, `geverifieerd` of `live`. Alleen `live` wordt gebouwd. |
| `publicatiedatum` | ja | ISO-datum (`2026-09-01`). Bepaalt wanneer de pagina verschijnt. |
| `bijgewerkt` | nee | ISO-datum van de laatste herziening; wordt `dateModified` in schema.org. |
| `antwoord` | nee | Het citeerbare antwoordblok bovenaan, ≤50 woorden. |
| `faq` | nee | Lijst met `vraag` en `antwoord`. Wordt FAQ-blok én schema.org FAQPage. |
| `bronnen` | nee | Lijst tekst, of blokken met `titel` en optioneel `url`. Komt onderaan het artikel. |

De URL volgt de map plus de slug: `content/gids/struweelhaag.md` met `slug: struweelhaag` wordt
`/gids/struweelhaag/`. Submappen mogen: `content/gids/grondsoort/klei.md` wordt
`/gids/grondsoort/klei/`.

### Statusflow en publicatiedatum

```
concept  →  geverifieerd  →  live
schrijven   feiten gecheckt   mag online, verschijnt op de publicatiedatum
```

- **`concept`** — in bewerking. Wordt niet gebouwd; de build meldt dat het bestand is overgeslagen.
- **`geverifieerd`** — de verificatieronde is gedaan, maar het stuk staat nog in de wacht. Wordt
  ook niet gebouwd. Gebruik dit om een batch klaar te zetten voor de eindredactie.
- **`live`** — mag online. De pagina wordt gebouwd zodra `publicatiedatum` vandaag of eerder is.
  Ligt de datum in de toekomst, dan meldt de build dat de datum nog niet is aangebroken.

**Zo plan je de cadans.** Schrijf in batches en zet de data een paar dagen uit elkaar
(SEO_PLAN §6 rekent op twee artikelen per week). De workflow draait elke drie dagen om 06:00 UTC
en bouwt dan opnieuw; artikelen waarvan de datum inmiddels is bereikt gaan vanzelf live. Er is dus
geen tweede merge nodig — datum zetten en mergen is genoeg. Controleer een geplande publicatie
vooraf met `--today`.

## De agent-workflow (SEO_PLAN §6)

Per artikel, alles Nederlands op B1-niveau:

1. **Schrijf-agent** — krijgt het doelkeyword-cluster en de SERP-notities uit
   `docs/SEO_KEYWORDS.md`, dit sjabloon, en toegang tot de eigen dataset en kennislaag. Cijfers en
   soortclaims komen uit die data, niet uit het hoofd. Elke soortnaam moet in
   `data/treeebb_planten_allfields.csv` bestaan.
2. **Verificatie-agent** — checkt elke feitelijke claim tegen de vaste bronnenlijst: WUR en
   bodemdata.nl, BRO, natuurkennis.nl en OBN, Ecopedia en INBO, FLORON en de verspreidingsatlas,
   RCE, en BIJ12 of RVO voor subsidieclaims. Geen blogs, geen webshops. Correcties zijn verplicht
   vóór publicatie; de gebruikte bronnen komen in het veld `bronnen`.
3. **SEO-controle** — titel ≤60 tekens met keyword, meta description, één H1, antwoordblok ≤50
   woorden bovenaan, FAQ uit de People-Also-Ask-vragen, minstens drie interne links
   (satelliet ↔ pijler ↔ tool), schema.org valide. `build.py` waarschuwt bij de meeste hiervan,
   maar blokkeert niet: de eindbeoordeling blijft mensenwerk.
4. **Publicatie** — status naar `live`, publicatiedatum inplannen, merge naar `master`.

## Publiceren en hosting

- **Pipeline**: `.github/workflows/site.yml` bouwt bij elke push naar `master` die `site/` raakt,
  en elke drie dagen via cron. Daarna volgt een productie-deploy naar Netlify. Ontbreken de
  secrets `NETLIFY_AUTH_TOKEN` of `NETLIFY_SITE_ID`, dan slaat de workflow de deploystap over met
  een melding — de build zelf draait dan gewoon, zodat fouten alsnog opvallen.
- **Hosting**: Netlify is de voordeur van het domein. `_redirects` houdt `/gids/*`, `/blog/*`,
  `/site-static/*` en `/sitemap-content.xml` op Netlify en proxyt al het andere met status 200
  naar de FastAPI-backend op Render. **De backend-URL in `_redirects` is nog een placeholder**
  (`https://RENDER-BACKEND-URL.onrender.com`) en moet na de Render-deploy worden ingevuld.
- **Assets**: de CSS staat op `/site-static/site.css`, bewust niet op `/static/` — dat pad is van
  de app en gaat via de proxy naar de backend. Alle paden in de HTML zijn absoluut, zodat een
  pagina op elke URL-diepte werkt.
- **Sitemap**: `build.py` schrijft `/sitemap-content.xml` met alleen de contentlaag. De app-sitemap
  blijft op `/sitemap.xml` bij de backend; meld in Search Console beide aan.

## Huisstijl

`static/site.css` gebruikt dezelfde kleur-tokens, typografie en vormtaal als `static/css/app.css`
van de app. Verschil: de site heeft geen JavaScript, dus licht en donker volgen
`prefers-color-scheme` in plaats van een themaknop. Lopende tekst is ±68 tekens breed, tabellen
scrollen binnen hun eigen kader op smalle schermen, en er zijn geen externe fonts, iconen of CDN's.

Elke pagina krijgt automatisch de header met het merkje en een link naar de tool, de vaste
CTA-sectie "Bekijk wat er op jouw adres past" die naar `/` linkt, en de footer met de
bronvermelding van de kaartlagen en de soortenlijst. Die hoef je in een artikel niet te herhalen.

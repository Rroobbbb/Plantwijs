# Beplantingswijzer — Livegang-checklist

*Voor Rob. Stap voor stap, in volgorde. Fase 1–3 zetten de app live op beplantingswijzer.nl;
fase 4 (de contentmachine met Netlify) kan later, wanneer je wilt. Tijden zijn schattingen.
Overal waar "zeg het Claude" staat, neem ik het vanaf daar weer over.*

## Wat al klaar staat (niets voor jou te doen)
- Code, data en kennislaag: compleet, geverifieerd, 266 tests groen, alles op GitHub (branch `master`).
- `render.yaml` (Render-blauwdruk), `runtime.txt`, deployhandleiding (docs/DEPLOY.md).
- SEO-plan + keywordonderzoek, contentpipeline-fundering (map `site/`), AI-toegang (llms.txt, robots, sitemap).

---

## Fase 1 — De app live op Render (±30 min)

1. **Account**: ga naar https://render.com → "Get Started" → kies **inloggen met GitHub** (dan ziet Render je repo meteen).
2. **Blueprint**: Dashboard → knop **New +** → **Blueprint** → kies de repo **Rroobbbb/plantwijs** → Render leest `render.yaml` en toont de service **beplantingswijzer** → klik **Apply**.
3. **Admin-sleutel**: Render vraagt om de omgevingsvariabele `PLANTWIJS_ADMIN_KEY` (staat op "sync: false"). Verzin een lang wachtwoord (bijv. 3 losse woorden + cijfers), vul het in en **bewaar het** (nodig om de dataset op afstand te verversen via `/api/admin/reload?key=...`).
4. **Wachten**: de eerste build duurt 5–10 minuten. Daarna krijg je een adres als `https://beplantingswijzer.onrender.com`.
5. **Testen**: open dat adres. Controleer: de kaart laadt → klik ergens → advies verschijnt. Let op: **de allereerste advies-klik kan 1–2 minuten duren** (de NSN-kaartindex wordt dan eenmalig opgebouwd). Daarna is het snel. Check ook `/api/health` (moet `"ok":true`, `"rows":1642`, `"versie":"4.0.0"` tonen).
6. **Niet laten inslapen (aanrader)**: op het gratis plan valt de server na 15 min stilte in slaap én is de NSN-index bij elke wekdienst weg (eerste bezoeker wacht dan lang). Voor een echte lancering: service → **Settings → Instance Type → Starter** (± $7/maand). Je kunt gerust eerst gratis testen en dit later omzetten.

## Fase 2 — beplantingswijzer.nl koppelen (±15 min + wachttijd)

7. **In Render**: service → **Settings → Custom Domains → Add Custom Domain** → vul `beplantingswijzer.nl` in, en daarna nog een keer `www.beplantingswijzer.nl`. Render toont per naam welke DNS-records je moet zetten.
8. **Bij je domeinregistrar** (waar je beplantingswijzer.nl hebt gekocht) → DNS-beheer:
   - voor `beplantingswijzer.nl`: het **A-record** (of ALIAS/ANAME) dat Render toont;
   - voor `www`: een **CNAME** naar `beplantingswijzer.onrender.com`.
9. **Wachten** (meestal 15 min – 2 uur): Render regelt daarna automatisch het HTTPS-certificaat. Klaar als er in Render een groen vinkje bij het domein staat.
10. **Eindcheck**: https://beplantingswijzer.nl werkt (kaart, advies, PDF-knop, donker thema); https://beplantingswijzer.nl/llms.txt toont de AI-uitleg; op je telefoon: open de site → "Zet op beginscherm" → het blaadjes-icoon verschijnt als app.

## Fase 3 — Vindbaar worden (±20 min)

11. **Google Search Console**: https://search.google.com/search-console → **Property toevoegen → Domein** → `beplantingswijzer.nl` → Google geeft een **TXT-record** → zet dat bij je registrar in de DNS → terug in Search Console op **Verifiëren** klikken (soms even wachten).
12. **Sitemap aanmelden**: in Search Console → Sitemaps → `https://beplantingswijzer.nl/sitemap.xml` toevoegen.
13. **Bing**: https://www.bing.com/webmasters → "Importeren uit Google Search Console" (twee klikken, neemt alles over).
14. **Eerste links** (belangrijkste ranking-zetje, zie SEO_PLAN §8): mail/bel de partijen die jou kennen — gemeente-groenpagina, IVN/KNNV-afdeling, provinciale landschapsstichting, Steenbreek — met het verzoek om een link. De tool is voor hen een gratis aanvulling op hun eigen voorlichting.

## Fase 4 — De contentmachine aan (later, wanneer jij wilt)

15. **Netlify-account**: https://netlify.com → inloggen met GitHub → **Add new site → Import an existing project** → kies de repo. Netlify leest `netlify.toml` en bouwt de gidsen-site.
16. **Secrets voor de automatische releases**: 
    - Netlify → **User settings → Applications → New access token** → kopieer de token;
    - Netlify → je site → **Site configuration** → kopieer de **Site ID**;
    - GitHub → repo **Rroobbbb/plantwijs → Settings → Secrets and variables → Actions** → voeg toe: `NETLIFY_AUTH_TOKEN` en `NETLIFY_SITE_ID`.
17. **Proxy invullen**: geef mij je Render-adres door ("zeg het Claude") — dan vul ik de placeholder in `site/_redirects` in, zodat Netlify de app doorstuurt naar Render.
18. **DNS omzetten**: in Netlify → **Domain management** → `beplantingswijzer.nl` toevoegen → volg de DNS-instructies (vervangt de records uit stap 8; het domein wijst dan naar Netlify, die de app doorproxyt). Daarna in Render het custom domain weghalen.
19. **Start de schrijfcadans**: zeg het Claude — dan starten de schrijf- en verificatie-agents met de eerste 12 artikelen uit SEO_PLAN §7, en publiceert de pipeline vanzelf elke 3 dagen wat klaarstaat.

## Daarna — onderhoudsritme (weinig werk)

- **Maandelijks** (5 min): Search Console openen — welke zoektermen groeien? Ik stuur bij in de contentplanning.
- **Twee keer per jaar**: dataset verversen — zeg het Claude, dan draai ik scraper + verrijking + controle + deploy.
- **Bij een nieuwe artikelronde**: alleen jij leest de geverifieerde concepten na (jouw vakblik blijft de laatste stap).

## Als er iets misgaat
- Render-build faalt → stuur mij de buildlog (Render → Events/Logs), ik fix het.
- Site traag na stilte → dat is de gratis-plan-slaapstand (stap 6).
- Dataset kapot/leeg → de app weigert bewust sets onder 500 rijen en valt terug op GitHub; `/api/admin/reload?key=JOUW_SLEUTEL` laadt opnieuw.

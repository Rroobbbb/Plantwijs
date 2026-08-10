# Verificatie van `content/context_descriptions.yaml`

Feitencontrole van alle 91 entries (categorieën `fgr`, `bodem`, `vocht`, `gmm`, `nsn`)
tegen gezaghebbende bronnen. Uitgevoerd op 10 augustus 2026.

**Brondiscipline.** Alleen overheids-, instituuts- en wetenschappelijke bronnen zijn
gebruikt: TNO Geologische Dienst Nederland (Geologie van Nederland), Rijksdienst voor
het Cultureel Erfgoed (RCE), natuurkennis.nl (OBN), Wageningen University & Research,
Basisregistratie Ondergrond (BRO), PDOK en Rijkswaterstaat. Blogs, tuincentra,
Wikipedia-als-eindbron en commerciële sites zijn niet gebruikt.

**Wat is er gewijzigd.** Alleen de tekstvelden `titel`, `ontstaan`, `versterken` en
`bron`. De structuur (`id`, `match`, `match_exact`, veldnamen, volgorde) is
ongemoeid gebleven. Het bestand parseert; de matchdekking is ongewijzigd.

---

## Vooraf: twee bevindingen die buiten de opdrachtgrens vallen

### 1. De kaartwaarde is `Niet indeelbaar`, niet `niet ingedeeld` — 25% van de FGR-vlakken valt terug op de fallback

De FGR-laag van PDOK is uitgelezen via de WFS
(`https://service.pdok.nl/ez/fysischgeografischeregios/wfs/v1_0`). De laag bevat
958 vlakken met exact tien waarden:

| Waarde | Aantal vlakken |
|---|---|
| Hogere Zandgronden | 307 |
| **Niet indeelbaar** | **239** |
| Zeekleigebied | 124 |
| Duinen | 122 |
| Laagveengebied | 117 |
| Rivierengebied | 25 |
| Heuvelland | 11 |
| Afgesloten Zeearmen | 9 |
| Getijdengebied | 3 |
| Noordzee | 1 |

De entry `fgr_niet_ingedeeld` matcht op `"niet ingedeeld"`, maar de bron schrijft
`"Niet indeelbaar"`. Gecontroleerd met de echte matcher:

```
Niet indeelbaar  ->  onbekend      (valt terug op de fallback)
Noordzee         ->  fgr_niet_ingedeeld
```

De op één na grootste FGR-waarde krijgt dus het fallback-verhaal in plaats van het
verhaal dat er speciaal voor is geschreven. Steekproef op de ligging: Amsterdam,
Rotterdam, Utrecht en Maastricht geven `Niet indeelbaar`; Eindhoven en Groningen niet.
Het gaat dus vooral om grote steden en sterk vergraven terrein.

**Niet gerepareerd**, omdat `match`/`match_exact` buiten de opdracht viel. De
`titel` en `ontstaan` van deze entry zijn wél feitelijk gecorrigeerd (zie tabel FGR),
zodat de tekst klopt zodra de matchterm wordt toegevoegd. Aanbevolen minimale fix:
`match_exact: ["niet indeelbaar", "niet ingedeeld", "noordzee"]`.

### 2. De FGR-indeling kent geen `hoogveenontginningsgebied`

De categorie `fgr` dekt met tien entries alle tien voorkomende waarden (op de bug
hierboven na). Er ontbreekt geen entry; het hoogveenontginningsgebied dat in sommige
oudere indelingen voorkomt, zit niet in deze PDOK-laag.

---

## FGR — Fysisch-Geografische Regio's

| Entry | Oordeel | Wat is aangepast | Bron |
|---|---|---|---|
| `hogere_zandgronden` | genuanceerd | "laatste ijstijden" → "de laatste ijstijd, het Weichselien"; podzolbeschrijving preciezer (uitspoeling van ijzer, aluminium en humus, inspoeling daaronder); plaggenlandbouw gedateerd "vanaf de middeleeuwen tot het eind van de negentiende eeuw" | [Geologie van Nederland — dekzand](https://www.geologievannederland.nl/landschap/landschapsvormen/dekzand), [podzolbodem](https://www.geologievannederland.nl/ondergrond/bodems/podzolbodem-zandlandschap.html), [RCE — Oude akkercomplexen](https://kennis.cultureelerfgoed.nl/index.php/Oude_akkercomplexen_(cultuurhistorisch_beheer)) |
| `heuvelland` | gecorrigeerd | Kalksteen gedateerd op het Krijt; tektonische opheffing toegevoegd als oorzaak van de insnijding; löss "plaatselijk tot wel vijftien meter dik"; **graften afgezwakt** van "legden boeren graften aan" naar "waarschijnlijk aangelegd om erosie tegen te gaan"; "dwars op de helling" → "evenwijdig aan de hoogtelijnen"; tamme kastanje als erfboom geschrapt (niet onderbouwd) | [natuurkennis.nl (OBN) — Heuvellandschap](https://natuurkennis.nl/landschappen/heuvellandschap/) |
| `rivierengebied` | klopt | Alleen bron aangevuld; advies verwijst nu naar rivierbeheerder én waterschap | [Geologie van Nederland — rivierlandschap](https://www.geologievannederland.nl/landschap/landschappen/rivierlandschap), [Rijkswaterstaat — beheer uiterwaarden](https://www.rijkswaterstaat.nl/water/waterbeheer/bescherming-tegen-het-water/maatregelen-om-overstromingen-te-voorkomen/beheer-van-uiterwaarden-voor-een-veilig-rivierengebied) |
| `zeekleigebied` | genuanceerd | Reliëfinversie explicieter: het zijn niet "zand klinkt minder in" alleen, maar de klei ernaast klonk ná ontwatering sterk in | [Geologie van Nederland — kwelder en kreekrug](https://www.geologievannederland.nl/landschap/landschapsvormen/kwelder-en-kreekrug) |
| `laagveengebied` | gecorrigeerd | "Achter de duinen en de oude kwelders" → "achter de strandwallen en duinen raakte het achterland afgesloten van de zee"; ontginning gedateerd "vanaf ongeveer de elfde eeuw" in plaats van het vage "vanaf de middeleeuwen" | [Geologie van Nederland — veenlandschap](https://www.geologievannederland.nl/landschap/landschappen/veenlandschap), [natuurkennis.nl (OBN) — Laagveen- en zeekleilandschap](https://natuurkennis.nl/landschappen/laagveen-zeekleilandschap/) |
| `duinen` | gecorrigeerd | Datering toegevoegd (oude duinen ca. 5000–2000 jaar geleden, jonge duinen ca. 1200–1600); **kalkclaim gecorrigeerd**: alleen ten zuiden van Bergen is het duinzand kalkrijk, op de Waddeneilanden en ten noorden ervan is het van nature kalkarm | [Geologie van Nederland — kustduin](https://www.geologievannederland.nl/landschap/landschapsvormen/kustduin), [natuurkennis.nl (OBN) — Duin- en kustlandschap](https://natuurkennis.nl/landschappen/duin-en-kustlandschap/) |
| `getijdengebied` | klopt | Alleen bron aangevuld | [Geologie van Nederland — zeekleiafzettingen en kwelders](https://www.geologievannederland.nl/landschap/landschapsvormen/zeekleiafzettingen-en-kwelders.html) |
| `afgesloten_zeearmen` | **gecorrigeerd** | De tekst schreef de afsluiting volledig toe aan 1953. De grootste afgesloten zeearm is de Zuiderzee, in **1932** door de Afsluitdijk gescheiden van de Waddenzee. Empirisch bevestigd: een punt in het IJsselmeer en in het Markermeer geeft `Afgesloten Zeearmen`. Deltawerken gedateerd 1956–1998 met de juiste wateren genoemd | [Rijkswaterstaat — Afsluitdijk](https://www.rijkswaterstaat.nl/water/waterbeheer/bescherming-tegen-het-water/waterkeringen/dijken/afsluitdijk), [Deltawerken/Oosterscheldekering](https://www.rijkswaterstaat.nl/water/waterbeheer/bescherming-tegen-het-water/waterkeringen/deltawerken/oosterscheldekering) |
| `fgr_niet_ingedeeld` | **gecorrigeerd** | De tekst zei "open zee, grote wateren en opgespoten land". In werkelijkheid ligt `Niet indeelbaar` vooral op grote steden en sterk vergraven terrein; `Noordzee` is de aparte waarde voor open zee. Titel aangepast naar "Niet indeelbaar of open zee" | [PDOK FGR WFS](https://service.pdok.nl/ez/fysischgeografischeregios/wfs/v1_0), eigen uitlezing van alle 958 vlakken en puntsteekproef |
| `onbekend` | klopt | Alleen bron ("geen kaartwaarde beschikbaar") | — |

---

## BODEM — BRO Bodemkaart

| Entry | Oordeel | Wat is aangepast | Bron |
|---|---|---|---|
| `zand` | klopt | Alleen bron | [Geologie van Nederland — zandlandschap](https://www.geologievannederland.nl/landschap/landschappen/zandlandschap), [podzolbodem](https://www.geologievannederland.nl/ondergrond/bodems/podzolbodem-zandlandschap.html) |
| `klei` | klopt | Alleen bron | [Geologie van Nederland — zeekleibodem](https://www.geologievannederland.nl/ondergrond/bodems/zeekleibodem-zeekleilandschap.html) |
| `leem` | genuanceerd | Dikte van het lösspakket toegevoegd ("plaatselijk tot wel vijftien meter") | [natuurkennis.nl (OBN) — Heuvellandschap](https://natuurkennis.nl/landschappen/heuvellandschap/), [Geologie van Nederland — löss](https://www.geologievannederland.nl/publicaties/111.html) |
| `veen` | klopt | Alleen bron. De claim dat ontwatering leidt tot oxidatie en bodemdaling die nog doorgaat, is bevestigd | [Geologie van Nederland — veenlandschap](https://www.geologievannederland.nl/landschap/landschappen/veenlandschap), [natuurkennis.nl (OBN) — Hoogveen](https://natuurkennis.nl/beheertypen/n06-voedselarme-venen-en-vochtige-heiden/n06-03-hoogveen/) |
| `onbekend` | klopt | Alleen bron | — |

---

## VOCHT — vochtklasse uit de grondwatertrap (Gt)

De backend (`plantwijs/services/pdok.py`) mapt de Gt-code op de vochtklasse:
I–II → zeer nat, III → nat, IV–V → vochtig, VI → droog, VII–VIII → zeer droog.
Alle vijf teksten zijn getoetst aan de officiële GHG/GLG-klassegrenzen uit de
BRO-catalogus Model grondwaterspiegeldiepte. Twee teksten waren daarmee in strijd.

| Entry | Oordeel | Wat is aangepast | Bron |
|---|---|---|---|
| `zeer_nat` | genuanceerd | Concreet gemaakt met de klassegrenzen van Gt I–II: in de natste tijd binnen ca. een halve meter, in de droogste tijd zelden dieper dan 80 cm | [BRO — Model grondwaterspiegeldiepte (Gt-tabel)](https://docs.geostandaarden.nl/bro/wdm/) |
| `nat` | genuanceerd | Gt III concreet gemaakt: GHG binnen ca. 40 cm, GLG tussen 80 en 120 cm | idem |
| `vochtig` | genuanceerd | Gt IV–V concreet gemaakt: GHG tussen ca. 25 en 80 cm, GLG dieper dan 80 cm en soms dieper dan 1,2 m | idem |
| `droog` | **gecorrigeerd** | De tekst zei "het grondwater staat hier diep, **ook in de winter**". Dat is onjuist voor Gt VI: de GHG ligt tussen 40 en 80 cm beneden maaiveld. Herschreven naar "een halve tot een hele meter in de natte tijd, in de droge tijd dieper dan 1,2 meter" | idem |
| `zeer_droog` | **gecorrigeerd** | De tekst zei "het hele jaar buiten bereik van de wortels" als hard feit. Gt VII heeft een GHG van 80–140 cm; dat is voor diepwortelende bomen niet per definitie buiten bereik. Afgezwakt naar "voor vrijwel alle beplanting" en de klassegrenzen genoemd | idem |
| `onbekend` | klopt | Alleen bron | — |

---

## GMM — Geomorfologische kaart

| Entry | Oordeel | Wat is aangepast | Bron |
|---|---|---|---|
| `esdek_oud_bouwland` | **gecorrigeerd** | De potstal werd voorgesteld als de manier waarop essen altijd zijn opgehoogd. Plaggenlandbouw ontstaat vanaf de volle middeleeuwen; het mengen in een **speciale potstal** dateert waarschijnlijk pas van de achttiende eeuw. Dikte genuanceerd naar "dertig centimeter tot ruim een meter" in plaats van "soms wel een meter" | [RCE — Oude akkercomplexen](https://kennis.cultureelerfgoed.nl/index.php/Oude_akkercomplexen_(cultuurhistorisch_beheer)) |
| `dekzandrug` | genuanceerd | Toegevoegd dat het reliëf pas laat in de ijstijd vastliep doordat er begroeiing kwam; afmetingen toegevoegd (kilometers lang, ca. honderd meter breed) | [Geologie van Nederland — dekzand](https://www.geologievannederland.nl/landschap/landschapsvormen/dekzand) |
| `dekzandvlakte` | klopt | Alleen bron | idem |
| `stuifzand_landduinen` | klopt | Alleen bron. Overbeweiding, plaggensteken en vastlegging met grove den zijn bevestigd | [Geologie van Nederland — stuifzand](https://www.geologievannederland.nl/landschap/landschapsvormen/stuifzand) |
| `stuwwal` | genuanceerd | 150.000 jaar geleden bevestigd; ijstijd bij naam genoemd (Saalien), de grens van het landijs (lijn Haarlem–Utrecht–Nijmegen) en de hoogte (ruim honderd meter) toegevoegd | [Geologie van Nederland — stuwwal](https://www.geologievannederland.nl/landschap/landschapsvormen/stuwwal) |
| `smeltwaterwaaier` | klopt | Alleen bron | [Geologie van Nederland — spoelzandwaaier](https://www.geologievannederland.nl/landschap/landschapsvormen/spoelzandwaaier) |
| `droogdal` | klopt | Alleen bron. Permafrost + oppervlakkig afstromend smeltwater bevestigd | [Geologie van Nederland](https://www.geologievannederland.nl/landschap/landschapsvormen), [natuurkennis.nl — Heuvellandschap](https://natuurkennis.nl/landschappen/heuvellandschap/) |
| `loss_glooiing_plateau` | gecorrigeerd | Graften afgezwakt naar "waarschijnlijk aangelegd"; holle wegen toegeschreven aan insnijding door gebruik; advies "dwars op de helling" → "evenwijdig aan de hoogtelijnen" (eenduidiger en correct) | [natuurkennis.nl (OBN) — Heuvellandschap](https://natuurkennis.nl/landschappen/heuvellandschap/) |
| `beekdalbodem` | klopt | Alleen bron. Kwel, hooilandgebruik en normalisatie bevestigd | [natuurkennis.nl (OBN) — Beekdallandschap](https://natuurkennis.nl/landschappen/beekdallandschap/) |
| `rivierduin_donk` | genuanceerd | Toegevoegd dat het grootste deel van het rivierduin onder veen en klei begraven ligt en dat de donk de top is | [Geologie van Nederland — rivierduin](https://www.geologievannederland.nl/landschap/landschapsvormen/rivierduin) |
| `oeverwal_stroomrug` | klopt | Alleen bron | [Geologie van Nederland — rivierlandschap](https://www.geologievannederland.nl/landschap/landschappen/rivierlandschap) |
| `komvlakte` | klopt | Alleen bron | idem |
| `uiterwaard` | genuanceerd | Advies concreet gemaakt: Rijkswaterstaat legt in de **vegetatielegger** vast welke begroeiing is toegestaan; vaak is een vergunning nodig | [Rijkswaterstaat — vegetatielegger](https://www.rijkswaterstaat.nl/water/waterbeheer/bescherming-tegen-het-water/waterkeringen/leggers/vegetatielegger/informatie-voor-terreineigenaren) |
| `rivierterras` | klopt | Alleen bron | [Geologie van Nederland](https://www.geologievannederland.nl/landschap/landschapsvormen/smeltwaterterras) |
| `strandwal_strandvlakte` | **gecorrigeerd** | "Toen de zeespiegel na de laatste ijstijd steeg, bouwde de zee zandruggen op" is de omkering van het mechanisme: strandwallen ontstonden juist toen de stijging ca. 5000 jaar geleden **afzwakte** (van ca. 1 m naar 15 cm per eeuw). Einddatering toegevoegd (begin van onze jaartelling) | [Geologie van Nederland — strandwal](https://www.geologievannederland.nl/landschap/landschapsvormen/strandwal), [Strandwal Spaarnwoude](https://www.geologievannederland.nl/landschap/geologische-locaties/strandwal-spaarnwoude) |
| `kustduinen` | **gecorrigeerd** | "vanaf ongeveer duizend jaar geleden" → "vooral tussen ongeveer 1200 en 1600"; kalkclaim genuanceerd met de grens bij Bergen | [Geologie van Nederland — kustduin](https://www.geologievannederland.nl/landschap/landschapsvormen/kustduin), [natuurkennis.nl (OBN) — Duin- en kustlandschap](https://natuurkennis.nl/landschappen/duin-en-kustlandschap/) |
| `getijdenvlakte_kwelder` | klopt | Alleen bron | [Geologie van Nederland — kwelder en kreekrug](https://www.geologievannederland.nl/landschap/landschapsvormen/kwelder-en-kreekrug) |
| `ontgonnen_veenvlakte` | klopt | Alleen bron. "Vanaf de zeventiende eeuw" bevestigd | [RCE — Panorama Landschap, Veenkoloniën en Westerwolde](https://kennis.cultureelerfgoed.nl/index.php/Panorama_Landschap_-_Veenkoloni%C3%ABn_en_Westerwolde) |
| `droogmakerij` | klopt | Alleen bron. "Vanaf de zeventiende eeuw" bevestigd | [RCE — droogmakerijen (landschapszone)](https://kennis.cultureelerfgoed.nl/index.php/Begrip:Ff8e83fe-8c42-450a-ad53-f71b399f00c5) |
| `veenvlakte` | klopt | Alleen bron | [Geologie van Nederland — veenlandschap](https://www.geologievannederland.nl/landschap/landschappen/veenlandschap) |
| `gmm_antropogeen` | **gecorrigeerd** | Terpen gedateerd op "vanaf ongeveer 500 voor Christus" (was: impliciet ongedateerd) | [RCE — Terp (cultuurhistorisch beheer)](https://kennis.cultureelerfgoed.nl/index.php/Terp_(cultuurhistorisch_beheer)) |
| `onbekend` | klopt | Alleen bron | — |

---

## NSN — Basiskaart Natuurlijk Systeem Nederland (BKNSN 2023)

Voor deze categorie is naast de literatuur ook de **brondata zelf** gebruikt:
`data/LBK_BKNSN_2023.zip` is gescand op `BKNSN_code`, en van de twijfelgevallen zijn
coördinaten uitgelezen en omgezet naar WGS84 om te zien in welk landschap het label
werkelijk ligt. Dat leverde drie inhoudelijke correcties op (`beekdal`, `depressie`,
`rivierterras`, `overige_afzettingen`).

| Entry | Oordeel | Wat is aangepast | Bron |
|---|---|---|---|
| `ontgonnen_hoogveen` | genuanceerd | Vervening gedateerd "eerste helft van de zeventiende eeuw"; rol van Hollands kapitaal en de dubbele functie van kanalen en wijken (afwatering én transport) toegevoegd; dalgrond correct beschreven als zand vermengd met bolster | [RCE — Panorama Landschap, Veenkoloniën en Westerwolde](https://kennis.cultureelerfgoed.nl/index.php/Panorama_Landschap_-_Veenkoloni%C3%ABn_en_Westerwolde) |
| `hoogveen` | klopt | Alleen bron. Veenmos, regenwatervoeding, bolle kussenvorm en de noodzaak van een permanent hoge waterstand zijn bevestigd; ook het beheeradvies om berken- en dennenopslag te verwijderen | [natuurkennis.nl (OBN) — N06.03 Hoogveen](https://natuurkennis.nl/beheertypen/n06-voedselarme-venen-en-vochtige-heiden/n06-03-hoogveen/), [Geologie van Nederland — hoogveen](https://www.geologievannederland.nl/landschap/landschapsvormen/hoogveen) |
| `beekdal_veen` | klopt | Alleen bron. Kwel met basenrijk grondwater en elzenbroekbos bevestigd | [natuurkennis.nl (OBN) — Beekdallandschap](https://natuurkennis.nl/landschappen/beekdallandschap/) |
| `beekdal_zand_leem` | klopt | Alleen bron | idem |
| `beekdal` | **gecorrigeerd** | Dit label is code `Lg5` en hoort bij het **löss- en heuvellandschap**; steekproef uit de brondata plaatst de vlakken rond 50,75° N / 5,90° O (Geuldal, Zuid-Limburg). De generieke zandlandschap-beschrijving is vervangen door een beschrijving met bronbeken en kwel waar de ondergrond slecht doorlatend is | [natuurkennis.nl (OBN) — Heuvellandschap](https://natuurkennis.nl/landschappen/heuvellandschap/), eigen scan van `LBK_BKNSN_2023.zip` |
| `pingoruine` | genuanceerd | Mechanisme preciezer (grondwater onder druk door een scheur in de permafrost, ijslens groeit aan); hoogte, datering (ca. 13.000–11.000 jaar geleden), verspreiding (Friesland, Groningen, Drenthe, Overijssel) en de opvulling met veen toegevoegd | [Geologie van Nederland — pingoruïne](https://www.geologievannederland.nl/landschap/landschapsvormen/pingoruine) |
| `depressie_veen` | klopt | Alleen bron | [natuurkennis.nl (OBN)](https://natuurkennis.nl/beheertypen/n06-voedselarme-venen-en-vochtige-heiden/n06-03-hoogveen/) |
| `depressie_zand` | klopt | Alleen bron | idem |
| `depressie` | **gecorrigeerd** | Dit label is code `Hv3` en hoort bij het **hoogveenlandschap**; steekproef uit de brondata plaatst de vlakken rond 51,22° N / 5,58° O (Peelregio). De generieke tekst is verankerd in dat landschap | eigen scan van `LBK_BKNSN_2023.zip`; [BKNSN technische documentatie](https://klimaatadaptatienederland.nl/hulpmiddelen/overzicht/basiskaart-natuurlijk-systeem/) |
| `droogdal` | klopt | Alleen bron. De varianten met keileem en veen (codes `Sw4x`, `Sw4v`) zijn correct verwerkt | [Geologie van Nederland](https://www.geologievannederland.nl/landschap/landschapsvormen), [natuurkennis.nl — Heuvellandschap](https://natuurkennis.nl/landschappen/heuvellandschap/) |
| `rivierterras_zand` | klopt | Alleen bron | [Geologie van Nederland](https://www.geologievannederland.nl/landschap/landschapsvormen/smeltwaterterras) |
| `rivierterras_klei` | klopt | Alleen bron | idem |
| `rivierterras` | **gecorrigeerd** | Dit label is code `Lg7` en ligt in het löss- en heuvellandschap van Zuid-Limburg (steekproef rond 50,77° N / 5,82° O). "langs Maas en Rijn" is teruggebracht tot de Maas; tektonische opheffing toegevoegd als reden dat er terrastrappen ontstonden | eigen scan van `LBK_BKNSN_2023.zip`; [natuurkennis.nl — Heuvellandschap](https://natuurkennis.nl/landschappen/heuvellandschap/) |
| `laagveenvlakte` | genuanceerd | Ontginning gedateerd "vanaf ongeveer de elfde eeuw"; toegevoegd dat de bodemdaling nog doorgaat | [Geologie van Nederland — laagveen](https://www.geologievannederland.nl/landschap/landschapsvormen/laagveen), [natuurkennis.nl (OBN) — Laagveen- en zeekleilandschap](https://natuurkennis.nl/landschappen/laagveen-zeekleilandschap/) |
| `zeekleivlakte` | klopt | Alleen bron | [Geologie van Nederland — zeekleilandschap](https://www.geologievannederland.nl/landschap/landschappen/zeekleilandschap) |
| `strandvlakte` | klopt | Alleen bron | [Geologie van Nederland — strandwal](https://www.geologievannederland.nl/landschap/landschapsvormen/strandwal) |
| `strandwal` | **gecorrigeerd** | Zelfde correctie als bij `strandwal_strandvlakte`: strandwallen ontstonden toen de zeespiegelstijging ca. 5000 jaar geleden afzwakte, niet doordat de zeespiegel steeg. Einddatering toegevoegd | [Geologie van Nederland — strandwal](https://www.geologievannederland.nl/landschap/landschapsvormen/strandwal) |
| `grondmorene_plateau` | genuanceerd | Saalien bij naam genoemd; keileem beschreven als meestal kalkloos en met leem in de mengeling; Drents Plateau als voorbeeld toegevoegd | [Geologie van Nederland — grondmorene](https://www.geologievannederland.nl/landschap/landschapsvormen/grondmorene), [RCE — keileemruggen Zuidwolde](https://kennis.cultureelerfgoed.nl/index.php/Aardkundig_erfgoed/De_ruggen_van_Zuidwolde_en_omgeving) |
| `grondmorenerug` | genuanceerd | "opgehoopt in de richting waarin het ijs bewoog" vervangen door de gedocumenteerde situatie: opgestuwd aan de randen van het keileemplateau, oriëntatie NNO–ZZW, wat verraadt dat het ijs uit het noorden kwam | [RCE — keileemruggen Zuidwolde](https://kennis.cultureelerfgoed.nl/index.php/Aardkundig_erfgoed/De_ruggen_van_Zuidwolde_en_omgeving) |
| `dekzandrug` | klopt | Alleen bron | [Geologie van Nederland — dekzand](https://www.geologievannederland.nl/landschap/landschapsvormen/dekzand) |
| `dekzandvlakte` | klopt | Alleen bron | idem |
| `stuifzandduin` | klopt | Alleen bron | [Geologie van Nederland — stuifzand](https://www.geologievannederland.nl/landschap/landschapsvormen/stuifzand) |
| `restgeul` | klopt | Alleen bron | [Geologie van Nederland — rivierlandschap](https://www.geologievannederland.nl/landschap/landschappen/rivierlandschap) |
| `veenrest` | klopt | Alleen bron | [Geologie van Nederland — veenlandschap](https://www.geologievannederland.nl/landschap/landschappen/veenlandschap) |
| `kreekrug` | klopt | Alleen bron. Het inversiemechanisme (zandvulling klinkt niet in, omringende klei wel na ontwatering) is precies zoals beschreven | [Geologie van Nederland — kwelder en kreekrug](https://www.geologievannederland.nl/landschap/landschapsvormen/kwelder-en-kreekrug) |
| `kreekbedding` | genuanceerd | Toegevoegd waarom sommige kreekvullingen wél tot een kreekrug werden en deze niet; daarmee is de spanning met de entry `kreekrug` weggenomen | idem |
| `meerbodem` | klopt | Alleen bron | [RCE — droogmakerijen](https://kennis.cultureelerfgoed.nl/index.php/Begrip:Ff8e83fe-8c42-450a-ad53-f71b399f00c5) |
| `petgaten` | klopt | Alleen bron. Legakkers, wegslaan bij storm en verlanding van open water via rietland naar moerasbos bevestigd | [natuurkennis.nl (OBN) — Laagveen- en zeekleilandschap](https://natuurkennis.nl/landschappen/laagveen-zeekleilandschap/) |
| `stroomrug_oeverwal` | klopt | Alleen bron | [Geologie van Nederland — rivierlandschap](https://www.geologievannederland.nl/landschap/landschappen/rivierlandschap) |
| `rivierkom` | klopt | Alleen bron | idem |
| `uiterwaard` | genuanceerd | Advies concreet gemaakt met de vegetatielegger van Rijkswaterstaat | [Rijkswaterstaat — vegetatielegger](https://www.rijkswaterstaat.nl/water/waterbeheer/bescherming-tegen-het-water/waterkeringen/leggers/vegetatielegger/informatie-voor-terreineigenaren) |
| `overslaggronden` | **gecorrigeerd** | De waaier werd als puur zandig, licht en **droog** beschreven. Overslaggronden bestaan uit klei vermengd met grof zand en soms grind, zijn tot ca. 1,5 m dik en juist **vruchtbaar** en van oudsher gewild voor fruitteelt. Toegevoegd dat de herstelde dijk meestal in een bocht om het wiel loopt; advies aangevuld met hoogstamboomgaard | [RCE — Dijkdoorbraakgaten (beheermodel)](https://kennis.cultureelerfgoed.nl/index.php/Dijkdoorbraakgaten_(beheermodel)), [Geologie van Nederland — doorbraakgaten](https://www.geologievannederland.nl/landschap/landschapsvormen/doorbraakgaten.html) |
| `rivierduin` | genuanceerd | Donk beschreven als de top van een grotendeels begraven rivierduin; bewoning gepreciseerd naar "al in de steentijd" | [Geologie van Nederland — rivierduin](https://www.geologievannederland.nl/landschap/landschapsvormen/rivierduin) |
| `kustduinen` | **gecorrigeerd** | Zelfde correctie als bij de GMM-entry: datering 1200–1600 en de kalkgrens bij Bergen | [Geologie van Nederland — kustduin](https://www.geologievannederland.nl/landschap/landschapsvormen/kustduin), [natuurkennis.nl (OBN) — Duin- en kustlandschap](https://natuurkennis.nl/landschappen/duin-en-kustlandschap/) |
| `stuwwal` | genuanceerd | Saalien, ijsgrens Haarlem–Utrecht–Nijmegen en hoogte toegevoegd | [Geologie van Nederland — stuwwal](https://www.geologievannederland.nl/landschap/landschapsvormen/stuwwal) |
| `smeltwaterafzetting` | klopt | Alleen bron | [Geologie van Nederland — spoelzandwaaier](https://www.geologievannederland.nl/landschap/landschapsvormen/spoelzandwaaier) |
| `daluitspoelingswaaier` | klopt | Alleen bron | idem |
| `lossplateau` | genuanceerd | Ondergrond gespecificeerd (kalksteen uit het Krijt en Maasafzettingen); lössdikte toegevoegd | [natuurkennis.nl (OBN) — Heuvellandschap](https://natuurkennis.nl/landschappen/heuvellandschap/) |
| `losshelling` | gecorrigeerd | Graften afgezwakt naar "waarschijnlijk aangelegd"; "dwars op de helling" → "evenwijdig aan de hoogtelijnen" in tekst én advies | idem |
| `kalkhelling` | genuanceerd | Krijt als vormingsperiode; pH 7–8 toegevoegd; **belangrijkste toevoeging**: kalkgrasland is een half-natuurlijk systeem dat is ontstaan door eeuwenlange schapenbegrazing zonder bemesting — dat ontbrak volledig | [natuurkennis.nl (OBN) — H6210 Kalkgraslanden](https://natuurkennis.nl/habitattypen/h6210-kalkgraslanden/) |
| `zoetwatergetijdenafzetting` | **gecorrigeerd** | "Het waterstandsverschil was klein maar constant" was onjuist: het getijverschil was juist fors en is pas **door de Deltawerken** teruggebracht tot enkele decimeters. Sint-Elisabethsvloed 1421 toegevoegd. Griendcyclus gecorrigeerd van "één tot drie jaar" naar snijgriend jaarlijks en hakgriend elke drie tot vijf jaar | [RCE — Panorama Landschap, Biesbosch](https://kennis.cultureelerfgoed.nl/index.php/Panorama_Landschap_-_Biesbosch), [natuurkennis.nl (OBN) — N17.05 Wilgengriend](https://natuurkennis.nl/beheertypen/n17-cultuurhistorische-bossen/n17-05-wilgengriend/) |
| `zoutwatergetijdenafzetting` | klopt | Alleen bron | [Geologie van Nederland — zeekleiafzettingen en kwelders](https://www.geologievannederland.nl/landschap/landschapsvormen/zeekleiafzettingen-en-kwelders.html) |
| `overige_afzettingen` | **gecorrigeerd** | De tekst noemde speculatieve voorbeelden ("hellingpuin, plaatselijk grind, een lokale leemlaag") zonder bron en suggereerde een landelijke restcategorie. Code `Lg8` ligt uitsluitend in het löss- en heuvellandschap van Zuid-Limburg (steekproef rond 50,75° N / 5,90–6,01° O). Voorbeelden geschrapt, landschap benoemd | eigen scan van `LBK_BKNSN_2023.zip` |
| `terp` | **gecorrigeerd** | "vanaf ongeveer tweeduizend jaar geleden" is ca. vijfhonderd jaar te laat: de oudste terpen dateren van omstreeks **500 voor Christus**. Toegevoegd dat de terpen omstreeks 1200 hun grootste hoogte bereikten. Beschermingsclaim gepreciseerd naar de formulering van de RCE | [RCE — Terp (cultuurhistorisch beheer)](https://kennis.cultureelerfgoed.nl/index.php/Terp_(cultuurhistorisch_beheer)) |
| `water` | klopt | Alleen bron | — |
| `es` | **gecorrigeerd** | Zelfde potstalcorrectie als bij `esdek_oud_bouwland`: plaggenlandbouw vanaf de middeleeuwen, potstal pas vanaf ca. de achttiende eeuw; dikte 30 cm tot ruim 1 m. Het advies "graaf niet af" is aangevuld met "ploeg niet dieper dan gebruikelijk", conform het RCE-beheeradvies | [RCE — Oude akkercomplexen](https://kennis.cultureelerfgoed.nl/index.php/Oude_akkercomplexen_(cultuurhistorisch_beheer)) |
| `antropogeen_element` | klopt | Alleen bron | — |
| `onbekend` | klopt | Alleen bron | — |

---

## Dekkingsverklaring

**Diepgaand gecontroleerd, met bron per claim:**

- Alle **jaartallen en dateringen** in het bestand. Dat waren de risicovolste claims en
  daar zaten ook de meeste fouten: terpen, jonge duinen, strandwallen, afgesloten
  zeearmen, potstal/esdek, veenontginning. Elk jaartal in de huidige tekst is
  herleidbaar tot een van de bronnen in de tabellen hierboven.
- Alle **vijf vochtklassen**, getoetst aan de officiële GHG/GLG-klassegrenzen uit de
  BRO-catalogus én aan de mapping die de backend feitelijk toepast.
- De **FGR-categorie in zijn geheel**, inclusief een volledige uitlezing van de
  PDOK-WFS (alle 958 vlakken, alle tien waarden) en een puntsteekproef op tien
  locaties, waarmee de matchbug en de foute omschrijving van `Niet indeelbaar` boven
  water kwamen.
- De **twijfelachtige NSN-labels** (`beekdal`, `depressie`, `rivierterras`,
  `overige_afzettingen`), geverifieerd door de brondata zelf te scannen op
  `BKNSN_code` en de coördinaten om te zetten naar WGS84.
- De **ontstaansmechanismen** die makkelijk verkeerd verteld worden: reliëfinversie bij
  kreekruggen, podzolvorming, pingovorming, strandwalvorming, en het getijverschil in
  zoetwatergetijdengebied.

**Steekproefsgewijs gecontroleerd:**

- De **soortenlijsten in de `versterken`-adviezen**. Die zijn getoetst op standplaats
  (droogte/nat/kalk/zout) tegen de landschapsbeschrijvingen van OBN en op aanwezigheid
  in `data/treeebb_planten_allfields.csv`, maar niet soort voor soort tegen
  verspreidingsdata van FLORON of het Nederlands Soortenregister. Er is één soort
  geschrapt (tamme kastanje als traditionele erfboom in Zuid-Limburg, niet
  onderbouwd) en er zijn géén nieuwe soorten toegevoegd, zodat de koppeling met de
  dataset intact blijft.
- De **beheeradviezen** (maaien en afvoeren, niet bemesten, gefaseerd maaien, niet
  draineren). Deze zijn consistent met het OBN-beheeradvies voor de betreffende
  natuurtypen, maar zijn niet per bullet tegen een beheerrichtlijn gelegd.
- De **cultuurhistorische beplantingsvormen** per streek (houtwal op zand, meidoornhaag
  op de oeverwal, elzensingel in laagveen). Deze zijn plausibel en komen overeen met de
  RCE-landschapsbeschrijvingen, maar zijn niet per streek tegen een landschapsbiografie
  gecontroleerd.

**Niet gecontroleerd:**

- De volledige **BKNSN-legendadefinities** per subtype. De technische documentatie is
  alleen als PDF beschikbaar en kon in deze omgeving niet als tekst worden uitgelezen.
  De landschapstoewijzing per code is daarom afgeleid uit het codeprefix in
  `content/_inventaris_nsn.txt` **plus** een eigen geografische steekproef op de
  brondata. Dat is voldoende om de vier correcties te dragen, maar een lezing van de
  officiële legendatabel blijft wenselijk.
- Het exacte **historische getijverschil in de Biesbosch** vóór de Deltawerken. De RCE
  noemt alleen de huidige situatie ("teruggebracht tot enkele decimeters"). De tekst
  claimt daarom geen getal voor de oude situatie.

**Validatie:** het YAML parseert; alle 91 entries hebben alle zeven verplichte velden
gevuld; de testsuite draait met 264 geslaagde tests. Twee tests falen
(`test_dataset_namen.py::test_kolommen_aanwezig` en
`test_ai_toegang.py::test_format_md_bevat_soortentabel_met_max_40_rijen`); beide komen
door een gewijzigde `data/treeebb_planten_allfields.csv` (1644 → 1642 rijen, 43 → 49
kolommen) en staan los van deze contentwijzigingen.

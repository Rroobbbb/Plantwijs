README - TreeEbb scraper (alle velden)

Locatie
- Deze map is <projectroot>\scripts\scraper\ (bij Rob: C:\Rob\Beplantingswijzer\Plantwijs\scripts\scraper).
- Alle paden worden door de scripts zelf afgeleid uit hun eigen locatie. Je hoeft
  niets te wijzigen als het project ergens anders staat.

Wat doet dit?
- treeebb_scraper_allfields.py maakt een CSV met ALLE "kenmerken/filters" per TreeEbb plant.
  Gebaseerd op het 'plant-specs' blok van de soortpagina's op ebben.nl.
  Beschrijvingstekst en foto's worden overgeslagen.
- verrijk_treeebb_met_sl2020.py voegt daarna de kolommen nsr_status en status_nl toe
  (inheems / ingeburgerd / exoot) op basis van de Standaardlijst Flora NL 2020.

Starten met 1 klik
1) Installeer Python (3.10+), of zorg dat de venv van het project bestaat (<projectroot>\.venv).
2) Dubbelklik: START_TreeEbb_Scrape.bat
   De .bat gebruikt de venv van het project als die er is, en installeert eerst
   requirements.txt uit deze map (requests, beautifulsoup4, lxml, selenium, webdriver-manager).

Output
- <projectroot>\data\treeebb_planten_allfields.csv
- URL-cache: <projectroot>\data\treeebb_urls.txt

Verrijken met SL2020 (stap 2, vanuit de projectroot)
- .venv\Scripts\python.exe scripts\scraper\verrijk_treeebb_met_sl2020.py
- Leest data\SL2020 Checklist Flora NL.xlsx (valt terug op de map boven het project).
- Overschrijft data\treeebb_planten_allfields.csv en zet een .bak ernaast.

Optioneel normaliseren (stap 3, vanuit de projectroot)
- .venv\Scripts\python.exe scripts\normalize_treeebb_csv.py
- Maakt multi-waardes consistent (" / " als scheidingsteken) en zet een .bak ernaast.

Testen (optioneel)
- 50 planten: python treeebb_scraper_allfields.py --max 50
- Browser zichtbaar: python treeebb_scraper_allfields.py --no-headless
- URL's opnieuw ophalen: python treeebb_scraper_allfields.py --fresh
- Ander outputbestand: python treeebb_scraper_allfields.py --out ..\..\data\test.csv

Let op
- De scraper haalt ~1650 pagina's op met een pauze van 0,5 s; reken op ruim een half uur.
- TreeEbb_Scraper_AllFields_v2.zip is de oorspronkelijke distributie van deze scraper
  en wordt door niets gebruikt; hij staat er alleen als historische kopie.

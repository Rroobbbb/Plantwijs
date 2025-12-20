# 📦 INSTALLATIE INSTRUCTIES - Kennisbibliotheek v2

## 🎯 Wat je hebt gedownload

Je hebt 4 ZIP/TAR.GZ bestanden gedownload:

1. **inheemse_soorten_64.tar.gz** - Alle 64 inheemse soorten (KLAAR!)
2. **kennislagen_voorbeelden.tar.gz** - NSN, Bodem, Gt voorbeelden + templates
3. **advies_bibliotheken.tar.gz** - Principes en voorbeeld soorten
4. **generator_script.tar.gz** - Het generator script

---

## 📁 Waar moet alles naartoe?

```
Plantwijs/
└── kennisbibliotheek_v2/            ← Maak deze folder eerst!
    ├── lagen/
    │   ├── nsn/                      ← Pak kennislagen_voorbeelden.tar.gz uit
    │   ├── bodem/                    ← Komt uit zelfde bestand
    │   ├── gt/                       ← Komt uit zelfde bestand
    │   └── fgr/                      ← (Leeg voor nu)
    │
    ├── advies/
    │   ├── soorten/
    │   │   └── inheems/              ← Pak inheemse_soorten_64.tar.gz uit
    │   ├── principes/                ← Pak advies_bibliotheken.tar.gz uit
    │   └── soorten_voorbeelden/      ← Komt uit zelfde bestand
    │
    └── scripts/
        └── generate_advies.py        ← Pak generator_script.tar.gz uit
```

---

## 🚀 STAP-VOOR-STAP INSTALLATIE

### STAP 1: Maak kennisbibliotheek_v2 folder

**In je Plantwijs folder, maak deze structuur:**

#### Windows (via Verkenner):
1. Open je Plantwijs folder
2. Rechtermuisklik → Nieuwe map → `kennisbibliotheek_v2`
3. Ga IN die folder
4. Maak deze submappen:
   - `lagen`
   - `advies`
   - `scripts`
5. Ga IN `lagen`, maak:
   - `nsn`
   - `bodem`
   - `gt`
   - `fgr`
6. Ga IN `advies`, maak:
   - `soorten`
   - `principes`
7. Ga IN `soorten`, maak:
   - `inheems`

#### Mac/Linux (via terminal):
```bash
cd /pad/naar/Plantwijs
mkdir -p kennisbibliotheek_v2/{lagen/{nsn,bodem,gt,fgr},advies/{soorten/inheems,principes},scripts}
```

---

### STAP 2: Pak bestanden uit

#### Bestand 1: inheemse_soorten_64.tar.gz

**Pak uit IN: `kennisbibliotheek_v2/advies/soorten/`**

##### Windows:
1. Hernoem `.tar.gz` naar `.zip`
2. Rechtermuisklik → Uitpakken naar...
3. Selecteer `Plantwijs/kennisbibliotheek_v2/advies/soorten/`
4. Je krijgt nu `soorten/inheemse_soorten_compleet/`
5. **HERNOEM** `inheemse_soorten_compleet` naar `inheems`

##### Mac/Linux:
```bash
cd Plantwijs/kennisbibliotheek_v2/advies/soorten/
tar -xzf ~/Downloads/inheemse_soorten_64.tar.gz
mv inheemse_soorten_compleet inheems
```

**✅ Check:** Je zou nu moeten hebben:
```
kennisbibliotheek_v2/advies/soorten/inheems/
├── zomereik.yaml
├── ruwe_berk.yaml
├── haagbeuk.yaml
└── ... (61 meer)
```

---

#### Bestand 2: kennislagen_voorbeelden.tar.gz

**Pak uit IN: `kennisbibliotheek_v2/`**

##### Windows:
1. Hernoem `.tar.gz` naar `.zip`
2. Uitpakken naar `Plantwijs/kennisbibliotheek_v2/`
3. Je krijgt nu `kennisbibliotheek_v2/kennislagen_compleet/`
4. **VERPLAATS** de inhoud:
   - `kennislagen_compleet/nsn/*` → `lagen/nsn/`
   - `kennislagen_compleet/bodem/*` → `lagen/bodem/`
   - `kennislagen_compleet/gt/*` → `lagen/gt/`
5. **VERWIJDER** lege `kennislagen_compleet` folder

##### Mac/Linux:
```bash
cd Plantwijs/kennisbibliotheek_v2/
tar -xzf ~/Downloads/kennislagen_voorbeelden.tar.gz
mv kennislagen_compleet/nsn/* lagen/nsn/
mv kennislagen_compleet/bodem/* lagen/bodem/
mv kennislagen_compleet/gt/* lagen/gt/
rm -rf kennislagen_compleet
```

**✅ Check:**
```
kennisbibliotheek_v2/lagen/
├── nsn/
│   ├── _template.yaml
│   └── dekzandrug.yaml
├── bodem/
│   ├── _template.yaml
│   └── podzolgrond.yaml
└── gt/
    ├── _template.yaml
    ├── gt_vii.yaml
    └── gt_iii.yaml
```

---

#### Bestand 3: advies_bibliotheken.tar.gz

**Pak uit IN: `kennisbibliotheek_v2/advies/`**

##### Windows:
1. Hernoem `.tar.gz` naar `.zip`
2. Uitpakken naar `Plantwijs/kennisbibliotheek_v2/advies/`
3. Je krijgt `advies/advies_bibliotheken/`
4. **VERPLAATS**:
   - `advies_bibliotheken/principes/*` → `principes/`
   - `advies_bibliotheken/soorten_voorbeelden/*` → `soorten/` (niet in inheems!)
5. **VERWIJDER** `advies_bibliotheken` folder

##### Mac/Linux:
```bash
cd Plantwijs/kennisbibliotheek_v2/advies/
tar -xzf ~/Downloads/advies_bibliotheken.tar.gz
mv advies_bibliotheken/principes/* principes/
mv advies_bibliotheken/soorten_voorbeelden/* soorten/
rm -rf advies_bibliotheken
```

**✅ Check:**
```
kennisbibliotheek_v2/advies/
├── principes/
│   ├── organische_stof_opbouw.yaml
│   └── water_vasthouden.yaml
└── soorten/
    ├── inheems/            (64 bestanden)
    └── zomereik.yaml       (voorbeeld buiten inheems)
```

---

#### Bestand 4: generator_script.tar.gz

**Pak uit IN: `kennisbibliotheek_v2/scripts/`**

##### Windows:
1. Hernoem `.tar.gz` naar `.zip`
2. Uitpakken naar `Plantwijs/kennisbibliotheek_v2/scripts/`
3. Je krijgt `scripts/generator_script/generate_advies.py`
4. **VERPLAATS** `generate_advies.py` naar `scripts/`
5. **VERWIJDER** `generator_script` folder

##### Mac/Linux:
```bash
cd Plantwijs/kennisbibliotheek_v2/scripts/
tar -xzf ~/Downloads/generator_script.tar.gz
mv generator_script/generate_advies.py .
rm -rf generator_script
```

**✅ Check:**
```
kennisbibliotheek_v2/scripts/
└── generate_advies.py
```

---

## ✅ FINALE CHECK

**Je zou nu moeten hebben:**

```
Plantwijs/
└── kennisbibliotheek_v2/
    ├── lagen/
    │   ├── nsn/
    │   │   ├── _template.yaml
    │   │   └── dekzandrug.yaml
    │   ├── bodem/
    │   │   ├── _template.yaml
    │   │   └── podzolgrond.yaml
    │   ├── gt/
    │   │   ├── _template.yaml
    │   │   ├── gt_vii.yaml
    │   │   └── gt_iii.yaml
    │   └── fgr/
    │       (leeg voor nu)
    │
    ├── advies/
    │   ├── soorten/
    │   │   ├── inheems/
    │   │   │   ├── zomereik.yaml
    │   │   │   ├── ruwe_berk.yaml
    │   │   │   └── ... (62 meer)
    │   │   └── zomereik.yaml (voorbeeld)
    │   ├── principes/
    │   │   ├── organische_stof_opbouw.yaml
    │   │   └── water_vasthouden.yaml
    │   └── templates/
    │       (leeg voor nu)
    │
    └── scripts/
        └── generate_advies.py
```

**Tel de bestanden:**
- ✅ 64 soorten in `advies/soorten/inheems/`
- ✅ 3 templates in `lagen/`
- ✅ 3 voorbeelden in `lagen/`
- ✅ 2 principes in `advies/principes/`
- ✅ 1 generator script

---

## 🧪 TEST DE GENERATOR

**Open terminal/cmd in Plantwijs folder:**

```bash
cd kennisbibliotheek_v2/scripts

python generate_advies.py --nsn dekzandrug --bodem podzolgrond --gt gt_vii --format markdown
```

**Zie je errors?** Probeer:
```bash
python3 generate_advies.py --nsn dekzandrug --bodem podzolgrond --gt gt_vii --format markdown
```

**✅ Als het werkt zie je:**
```
======================================================================
Advies Generator - Beplantingswijzer
======================================================================

📂 Laden kennislagen...
   ✅ NSN: Dekzandrug
   ✅ Bodem: Podzolgrond (haarpodzol)
   ✅ Gt: GWT VII - Zeer droog

📚 Laden advies-bibliotheken...
   Soorten: 65
   Principes: 2

🔍 Analyseren context...
   Reliëf: hoog
   Bodem textuur: zand
   Water regime: zeer_droog
   Primaire uitdagingen: 2

🌱 Selecteren geschikte soorten...
   pioniers: X
   hoofdbomen: Y
   ...

# Uw Locatie: Advies voor Erfbeplanting

...
```

**Sla advies op:**
```bash
python generate_advies.py --nsn dekzandrug --bodem podzolgrond --gt gt_vii --format json --output test_advies.json
```

---

## 🎉 KLAAR!

Je hebt nu:
- ✅ 64 inheemse soorten volledig uitgewerkt
- ✅ Voorbeelden van NSN, Bodem, Gt kennislagen
- ✅ Templates om nieuwe items toe te voegen
- ✅ Werkende generator
- ✅ Basis advies-bibliotheken

**Volgende stappen:**
1. Test de generator met verschillende combinaties
2. Voeg meer kennislaag items toe (gebruik templates!)
3. Voeg meer principes toe
4. Integreer in je API

---

## 🆘 Hulp Nodig?

**Generator werkt niet:**
- Check of PyYAML geïnstalleerd is: `pip install pyyaml`
- Check of bestanden op juiste plek staan (zie structuur boven)

**Bestanden op verkeerde plek:**
- Volg de structuur hierboven EXACT
- Vooral belangrijk: `inheems/` subfolder in `advies/soorten/`

**Error "bestand niet gevonden":**
- Gebruik exact deze codes: `dekzandrug`, `podzolgrond`, `gt_vii`
- Hoofdlettergevoelig!

# Beplantingswijzer Kennisbibliotheek v2.0
## Gelaagd Systeem met Advies-Generator

## 🎯 Kernprincipe

**Scheiding van Kennis en Advies**

De kennisbibliotheek is opgesplitst in **kennislagen** (feiten) en **advies** (combinatie van feiten):

```
KENNIS (feiten)              ADVIES (synthese)
├── NSN (landvorm)          ─┐
├── Bodem (textuur, pH)     ─┤
├── Gt (water)              ─┼──→ Generator → Erfadvies
└── FGR (regio)             ─┘                (soorten + praktijk)
```

## 📁 Structuur

```
kennisbibliotheek_v2/
│
├── lagen/                          # Kennislagen (feiten)
│   ├── nsn/                        # Geomorfologie/landvorm
│   │   ├── _template.yaml
│   │   ├── bknsn_dz1.yaml
│   │   └── ...
│   │
│   ├── bodem/                      # Bodemtype
│   │   ├── _template.yaml
│   │   ├── podzol.yaml
│   │   ├── klei.yaml
│   │   └── ...
│   │
│   ├── gt/                         # Grondwatertrap
│   │   ├── _template.yaml
│   │   ├── gt_i.yaml
│   │   ├── gt_vii.yaml
│   │   └── ...
│   │
│   └── fgr/                        # Fysisch Geografische Regio
│       ├── _template.yaml
│       └── ...
│
├── advies/                         # Advies-bibliotheken
│   ├── principes/                  # Ontwerpprincipes (herbruikbaar)
│   │   ├── organische_stof_opbouw.yaml
│   │   ├── water_vasthouden.yaml
│   │   ├── windkering.yaml
│   │   └── ...
│   │
│   ├── soorten/                    # Soorten-database
│   │   ├── zomereik.yaml
│   │   ├── grove_den.yaml
│   │   ├── ruwe_berk.yaml
│   │   └── ...
│   │
│   └── templates/                  # Tekst-templates
│       └── ...
│
└── scripts/
    ├── generate_advies.py          # HOOFDSCRIPT: combineert alles
    └── merge_layers.py             # Voegt lagen samen (optioneel)
```

## 🔄 Hoe het Werkt

### Stap 1: Kennislagen apart beheren

Elk item in elke laag focust op **één aspect**:

**NSN (bknsn_dz1.yaml)** - Alleen landvorm:
```yaml
landvorm:
  reliëf:
    hoogtebereik: "5-25m boven NAP"
    vorm: "Golvend"
    helling: "1-5%"
  
  betekenis_voor_erfbeplanting:
    reliëf_implicaties: |
      Hogere ligging = snellere afwatering.
      Benut microreliëf: top droger dan flanken.
```

**Bodem (podzol.yaml)** - Alleen bodem:
```yaml
chemie:
  pH:
    range: "4.0-5.5"
    classificatie: "Zuur"
  
  voedselrijkdom:
    algemeen: "Arm"

betekenis_voor_erfbeplanting:
  bodem_implicaties: |
    Zure, voedselarme grond. Kies soorten die tegen 
    lage pH kunnen (eik, berk, rododendron).
```

**Gt (gt_vii.yaml)** - Alleen water:
```yaml
grondwaterstand:
  GHG: "120-180cm onder maaiveld"
  GLG: ">180cm onder maaiveld"

betekenis_voor_erfbeplanting:
  water_implicaties: |
    Grondwater speelt geen rol. Plant is afhankelijk 
    van regen. Droogte in zomer is groot risico.
```

### Stap 2: Generator combineert lagen

```bash
python scripts/generate_advies.py \
  --nsn bknsn_dz1 \
  --bodem podzol \
  --gt gt_vii \
  --output advies.json
```

**Wat het script doet:**

1. **Laadt** alle kennislagen
2. **Analyseert** context:
   - "Hoog + droog + arm = EXTREME DROOGTE"
3. **Selecteert** relevante principes:
   - Organische stof opbouw ✅
   - Water vasthouden ✅
4. **Filtert** soorten:
   - `droogte_tolerantie: hoog` ✅
   - `pH_voorkeur: zuur` ✅
5. **Genereert** geïntegreerd advies

**Output:**
```json
{
  "context": {
    "water_regime": "zeer_droog",
    "bodem_ph": "zuur",
    "primaire_uitdagingen": [
      {
        "type": "droogte",
        "ernst": "zeer_hoog",
        "omschrijving": "Extreme droogte door zand + diep grondwater"
      }
    ]
  },
  "principes": [
    {
      "naam": "Organische stof opbouw",
      "relevantie_score": 5,
      ...
    }
  ],
  "soorten": {
    "pioniers": [
      {"naam": "Grove den", "geschiktheid_score": 4},
      {"naam": "Ruwe berk", "geschiktheid_score": 3}
    ],
    "hoofdbomen": [
      {"naam": "Zomereik", "geschiktheid_score": 3},
      ...
    ]
  },
  "rapporttekst": "# Uw Locatie: Advies ...\n\n..."
}
```

## 🚀 Aan de Slag

### 1. Installeer dependencies

```bash
pip install pyyaml
```

### 2. Vul kennislagen in

Start met de templates en vul in:

```bash
# Kopieer template
cd lagen/nsn
cp _template.yaml bknsn_dz1.yaml

# Bewerk (vul alleen NSN-specifieke info in!)
nano bknsn_dz1.yaml
```

**Belangrijk:** Elk bestand focust op **één aspect**:
- NSN = alleen landvorm
- Bodem = alleen bodemtype
- Gt = alleen water

### 3. Bouw advies-bibliotheken

Maak soorten en principes:

```bash
cd advies/soorten
cp zomereik.yaml winterlinde.yaml
# Bewerk voor winterlinde
```

### 4. Test de generator

```bash
python scripts/generate_advies.py \
  --nsn bknsn_dz1 \
  --bodem podzol \
  --gt gt_vii \
  --format markdown
```

## 📝 Wat Hoort Waar?

### ✅ In NSN.yaml (geomorfologie)
- Ontstaansgeschiedenis
- Reliëf (hoogte, vorm, helling)
- Positie in landschap (hoog/laag)
- Afwatering door reliëf
- Erosierisico

### ❌ NIET in NSN.yaml
- Bodemtype (→ bodem.yaml)
- Grondwaterstand (→ gt.yaml)
- Concrete soorten (→ advies/soorten/)
- pH, voedselrijkdom (→ bodem.yaml)

### ✅ In Bodem.yaml
- Textuur (zand/klei/veen)
- pH
- Voedselrijkdom
- Doorlatendheid
- Bewortelbaarheid

### ❌ NIET in Bodem.yaml
- Grondwaterstand (→ gt.yaml)
- Reliëf (→ nsn.yaml)
- Concrete soorten (→ advies/soorten/)

### ✅ In Gt.yaml (grondwatertrap)
- GHG/GLG
- Fluctuatie
- Droogtegevoeligheid
- Drainage

### ❌ NIET in Gt.yaml
- Bodemtype (→ bodem.yaml)
- Reliëf (→ nsn.yaml)
- Concrete soorten (→ advies/soorten/)

### ✅ In advies/soorten/
- Standplaatseisen (droogte, pH, etc.)
- Groeikenmerken
- Ecologische waarde
- Praktische aspecten

### ✅ In advies/principes/
- Ontwerpprincipes (herbruikbaar!)
- Wanneer toepassen
- Hoe toepassen
- Effect

## 🎨 Voorbeeld Workflow

### Scenario: Nieuwe locatie

```python
# API krijgt:
lat, lon = 52.1234, 5.6789

# Haalt op van kaartlagen:
nsn_code = "bknsn_dz1"  # Dekzandrug
bodem_code = "podzol"   # Haarpodzol
gt_code = "gt_vii"      # Zeer droog
fgr_code = "heuvelland" # Oost-Nederland

# Roept generator aan:
advies = generate_advies(
    nsn=nsn_code,
    bodem=bodem_code,
    gt=gt_code,
    fgr=fgr_code
)

# Genereert PDF met:
- Context: "Droge dekzandrug met zure podzol"
- Uitdagingen: "Extreme droogte, voedselarm"
- Principes: "Organische stof, mulchen"
- Soorten: "Den, berk, eik, linde"
- Rapporttekst: Geïntegreerd verhaal
```

## 💡 Voordelen van dit Systeem

### ✅ DRY (Don't Repeat Yourself)
- Elke feit maar 1x opschrijven
- "Droogte-advies" staat in principe, niet in elk NSN-item
- "Zomereik kenmerken" staat in soort, niet in elk advies

### ✅ Onderhoudbaar
- Wijziging in bodem-template = alle bodemitems consistent
- Nieuwe soort toevoegen = 1 bestand
- Nieuw principe = meteen bruikbaar voor alle combinaties

### ✅ Schaalbaar
- 50 NSN × 20 bodems × 8 Gt = 8000 combinaties
- Maar je hoeft maar 78 bestanden te onderhouden (50+20+8)!
- Plus herbruikbare principes en soorten

### ✅ Flexibel
- Makkelijk nieuwe lagen toevoegen (bijv. klimaat)
- Principes zijn herbruikbaar tussen lagen
- Generator kan uitbreiden met nieuwe logica

## 🔧 Geavanceerd Gebruik

### Eigen filtercriteria toevoegen

In `generate_advies.py`:

```python
def filter_soorten(soorten, context):
    # Voeg eigen logica toe
    if context['reliëf'] == 'hoog' and context['wind_exposure'] == 'hoog':
        # Filter op wind-tolerantie
        ...
```

### Nieuwe kennislaag toevoegen

1. Maak directory: `lagen/klimaat/`
2. Maak template: `lagen/klimaat/_template.yaml`
3. Vul items in
4. Update generator om klimaat mee te nemen

### Weging aanpassen

In `select_principes()`:

```python
# Geef droogte hogere prioriteit
if uitdaging_type == 'droogte':
    relevantie_score += 3  # Was 2
```

## 📊 Statistieken

**Huidige opzet:**
- Kennislagen: 78 items (50 NSN + 20 bodem + 8 Gt)
- Principes: ~15 herbruikbare principes
- Soorten: ~50 soorten in database
- Mogelijke combinaties: 8.000+

**Onderhoudslast:**
- Was: 8.000 advies-combinaties handmatig maken
- Nu: 143 items (78+15+50) onderhouden
- **Reductie: 98%!**

## 🎯 Prioritering

### Week 1-2: Basis opzet
- [ ] Vul 10 meest voorkomende NSN items in
- [ ] Vul 5 meest voorkomende bodemtypen in
- [ ] Vul alle 8 Gt's in
- [ ] Test generator

### Week 3-4: Advies-bibliotheken
- [ ] Maak 10 basis ontwerpprincipes
- [ ] Maak database met 20 belangrijkste soorten
- [ ] Test verschillende combinaties

### Week 5-6: Uitbreiden
- [ ] Vul alle 54 NSN items in (basis niveau)
- [ ] Vul alle 20 bodemtypen in
- [ ] Voeg 30 extra soorten toe

### Week 7+: Verfijnen
- [ ] Verbeter filtering-logica
- [ ] Voeg FGR laag toe
- [ ] Maak klimaat-laag (optioneel)
- [ ] Expert review

## 📖 Documentatie

- **Kennislagen**: Zie templates in `lagen/*/`
- **Advies**: Zie voorbeelden in `advies/`
- **Generator**: Zie `scripts/generate_advies.py`

## ❓ FAQ

**Q: Moet ik nu alles opnieuw doen?**
A: Nee! Je huidige NSN.yaml kun je splitsen en hergebruiken.

**Q: Hoeveel werk is een nieuw NSN-item?**
A: 15-30 min (want je hoeft alleen landvorm in te vullen)

**Q: Hoe werkt dit met mijn API?**
A: Je API roept generate_advies.py aan met de codes die je van PDOK krijgt.

**Q: Kan ik de oude structuur blijven gebruiken?**
A: Ja, maar dan mis je de voordelen van dit systeem (herbruikbaarheid, onderhoudbaarheid).

---

**Veel succes! Dit is een professioneel systeem dat schaalt. 🚀**

import yaml
from collections import OrderedDict

def represent_ordereddict(dumper, data):
    return dumper.represent_mapping('tag:yaml.org,2002:map', data.items())

yaml.add_representer(OrderedDict, represent_ordereddict)

# Echte gedetailleerde data per bodemtype
detailed_data = {
    "loss.yaml": {
        "textuur": {
            "hoofdtextuur": "Löss (zeer fijn silt)",
            "korrelgrootte": "Zeer fijn",
            "korrelgrootte_detail": "2-50μm (silt fractie)",
            "samenstelling": {
                "zand_percentage": "5-15%",
                "silt_percentage": "70-85%",
                "klei_percentage": "5-20%",
                "organische_stof": "3-6%"
            },
            "textuurklasse": "Silt loam",
            "beschrijving": "Zeer fijn, zacht poeder dat bij nat kleverig wordt. Optimale textuur voor plantengroei."
        },
        "fysisch_complete": {
            "doorlatendheid": {
                "verticaal": "Matig",
                "K_waarde": "10-50 cm/dag",
                "beschrijving": "Gebalanceerde drainage - niet te snel, niet te langzaam. Ideaal."
            },
            "vochtvasthoudend_vermogen": {
                "capaciteit": "Zeer hoog",
                "beschikbaar_water": "200-300 mm per meter",
                "beschrijving": "Fijne deeltjes + organische stof = excellent vochtvasthouden."
            },
            "bewortelbaarheid": {
                "diepte": "Zeer diep (>200cm)",
                "belemmeringen": "Geen",
                "beschrijving": "Homogeen, rijkmaar, diep profiel. Perfect bewortelbaar."
            },
            "draagkracht": {
                "droog": "Hoog",
                "nat": "Matig (kan glad zijn)",
                "bewerkbaarheid": "Goed, maar niet bij te nat (smeren)"
            }
        },
        "profielopbouw_complete": {
            "beschrijving": "Homogeen lösspakket, windafzetting uit ijstijd. Kan tot 10m+ dik zijn.",
            "horizonten": [
                {"horizont": "Ap (bouwvoor)", "dikte": "30cm", "kenmerken": "Bewerkt, humeus"},
                {"horizont": "A", "dikte": "30-50cm", "kenmerken": "Donker, rijk aan organische stof"},
                {"horizont": "C (löss)", "dikte": ">500cm", "kenmerken": "Geel-bruin, homogeen silt"}
            ]
        },
        "plantmogelijkheden_lijst": [
            "Vruchtbomen - IDEAAL (appel, peer, pruim, kers)",
            "Walnoot - uniek mogelijk in NL (warmte + voeding)",
            "Tamme kastanje - Zuid-Limburg specialiteit",
            "Haagbeuk - prachtige groei",
            "Beuk, eik - topkwaliteit hout",
            "Hazelaar, linde - uitstekend",
            "Vrijwel ALLES groeit hier perfect"
        ],
        "aandachtspunten_lijst": [
            "Wind op plateaus - mulch tegen uitdroging",
            "Erosie op hellingen - plant dwars, mulch, bodembedekkers",
            "Niet bewerken bij nat (smeren, structuurschade)",
            "Geniet van deze topbodem - beste van Nederland!"
        ]
    },
    
    "veengrond.yaml": {
        "textuur": {
            "hoofdtextuur": "Veen (organisch)",
            "samenstelling": {
                "organische_stof": ">30% (definitie veen)",
                "klei_deklaag": "0-30cm (vaak aanwezig)",
                "veensoort": "Riet-, zegge- of veenmosveen"
            },
            "beschrijving": "Donkerbruin tot zwart, sponsachtig materiaal. Zeer licht en poreus."
        },
        "fysisch_complete": {
            "doorlatendheid": {
                "verticaal": "Zeer laag",
                "beschrijving": "Water stagneert. Veen verzadigd met water."
            },
            "vochtvasthoudend_vermogen": {
                "capaciteit": "Extreem hoog",
                "beschikbaar_water": "Altijd vochtig (verzadigd)",
                "beschrijving": "Veen is een spons - houdt enorm veel water vast."
            },
            "bewortelbaarheid": {
                "diepte": "Matig (50-80cm)",
                "belemmeringen": "Grondwater, zakkende bodem",
                "beschrijving": "Nat en zakkend maakt beworteling lastig."
            },
            "draagkracht": {
                "droog": "Hoog (maar zakt bij belasten)",
                "nat": "ZEER laag (zompig, instabiel)",
                "bewerkbaarheid": "Zeer slecht - NOOIT betreden bij nat"
            },
            "verdichting": {
                "gevoeligheid": "Zeer hoog",
                "herstel": "NOOIT (blijvende schade)"
            }
        },
        "profielopbouw_complete": {
            "beschrijving": "Veenpakket met vaak kleidek. Zakkend door oxidatie en compactie.",
            "horizonten": [
                {"horizont": "Kleidek (optioneel)", "dikte": "0-30cm", "kenmerken": "Kleilaag bovenop"},
                {"horizont": "O (veen)", "dikte": "50-200cm+", "kenmerken": "Donker, organisch, nat"}
            ]
        },
        "plantmogelijkheden_lijst": [
            "Els - BESTE keuze (stikstoffixerend + nat-tolerant)",
            "Schietwilg - houdt van natte voeten",
            "Grauwe wilg - perfect voor veen",
            "Zwarte populier - snel groeiend op nat",
            "Gelderse roos - struik voor natte plekken",
            "Moeras accepteren OF intensief draineren"
        ],
        "aandachtspunten_lijst": [
            "Zakkende bodem - blijft zakken (5-10mm/jaar)",
            "Bij drainage: oxidatie veen (CO2-uitstoot + extra zakking)",
            "NOOIT betreden bij nat - blijvende schade",
            "Peilbehoud cruciaal - te droog = oxidatie",
            "Moeras accepteren = minste werk en beste voor klimaat"
        ]
    },
    
    "keileem.yaml": {
        "textuur": {
            "hoofdtextuur": "Keileem (glaciale afzetting)",
            "samenstelling": {
                "klei_percentage": "20-40%",
                "zand_percentage": "40-60%",
                "grind_stenen": "5-15% (karakteristiek!)",
                "organische_stof": "<1%"
            },
            "beschrijving": "Zeer compacte mix van klei, zand en stenen. Keihard bij droog."
        },
        "fysisch_complete": {
            "doorlatendheid": {
                "verticaal": "Vrijwel nul (ondoorlatend!)",
                "K_waarde": "<0.1 cm/dag",
                "beschrijving": "PROBLEEM: Water kan er niet doorheen. Totale stagnatie."
            },
            "vochtvasthoudend_vermogen": {
                "capaciteit": "Hoog (maar water staat)",
                "beschrijving": "Houdt water vast maar stagneert boven keileem."
            },
            "bewortelbaarheid": {
                "diepte": "Tot keileem (vaak 40-120cm)",
                "belemmeringen": "Keileem is niet te penetreren",
                "beschrijving": "Wortels stoppen bij keileem. Zeer dichte laag."
            },
            "draagkracht": {
                "droog": "Zeer hoog (keihard)",
                "nat": "ZEER laag (smeren, modder)",
                "bewerkbaarheid": "Zeer slecht - NOOIT bewerken bij nat"
            },
            "verdichting": {
                "gevoeligheid": "Extreem hoog",
                "herstel": "NOOIT (blijvende schade)"
            }
        },
        "profielopbouw_complete": {
            "beschrijving": "Keileem laag op 40-120cm diepte blokkeert drainage compleet.",
            "horizonten": [
                {"horizont": "A/C", "dikte": "40-120cm", "kenmerken": "Zand of klei bovenop"},
                {"horizont": "Keileem", "dikte": "50-200cm+", "kenmerken": "Zeer compact, stenen, ondoorlatend"}
            ]
        },
        "plantmogelijkheden_lijst": [
            "Met drainage: normaal assortiment mogelijk",
            "Zonder drainage: Alleen nat-tolerant (els, wilg)",
            "Ondiepe wortelaars: Berk, lijsterbes (bereiken keileem niet)",
            "Vermijd diepwortelaars zonder drainage",
            "Beste advies: Drainage aanleggen OF nat accepteren"
        ],
        "aandachtspunten_lijst": [
            "PROBLEEM-BODEM: water stagneert structureel boven keileem",
            "Drainage is meestal essentieel voor normale soorten",
            "OF accepteer nat en plant els/wilg",
            "NOOIT betreden bij nat - blijvende puinzooi",
            "Overweeg professionele drainage bij ernstige stagnatie"
        ]
    }
}

# Past data toe
for filename, data in detailed_data.items():
    with open(filename, 'r') as f:
        bodem = yaml.safe_load(f)
    
    # Update textuur
    if "textuur" in data:
        for key, value in data["textuur"].items():
            if key not in bodem.get("textuur", {}):
                if "textuur" not in bodem:
                    bodem["textuur"] = OrderedDict()
                bodem["textuur"][key] = value
    
    # Update fysisch
    if "fysisch_complete" in data:
        if "fysisch" not in bodem:
            bodem["fysisch"] = OrderedDict()
        for key, value in data["fysisch_complete"].items():
            bodem["fysisch"][key] = value
    
    # Update profielopbouw
    if "profielopbouw_complete" in data:
        bodem["profielopbouw"] = data["profielopbouw_complete"]
    
    # Update plantmogelijkheden
    if "plantmogelijkheden_lijst" in data:
        if "plantmogelijkheden" not in bodem:
            bodem["plantmogelijkheden"] = OrderedDict()
        bodem["plantmogelijkheden"]["geschikte_soorten"] = data["plantmogelijkheden_lijst"]
    
    # Update aandachtspunten
    if "aandachtspunten_lijst" in data:
        if "betekenis_voor_erfbeplanting" not in bodem:
            bodem["betekenis_voor_erfbeplanting"] = OrderedDict()
        bodem["betekenis_voor_erfbeplanting"]["aandachtspunten"] = data["aandachtspunten_lijst"]
    
    # Schrijf terug
    with open(filename, 'w') as f:
        yaml.dump(bodem, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print(f"✅ Detailed upgrade: {filename}")

print("\n✅ 3 bodems volledig uitgebreid met gedetailleerde data")

"""Tests voor de contextmatcher (plantwijs/services/context.py).

De casussen komen uit content/README.md: de volgorde in het YAML-bestand is
betekenisvol, `match_exact` wint van een deeltekst-match, en alle 49
NSN-labels uit content/_inventaris_nsn.txt moeten op een echte entry
uitkomen — niet op de fallback.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plantwijs.services import context as ctx  # noqa: E402

INVENTARIS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "content", "_inventaris_nsn.txt",
)


def _nsn_labels() -> list[str]:
    """Lees de unieke Subtype_na-waarden uit het inventarisbestand (deel 1)."""
    labels: list[str] = []
    with open(INVENTARIS, encoding="utf-8") as f:
        for regel in f:
            if regel.startswith((" ", "#", "=", "-")):
                continue
            m = re.match(r"^(\S.{0,48}?)\s{2,}\d+\s\s+\S", regel.rstrip())
            if m and m.group(1) != "SUBTYPE_NA":
                labels.append(m.group(1).strip())
    return labels


# ───────────────────── basisgedrag
def test_yaml_is_geladen():
    assert set(ctx.CATEGORIEEN) <= set(ctx.categorieen())
    for cat in ctx.CATEGORIEEN:
        assert ctx.entries(cat), f"categorie {cat} is leeg"


@pytest.mark.parametrize("categorie", list(ctx.CATEGORIEEN))
def test_elke_categorie_heeft_fallback(categorie: str):
    fallbacks = [e for e in ctx.entries(categorie) if not e["match"] and not e["match_exact"]]
    assert len(fallbacks) == 1
    assert fallbacks[0]["id"] == "onbekend"


@pytest.mark.parametrize("waarde", [None, "", "   "])
def test_lege_waarde_geeft_fallback(waarde):
    assert ctx.entry_id("fgr", waarde) == "onbekend"
    assert ctx.entry_id("nsn", waarde) == "onbekend"
    d = ctx.beschrijf("bodem", waarde)
    assert d is not None and d["titel"]


def test_onbekende_categorie_geeft_none():
    assert ctx.beschrijf("bestaatniet", "van alles") is None
    assert ctx.entry_id("bestaatniet", "van alles") is None


def test_beschrijf_levert_contractvelden():
    d = ctx.beschrijf("fgr", "Hogere zandgronden")
    assert set(d) == {"titel", "ontstaan", "versterken", "bron"}
    assert d["titel"] == "Hogere zandgronden"
    assert isinstance(d["versterken"], list) and d["versterken"]
    assert d["bron"]


def test_hoofdletters_en_spaties_maken_niet_uit():
    assert ctx.entry_id("fgr", "  HOGERE   Zandgronden ") == "hogere_zandgronden"


# ───────────────────── matchvolgorde (casussen uit content/README.md)
def test_match_exact_wint_van_substring():
    # "es" staat onderaan in nsn en matcht als deeltekst op van alles; als
    # exacte waarde moet het tóch de es-entry zijn.
    assert ctx.entry_id("nsn", "Es") == "es"
    # En andersom: een langere waarde met "es" erin mag nooit bij es uitkomen.
    for waarde in ("Depressie", "Restgeul", "Veenrest", "Stuifzandduin (en bijbehorende vlaktes)"):
        assert ctx.entry_id("nsn", waarde) != "es", waarde


def test_pingoruine_staat_boven_depressie():
    # Het label bevat het woord "laagten", waar de depressie-entry ook op matcht.
    assert ctx.entry_id("nsn", ":ingoruines en periglaciale laagten") == "pingoruine"
    assert ctx.entry_id("nsn", "Pingoruines en periglaciale laagten") == "pingoruine"
    assert ctx.entry_id("nsn", "Depressie") == "depressie"


def test_specifieke_entries_boven_algemene():
    assert ctx.entry_id("nsn", "Ontgonnen hoogveen") == "ontgonnen_hoogveen"
    assert ctx.entry_id("nsn", "Hoogveen") == "hoogveen"
    assert ctx.entry_id("nsn", "Beekdal veen") == "beekdal_veen"
    assert ctx.entry_id("nsn", "Beekdal zand/leem") == "beekdal_zand_leem"
    assert ctx.entry_id("nsn", "Beekdal") == "beekdal"
    assert ctx.entry_id("nsn", "Zoetwatergetijdenafzetting") == "zoetwatergetijdenafzetting"
    assert ctx.entry_id("nsn", "Zoutwatergetijdenafzetting") == "zoutwatergetijdenafzetting"
    assert ctx.entry_id("nsn", "Water") == "water"


# ───────────────────── dekking
def test_inventaris_bevat_49_labels():
    assert len(_nsn_labels()) == 49


@pytest.mark.parametrize("label", _nsn_labels())
def test_elk_nsn_label_matcht_een_echte_entry(label: str):
    eid = ctx.entry_id("nsn", label)
    assert eid, label
    assert eid != "onbekend", f"{label} valt terug op de fallback"


def test_alle_categorieen_matchen_hun_eigen_waarden():
    assert ctx.entry_id("bodem", "zand") == "zand"
    assert ctx.entry_id("bodem", "Kalkrijke poldervaaggronden") == "klei"
    assert ctx.entry_id("vocht", "zeer nat") == "zeer_nat"
    assert ctx.entry_id("vocht", "nat") == "nat"
    assert ctx.entry_id("gmm", "Dekzandrug") == "dekzandrug"
    assert ctx.entry_id("fgr", "Rivierengebied") == "rivierengebied"


def test_entry_by_id():
    e = ctx.entry_by_id("fgr", "heuvelland")
    assert e and e["titel"] == "Heuvelland"
    assert ctx.entry_by_id("fgr", "bestaatniet") is None


# ───────────────────── cache
def test_cache_herlaadt_bij_gewijzigde_mtime(tmp_path, monkeypatch):
    bron = ctx.CONTEXT_YAML_PATH
    kopie = tmp_path / "context_descriptions.yaml"
    kopie.write_text(
        "categorieen:\n"
        "  fgr:\n"
        "    - id: alfa\n"
        "      match_exact: ['alfa']\n"
        "      match: []\n"
        "      titel: Alfa\n"
        "      ontstaan: x\n"
        "      versterken: [y]\n"
        "      bron: test\n"
        "    - id: onbekend\n"
        "      match_exact: []\n"
        "      match: []\n"
        "      titel: Onbekend\n"
        "      ontstaan: x\n"
        "      versterken: [y]\n"
        "      bron: test\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ctx, "CONTEXT_YAML_PATH", str(kopie))
    ctx.reload_cache()
    try:
        assert ctx.entry_id("fgr", "alfa") == "alfa"

        # bestand wijzigen (nieuwe mtime) → matcher pikt het zonder herstart op
        kopie.write_text(
            "categorieen:\n"
            "  fgr:\n"
            "    - id: beta\n"
            "      match_exact: ['alfa']\n"
            "      match: []\n"
            "      titel: Beta\n"
            "      ontstaan: x\n"
            "      versterken: [y]\n"
            "      bron: test\n",
            encoding="utf-8",
        )
        # expliciet een andere mtime zetten: de klokresolutie van het
        # bestandssysteem mag deze test niet flaky maken
        os.utime(kopie, (1_600_000_000, 1_600_000_000))
        assert ctx.entry_id("fgr", "alfa") == "beta"
    finally:
        monkeypatch.setattr(ctx, "CONTEXT_YAML_PATH", bron)
        ctx.reload_cache()

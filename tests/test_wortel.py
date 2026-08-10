"""Tests voor de wortelregels (plantwijs/services/wortel.py).

De verwachte uitkomsten zijn direct terug te lezen in
content/wortelbare_diepte.yaml (basisregels_bodem_gt + nsn_modifiers).
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plantwijs.services import wortel  # noqa: E402


def test_bestand_is_geladen():
    assert wortel._klassen()
    assert wortel._regels()
    assert wortel._klasse_orde()[0] == "zeer_beperkt"


# ───────────────────── basisscenario's
def test_nat_veen():
    r = wortel.bepaal(bodem="veen", gt_code="Ia")
    assert r["klasse"] == "zeer_beperkt"
    assert r["band_cm"] == "0-30"
    assert "natstress" in r["indicatie"]
    assert "zuurstofgebrek" in r["toelichting"]


def test_droog_zand():
    r = wortel.bepaal(bodem="zand", gt_code="VIIo")
    assert r["klasse"] == "zeer_goed"
    assert r["band_cm"] == "150-200"


def test_klei_gemiddeld():
    r = wortel.bepaal(bodem="klei", gt_code="IIIb")
    assert r["klasse"] == "matig"
    assert r["band_cm"] == "60-100"


def test_geen_input_geeft_none():
    assert wortel.bepaal() is None
    assert wortel.bepaal(bodem=None, gt_code=None) is None
    assert wortel.bepaal(bodem="", gt_code="   ") is None
    # alleen een NSN-label is te weinig: modifiers sturen alleen bij
    assert wortel.bepaal(nsn="Dekzandrug") is None


def test_contractvelden_en_disclaimer():
    r = wortel.bepaal(bodem="klei", gt_code="IIIb")
    assert set(r) == {"klasse", "band_cm", "indicatie", "toelichting"}
    assert "indicatief" in r["toelichting"].lower()


# ───────────────────── gedeeltelijke invoer
def test_alleen_gt_werkt():
    r = wortel.bepaal(gt_code="VIo")
    assert r is not None and r["klasse"] in wortel._klasse_orde()


def test_alleen_bodem_werkt():
    r = wortel.bepaal(bodem="zand")
    assert r is not None and "grondwatertrap onbekend" in r["toelichting"]


def test_combinatie_zonder_regel_valt_terug_op_gt():
    # leem komt niet voor in de Gt Ia/Ib-regels
    r = wortel.bepaal(bodem="leem", gt_code="Ia")
    assert r is not None
    assert "staat niet in de regels" in r["toelichting"]


# ───────────────────── tokenherkenning
def test_ruwe_bodemomschrijving_wordt_herkend():
    assert wortel.bodem_token("Kalkrijke poldervaaggronden, zware klei") == "zware_klei"
    assert wortel.bodem_token("zand") == "zand"
    assert wortel.bodem_token("Veen") == "veen"
    assert wortel.bodem_token("graniet") is None


@pytest.mark.parametrize("code,verwacht", [
    ("VIo", "vio"), ("vio", "vio"), ("IIIb", "iiib"), ("Ia", "ia"),
    ("VI", "vio"), ("VIII", "viiio"), ("IV", "ivu"),
])
def test_gt_codes_worden_herkend(code: str, verwacht: str):
    assert wortel.gt_token(code) == verwacht


def test_onzinnige_gt_code():
    assert wortel.gt_token("XYZ") is None
    assert wortel.gt_token(None) is None


# ───────────────────── NSN-modifiers
def test_modifier_verlaagt_klasse():
    zonder = wortel.bepaal(bodem="klei", gt_code="IIIb")
    met = wortel.bepaal(bodem="klei", gt_code="IIIb", nsn="Rivierkom")
    assert zonder["klasse"] == "matig"
    assert met["klasse"] == "beperkt"
    assert met["band_cm"] == "30-60"
    assert "natuurlijk systeem" in met["toelichting"]


def test_modifier_verhoogt_klasse():
    zonder = wortel.bepaal(bodem="zand", gt_code="IIIa")
    met = wortel.bepaal(bodem="zand", gt_code="IIIa", nsn="Stuifzandduin (en bijbehorende vlaktes)")
    assert zonder["klasse"] == "goed"
    assert met["klasse"] == "zeer_goed"


def test_modifier_rekt_de_band_op():
    zonder = wortel.bepaal(bodem="zand", gt_code="VIo")
    met = wortel.bepaal(bodem="zand", gt_code="VIo", nsn="Dekzandrug")
    assert zonder["band_cm"] == "150-200"
    assert met["band_cm"] == "160-220"          # min +10, max +20
    assert met["klasse"] == zonder["klasse"]


def test_modifier_op_bknsn_code():
    # De modifier-regels noemen BKNSN-codes; die mogen ook rechtstreeks binnenkomen.
    met = wortel.bepaal(bodem="klei", gt_code="IIIb", nsn="Rg2")
    assert met["klasse"] == "beperkt"


def test_zonder_relevante_nsn_geen_bijstelling():
    zonder = wortel.bepaal(bodem="klei", gt_code="IIIb")
    met = wortel.bepaal(bodem="klei", gt_code="IIIb", nsn="Antropogeen Element")
    assert zonder == met


def test_verschuiving_wordt_begrensd():
    # zeer_beperkt kan niet verder omlaag
    r = wortel.bepaal(bodem="veen", gt_code="Ia", nsn="Petgaten")
    assert r["klasse"] == "zeer_beperkt"
    assert r["band_cm"] == "0-30"

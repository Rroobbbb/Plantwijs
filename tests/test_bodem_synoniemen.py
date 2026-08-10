"""Bodemsynoniemen: TreeEbb-/Bodemkaart-termen → canonieke klassen.

De TreeEbb-kolom `grondsoorten` kent alleen samengestelde schrijfwijzen als
"lemige grond", "lichte klei" en "zavel"; de losse tokens "klei" en "leem"
komen er niet in voor. Zonder synoniementabel leverden klei- en leemlocaties
daardoor nul soorten op. Deze tests pinnen de tabel vast, de consistentie
tussen kaartzijde (`services.pdok`) en datasetzijde (`services.dataset`), en
dat elke canonieke klasse op de echte dataset soorten oplevert.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plantwijs.services import pdok  # noqa: E402
from plantwijs.services.dataset import (  # noqa: E402
    SOIL_SYNONYMS,
    _canon_soil_token,
    filter_standplaats,
    get_df,
)

KLASSEN = ("zand", "klei", "leem", "veen")


def _rij(naam: str, grondsoorten: str) -> dict:
    return {"naam": naam, "vocht": "", "grondsoorten": grondsoorten}


# ───────────────────── de synoniementabel zelf
@pytest.mark.parametrize("token, klasse", [
    ("zand", "zand"),
    ("zavel", "klei"),
    ("lichte klei", "klei"),
    ("zware klei", "klei"),
    ("lemige grond", "leem"),
    ("löss", "leem"),
    ("loess", "leem"),
    ("veen", "veen"),
])
def test_treeebb_token_krijgt_juiste_klasse(token: str, klasse: str):
    assert _canon_soil_token(token) == klasse


def test_synoniemen_consistent_tussen_dataset_en_bodemkaart():
    """Elk synoniem levert op beide plekken dezelfde canonieke klasse op."""
    for klasse, synoniemen in SOIL_SYNONYMS.items():
        for s in synoniemen:
            assert _canon_soil_token(s) == klasse, s
            assert pdok._soil_from_text(s) == klasse, s


# ───────────────────── filtering op een minidataset
def test_alle_grondsoorten_telt_bij_elke_klasse():
    df = pd.DataFrame([_rij("Alleplant", "alle grondsoorten")])
    for klasse in KLASSEN:
        assert len(filter_standplaats(df, bodem=[klasse])) == 1, klasse


def test_lemige_grond_matcht_leem_en_niets_anders():
    """Regressie: rijen met alléén "lemige grond" vielen buiten elke klasse."""
    df = pd.DataFrame([_rij("Leemplant", "lemige grond")])
    for klasse in KLASSEN:
        n = len(filter_standplaats(df, bodem=[klasse]))
        assert n == (1 if klasse == "leem" else 0), klasse


# ───────────────────── de echte dataset
@pytest.mark.parametrize("klasse", KLASSEN)
def test_echte_dataset_heeft_soorten_voor_elke_klasse(klasse: str):
    """klei en leem gaven ooit 0 soorten; elke klasse moet er nu opleveren."""
    df = get_df()
    assert len(filter_standplaats(df, bodem=[klasse])) > 0

"""Tests voor de Nederlandse namen uit SL2020 (plantwijs/services/dataset.py)."""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plantwijs.main import app  # noqa: E402
from plantwijs.services import dataset  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def df():
    return dataset.get_df()


# ───────────────────── bronbestand + kolommen
def test_sl2020_bestand_staat_in_data():
    assert os.path.exists(dataset.SL2020_XLSX), dataset.SL2020_XLSX


def test_sl2020_lookup_is_gevuld():
    lookup = dataset._sl2020_lookup()
    assert len(lookup) > 1000
    assert lookup["quercus robur"] == "Zomereik"
    assert lookup["alnus glutinosa"] == "Zwarte els"


def test_kolommen_aanwezig(df):
    for kolom in ("naam", "wetenschappelijke_naam", "nederlandse_naam"):
        assert kolom in df.columns, kolom
    assert len(df) == 1644


def test_wetenschappelijke_naam_is_de_latijnse_naam(df):
    rij = df[df["wetenschappelijke_naam"] == "Quercus robur 'Fastigiata'"]
    assert len(rij) == 1
    assert rij.iloc[0]["nederlandse_naam"] == "Zomereik"
    assert rij.iloc[0]["naam"] == "Zomereik 'Fastigiata'"


def test_zonder_nederlandse_naam_blijft_latijn(df):
    rij = df[df["wetenschappelijke_naam"] == "Abies alba"]
    assert len(rij) == 1
    assert rij.iloc[0]["nederlandse_naam"] == ""
    assert rij.iloc[0]["naam"] == "Abies alba"


def test_dekkingsgraad(df):
    gevonden = (df["nederlandse_naam"].astype(str).str.strip() != "").sum()
    # SL2020 bevat alleen de Nederlandse wilde flora; sierbomen uit de
    # TreeEbb-set komen er niet in voor. Ruim een kwart is de verwachting.
    assert gevonden >= 400, gevonden
    assert gevonden < len(df)


# ───────────────────── matchstrategieën
@pytest.mark.parametrize("latijn,verwacht_nl,verwacht_rest", [
    ("Quercus robur", "Zomereik", ""),
    ("quercus  ROBUR", "Zomereik", ""),                       # genormaliseerd
    ("Quercus robur 'Fastigiata'", "Zomereik", "'Fastigiata'"),  # cultivar
    ("Alnus glutinosa var. barbata", "Zwarte els", "var. barbata"),
    ("Acer campestre 'Elsrijk'", "Spaanse aak", "'Elsrijk'"),
    ("Betula pendula", "Ruwe berk", ""),
    ("Bestaat nietus", "", ""),
])
def test_nl_naam_voor(latijn: str, verwacht_nl: str, verwacht_rest: str):
    nl, rest = dataset._nl_naam_voor(latijn, dataset._sl2020_lookup())
    assert nl == verwacht_nl
    assert rest == verwacht_rest


def test_hybride_notatie_beide_vormen():
    lookup = {"populus canescens": "Grauwe abeel", "salix x rubens": "Bastaardwilg"}
    assert dataset._nl_naam_voor("Populus x canescens", lookup)[0] == "Grauwe abeel"
    assert dataset._nl_naam_voor("Populus × canescens", lookup)[0] == "Grauwe abeel"
    assert dataset._nl_naam_voor("Salix x rubens 'Basfordiana'", lookup) == \
        ("Bastaardwilg", "'Basfordiana'")


def test_zonder_sl2020_blijft_dataset_werken(monkeypatch):
    import pandas as pd
    monkeypatch.setattr(dataset, "SL2020_XLSX", "bestaat/niet.xlsx")
    dataset._SL_CACHE.update({"map": None, "mtime": None, "path": None})
    try:
        assert dataset._sl2020_lookup() == {}
        d = dataset._verrijk_namen(pd.DataFrame({"naam": ["Quercus robur"]}))
        assert d["naam"].iloc[0] == "Quercus robur"
        assert d["nederlandse_naam"].iloc[0] == ""
        assert d["wetenschappelijke_naam"].iloc[0] == "Quercus robur"
    finally:
        dataset._SL_CACHE.update({"map": None, "mtime": None, "path": None})


# ───────────────────── zoeken
def test_zoeken_op_eik_geeft_resultaten(client: TestClient):
    r = client.get("/api/plants", params={"q": "eik"})
    assert r.status_code == 200
    d = r.json()
    assert d["count"] > 0
    assert any("Zomereik" in (it.get("naam") or "") for it in d["items"])


def test_plants_geeft_nederlandse_naam_terug(client: TestClient):
    r = client.get("/api/plants", params={"q": "quercus robur"})
    d = r.json()
    assert d["count"] > 0
    it = d["items"][0]
    assert "nederlandse_naam" in it
    assert "quercus" in it["wetenschappelijke_naam"].lower()


@pytest.mark.parametrize("term", ["els", "berk", "wilg", "linde"])
def test_nederlandse_zoektermen_werken(client: TestClient, term: str):
    r = client.get("/api/plants", params={"q": term})
    assert r.json()["count"] > 0, term

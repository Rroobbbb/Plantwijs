"""Tests voor de Ellenberg-verrijking (scripts/verrijk_ellenberg.py).

De verrijking zet de indicatorwaarden van Tichý et al. (2022) als kolommen
ellenberg_l/f/t/n/r/s in data/treeebb_planten_allfields.csv. Deze tests
controleren dat die kolommen bestaan, dat ze door de dataset-service en de API
heen komen, en dat een bekende inheemse soort (Quercus robur / Zomereik) een
gevulde vochtwaarde heeft.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from plantwijs.main import app  # noqa: E402
from plantwijs.services import dataset  # noqa: E402

ELLENBERG_KOLOMMEN = (
    "ellenberg_l", "ellenberg_f", "ellenberg_t",
    "ellenberg_n", "ellenberg_r", "ellenberg_s",
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def df():
    return dataset.get_df()


@pytest.fixture(scope="module")
def script():
    """Laad scripts/verrijk_ellenberg.py als module (staat niet op sys.path)."""
    pad = os.path.join(ROOT, "scripts", "verrijk_ellenberg.py")
    spec = importlib.util.spec_from_file_location("verrijk_ellenberg", pad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ───────────────────── bronbestand + kolommen
def test_ellenberg_bronbestand_staat_in_data():
    pad = os.path.join(ROOT, "data", "ellenberg_tichy_2022.xlsx")
    assert os.path.exists(pad), pad


def test_ellenberg_kolommen_bestaan_na_verrijking(df):
    for kolom in ELLENBERG_KOLOMMEN:
        assert kolom in df.columns, kolom


def test_ellenberg_waarden_zijn_gevuld(df):
    # Ellenberg dekt de Europese wilde flora; de TreeEbb-set zit vol met
    # niet-Europese sierbomen, dus een deel blijft leeg. Ruim een kwart is de
    # verwachting.
    gevuld = df["ellenberg_f"].astype(str).str.strip()
    aantal = int(((gevuld != "") & (gevuld.str.lower() != "nan")).sum())
    assert aantal >= 300, aantal
    assert aantal < len(df)


def test_zomereik_heeft_vochtwaarde(df):
    """Quercus robur (Zomereik) is inheems en staat in de Ellenberg-lijst."""
    rij = df[df["wetenschappelijke_naam"] == "Quercus robur"]
    assert len(rij) == 1
    waarde = str(rij.iloc[0]["ellenberg_f"]).strip()
    assert waarde not in ("", "nan"), waarde
    assert 1.0 <= float(waarde) <= 12.0, waarde
    assert rij.iloc[0]["nederlandse_naam"] == "Zomereik"


def test_cultivar_erft_waarde_van_de_soort(df):
    """De basis-match laat cultivars de waarde van de soort overnemen."""
    soort = df[df["wetenschappelijke_naam"] == "Quercus robur"].iloc[0]
    cultivar = df[df["wetenschappelijke_naam"] == "Quercus robur 'Fastigiata'"]
    assert len(cultivar) == 1
    assert str(cultivar.iloc[0]["ellenberg_f"]) == str(soort["ellenberg_f"])


def test_waarden_hebben_een_decimaal_en_geldig_bereik(df):
    for kolom in ELLENBERG_KOLOMMEN:
        waarden = df[kolom].astype(str).str.strip()
        waarden = waarden[(waarden != "") & (waarden.str.lower() != "nan")]
        assert len(waarden) > 0, kolom
        for w in waarden.unique():
            assert "." in w and len(w.split(".")[1]) == 1, f"{kolom}: {w}"
            assert 0.0 <= float(w) <= 12.0, f"{kolom}: {w}"


# ───────────────────── hulpfuncties van het script
@pytest.mark.parametrize("ruw,verwacht", [
    ("Quercus robur", "quercus robur"),
    ("  QUERCUS   ROBUR ", "quercus robur"),
    ("Quercus × warei", "quercus x warei"),
    ("Quercus robur ’Fastigiata’", "quercus robur 'fastigiata'"),
])
def test_norm_naam(script, ruw: str, verwacht: str):
    assert script.norm_naam(ruw) == verwacht


@pytest.mark.parametrize("genormaliseerd,verwacht", [
    ("quercus robur 'fastigiata'", ["quercus robur", "quercus x robur"]),
    ("populus x canescens", ["populus x canescens", "populus canescens"]),
    ("acer cappadocicum subsp. lobelii", ["acer cappadocicum", "acer x cappadocicum"]),
    ("malus", []),
])
def test_basis_kandidaten(script, genormaliseerd: str, verwacht: list):
    assert script.basis_kandidaten(genormaliseerd) == verwacht


@pytest.mark.parametrize("ruw,verwacht", [
    (5, "5.0"),
    (5.68, "5.7"),
    ("6.9", "6.9"),
    ("x", ""),        # indifferent in de Ellenberg-dataset
    ("NA", ""),
    (None, ""),
    ("", ""),
])
def test_format_waarde(script, ruw, verwacht: str):
    assert script.format_waarde(ruw) == verwacht


# ───────────────────── API
def test_api_plants_geeft_ellenberg_terug(client: TestClient):
    r = client.get("/api/plants", params={"q": "quercus robur"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    for kolom in ELLENBERG_KOLOMMEN:
        assert kolom in items[0], kolom
    assert any(it.get("ellenberg_f") not in (None, "") for it in items)

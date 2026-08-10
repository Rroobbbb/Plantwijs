"""Nazorg op fixronde 1: bodemtekst-herkenning, dataset-ondergrens en
vormen-ranking op locaties waar de vochtklasse onbekend is.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plantwijs.services import dataset  # noqa: E402
from plantwijs.services.advies import verrijk_advies  # noqa: E402
from plantwijs.services.pdok import _soil_from_text  # noqa: E402


# ───────────────────── _soil_from_text: 'X-arm' is geen X
@pytest.mark.parametrize(
    ("tekst", "verwacht"),
    [
        ("Leemarm fijn zand", "zand"),
        ("Zwak lemig fijn zand", "zand"),
        ("Kalkarme zandgronden", "zand"),
        ("Zavel", "leem"),
        ("Löss", "leem"),
        ("Petgaten", "veen"),
        ("Moerige gronden op zand", "veen"),
        ("Zware klei", "klei"),
        ("Bebouwing", None),
    ],
)
def test_soil_from_text(tekst, verwacht):
    assert _soil_from_text(tekst) == verwacht


# ───────────────────── dataset-ondergrens
@pytest.fixture()
def schone_dataset_cache():
    dataset.clear_cache()
    yield
    dataset.clear_cache()


def _mini_csv(tmp_path, naam: str, rijen: int) -> str:
    p = tmp_path / naam
    regels = ["naam;vocht;standplaats_licht"] + [f"Soort {i};droog;zon" for i in range(rijen)]
    p.write_text("\n".join(regels), encoding="utf-8")
    return str(p)


def test_te_klein_bestand_wordt_overgeslagen(tmp_path, monkeypatch, schone_dataset_cache):
    klein = _mini_csv(tmp_path, "klein.csv", 3)
    monkeypatch.setattr(dataset, "DATA_PATHS", [klein])
    monkeypatch.setattr(dataset, "ONLINE_CSV_URLS", [])
    monkeypatch.delenv("PLANTWIJS_CSV", raising=False)
    with pytest.raises(FileNotFoundError):
        dataset.get_df()


def test_te_klein_bestand_slaat_door_naar_volgende(tmp_path, monkeypatch, schone_dataset_cache):
    klein = _mini_csv(tmp_path, "klein.csv", 3)
    groot = _mini_csv(tmp_path, "groot.csv", dataset.MIN_DATASET_ROWS + 10)
    monkeypatch.setattr(dataset, "DATA_PATHS", [klein, groot])
    monkeypatch.setattr(dataset, "ONLINE_CSV_URLS", [])
    monkeypatch.delenv("PLANTWIJS_CSV", raising=False)
    df = dataset.get_df()
    assert len(df) == dataset.MIN_DATASET_ROWS + 10
    assert dataset.dataset_info()["path"] == groot


def test_expliciete_env_csv_mag_wel_klein_zijn(tmp_path, monkeypatch, schone_dataset_cache):
    klein = _mini_csv(tmp_path, "klein.csv", 3)
    monkeypatch.setenv("PLANTWIJS_CSV", klein)
    monkeypatch.setattr(dataset, "DATA_PATHS", [klein])
    monkeypatch.setattr(dataset, "ONLINE_CSV_URLS", [])
    df = dataset.get_df()
    assert len(df) == 3


# ───────────────────── vormen-ranking bij onbekende vochtklasse
def test_stuwwal_zonder_vochtklasse_krijgt_geen_elzensingel():
    """De live-casus uit de QA: Gt ontbreekt op de stuwwal (vocht=None), maar
    een elzensingel hoort daar ook dan niet tussen de aanbevelingen."""
    r = verrijk_advies(fgr="Hogere zandgronden", nsn="Stuwwal", gmm="Stuwwal",
                       bodem="zand", vocht=None, gt_code=None)
    namen = [v["vorm"] for v in r["aanbevolen_beplanting"]]
    assert len(namen) >= 3
    assert "Elzensingel" not in namen
    assert "Griend" not in namen


def test_zandbeekdal_houdt_elzensingel():
    """Maar in een nat beekdal op zandgrond blijft de elzensingel gewoon staan."""
    r = verrijk_advies(fgr="Hogere zandgronden", nsn="Beekdal zand/leem",
                       bodem="zand", vocht="nat", gt_code="IIIa")
    namen = [v["vorm"] for v in r["aanbevolen_beplanting"]]
    assert "Elzensingel" in namen

"""Tests voor de kennislaag-samenvoeging en de advies-endpoints.

De PDOK- en NSN-lookups worden gemonkeypatcht, zodat er geen netwerk nodig is.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plantwijs.main import app  # noqa: E402
from plantwijs.routers import advies as advies_router  # noqa: E402
from plantwijs.services import advies as advies_service  # noqa: E402
from plantwijs.services import context as ctx  # noqa: E402
from plantwijs.services import pdok  # noqa: E402
from plantwijs.services.advies import verrijk_advies  # noqa: E402

CONTRACT_VELDEN = {
    "fgr", "bodem", "bodem_bron", "gt_code", "vocht", "vocht_bron",
    "ahn", "ahn_bron", "gmm", "gmm_bron", "nsn", "advies", "elapsed_ms",
    "landschap", "wortelbare_diepte", "aanbevolen_beplanting", "bronnen_status",
}
LANDSCHAP_CATEGORIEEN = {"fgr", "nsn", "gmm", "bodem", "vocht"}
BRONNEN = {"fgr", "bodem", "gwt", "ahn", "gmm", "nsn"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# ───────────────────── verrijk_advies
def test_volledige_input_vult_alle_blokken():
    r = verrijk_advies(
        fgr="Hogere zandgronden", nsn="Dekzandrug", gmm="Dekzandrug",
        bodem="zand", vocht="droog", gt_code="VIo",
    )
    assert set(r) == {"landschap", "wortelbare_diepte", "aanbevolen_beplanting"}

    assert set(r["landschap"]) == LANDSCHAP_CATEGORIEEN
    for cat, blok in r["landschap"].items():
        assert blok is not None, cat
        assert set(blok) == {"titel", "ontstaan", "versterken", "bron"}
        assert blok["titel"] and blok["ontstaan"] and blok["versterken"]
    assert r["landschap"]["fgr"]["titel"] == "Hogere zandgronden"
    assert r["landschap"]["nsn"]["titel"] == "Dekzandrug"

    w = r["wortelbare_diepte"]
    assert set(w) == {"klasse", "band_cm", "indicatie", "toelichting"}
    assert w["klasse"] == "zeer_goed"

    vormen = r["aanbevolen_beplanting"]
    assert 3 <= len(vormen) <= 5
    for v in vormen:
        assert set(v) == {"vorm", "omschrijving", "waarom_hier", "voorbeeldsoorten"}
        assert v["vorm"] and v["omschrijving"] and v["waarom_hier"]
        assert v["voorbeeldsoorten"]
    # de houtwal is dé vorm van de hogere zandgronden en moet bovenaan staan
    assert vormen[0]["vorm"] == "Houtwal"
    assert "hogere zandgronden" in vormen[0]["waarom_hier"].lower()


def test_alles_none_geeft_fallbacks():
    r = verrijk_advies()
    assert set(r["landschap"]) == LANDSCHAP_CATEGORIEEN
    for cat, blok in r["landschap"].items():
        assert blok is not None, cat
        assert "onbekend" in blok["titel"].lower()
    assert r["wortelbare_diepte"] is None
    assert len(r["aanbevolen_beplanting"]) >= 3
    for v in r["aanbevolen_beplanting"]:
        assert v["voorbeeldsoorten"]


def test_natte_veenlocatie_krijgt_natte_vormen():
    r = verrijk_advies(fgr="Laagveengebied", nsn="Petgaten", bodem="veen",
                       vocht="zeer nat", gt_code="Ia")
    namen = [v["vorm"] for v in r["aanbevolen_beplanting"]]
    assert "Griend" in namen or "Knotbomen" in namen or "Elzensingel" in namen
    assert "Graft" not in namen  # heuvelland-vorm hoort hier niet
    assert r["wortelbare_diepte"]["klasse"] == "zeer_beperkt"


def test_droge_stuwwal_krijgt_geen_natte_vormen():
    """Vocht-conflict sluit uit: een elzensingel hoort niet op een droge stuwwal."""
    r = verrijk_advies(fgr="Hogere zandgronden", nsn="Stuwwal", bodem="zand",
                       vocht="droog", gt_code="VIo")
    namen = [v["vorm"] for v in r["aanbevolen_beplanting"]]

    assert 3 <= len(namen) <= 5
    for nat in ("Elzensingel", "Griend", "Knotbomen"):
        assert nat not in namen, nat
    assert namen[0] == "Houtwal"


def test_zeer_droog_houdt_minimaal_drie_vormen():
    """Ook als bijna elke vorm op vocht afvalt blijven er drie suggesties over."""
    r = verrijk_advies(fgr="Hogere zandgronden", nsn="Stuwwal", bodem="zand",
                       vocht="zeer droog", gt_code="VIId")
    namen = [v["vorm"] for v in r["aanbevolen_beplanting"]]

    assert len(namen) >= 3
    assert namen[0] == "Houtwal"          # de enige vorm die zeer droog noemt
    assert "Elzensingel" not in namen     # aanvullen gebeurt met generieke vormen
    assert "Griend" not in namen


def test_natte_plek_houdt_natte_vormen():
    """De uitsluiting mag natte vormen op natte grond juist niet raken."""
    r = verrijk_advies(fgr="Laagveengebied", nsn="Petgaten", bodem="veen",
                       vocht="zeer nat", gt_code="Ia")
    namen = [v["vorm"] for v in r["aanbevolen_beplanting"]]

    assert "Elzensingel" in namen
    assert "Griend" in namen
    assert "Houtwal" not in namen  # vraagt om droog/vochtig


def test_onbekend_vocht_sluit_niets_uit():
    """Zonder vochtklasse blijft de vocht-eis ongetoetst; niets valt af."""
    ids = {"fgr": ctx.entry_id("fgr", "Laagveengebied"),
           "nsn": ctx.entry_id("nsn", "Petgaten"),
           "bodem": ctx.entry_id("bodem", "veen"),
           "vocht": ctx.entry_id("vocht", None)}
    assert ids["vocht"] == "onbekend"
    namen = [v["vorm"] for v in advies_service.aanbevolen_beplanting_voor_ids(ids)]
    assert "Elzensingel" in namen


def test_onbekend_vocht_zet_vochtclaim_achteraan(monkeypatch):
    """Tie-break: bij gelijke score gaat een vorm zónder vochtvoorkeur voor."""
    vormen = [
        {"id": "met_vocht", "naam": "Met vochtvoorkeur", "omschrijving": "x",
         "voorbeeldsoorten": ["Zomereik (Quercus robur)"],
         "past_bij": {"fgr": ["hogere_zandgronden"], "vocht": ["nat"]}},
        {"id": "zonder_vocht", "naam": "Zonder vochtvoorkeur", "omschrijving": "y",
         "voorbeeldsoorten": ["Ruwe berk (Betula pendula)"],
         "past_bij": {"fgr": ["hogere_zandgronden"]}},
    ]
    monkeypatch.setattr(advies_service, "_vormen", lambda: vormen)

    onbekend = {"fgr": "hogere_zandgronden", "nsn": None, "bodem": None,
                "vocht": "onbekend"}
    namen = [v["vorm"] for v in advies_service.aanbevolen_beplanting_voor_ids(onbekend)]
    assert namen[0] == "Zonder vochtvoorkeur"

    # met een bekende, passende vochtklasse telt alleen de score + bestandsvolgorde
    bekend = dict(onbekend, vocht="nat")
    namen = [v["vorm"] for v in advies_service.aanbevolen_beplanting_voor_ids(bekend)]
    assert namen[0] == "Met vochtvoorkeur"


def test_score_sorteert_aflopend():
    """Vormen met meer past_bij-treffers staan bovenaan."""
    ids = {
        "fgr": ctx.entry_id("fgr", "Heuvelland"),
        "nsn": ctx.entry_id("nsn", "Losshelling"),
        "bodem": ctx.entry_id("bodem", "leem"),
        "vocht": ctx.entry_id("vocht", "droog"),
    }
    gekozen = advies_service.aanbevolen_beplanting_voor_ids(ids)
    per_naam = {v.get("naam"): v for v in advies_service._vormen()}
    scores = [advies_service._score(per_naam[v["vorm"]], ids)[0] for v in gekozen]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] >= 3


# ───────────────────── /advies/geo met gemockte bronnen
def _mock_bronnen(monkeypatch, *, fgr="Hogere zandgronden", nsn="Dekzandrug",
                  bodem=("zand", {}), gwt=("droog", {}, "VIo"),
                  ahn=("12.34", {}), gmm=("Dekzandrug", {})):
    def _of_raise(waarde):
        def _fn(*_a, **_k):
            if isinstance(waarde, Exception):
                raise waarde
            return waarde
        return _fn

    monkeypatch.setattr(advies_router, "fgr_from_point", _of_raise(fgr))
    monkeypatch.setattr(advies_router, "nsn_from_point", _of_raise(nsn))
    monkeypatch.setattr(advies_router, "bodem_from_bodemkaart", _of_raise(bodem))
    monkeypatch.setattr(advies_router, "vocht_from_gwt", _of_raise(gwt))
    monkeypatch.setattr(advies_router, "ahn_from_wms", _of_raise(ahn))
    monkeypatch.setattr(advies_router, "gmm_from_wms", _of_raise(gmm))


def test_advies_geo_bevat_alle_contractvelden(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    r = client.get("/advies/geo", params={"lat": 52.078, "lon": 5.89})
    assert r.status_code == 200
    d = r.json()

    assert CONTRACT_VELDEN <= set(d)
    assert d["fgr"] == "Hogere zandgronden"
    assert d["bodem"] == "zand"
    assert d["gt_code"] == "VIo"
    assert d["vocht"] == "droog"
    assert d["ahn"] == "12.34"
    assert d["gmm"] == "Dekzandrug"
    assert d["nsn"] == "Dekzandrug"
    assert isinstance(d["advies"], list) and d["advies"]

    assert set(d["landschap"]) == LANDSCHAP_CATEGORIEEN
    assert d["landschap"]["nsn"]["titel"] == "Dekzandrug"
    assert d["wortelbare_diepte"]["band_cm"]
    assert len(d["aanbevolen_beplanting"]) >= 3
    assert set(d["bronnen_status"]) == BRONNEN
    assert all(v == "ok" for v in d["bronnen_status"].values())


def test_advies_geo_bestaande_velden_ongewijzigd(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    r = client.get("/advies/geo", params={"lat": 52.078, "lon": 5.89})
    d = r.json()
    assert d["bodem_bron"] == "BRO Bodemkaart WMS"
    assert d["vocht_bron"] == "BRO Gt/GLG WMS"
    assert d["ahn_bron"] == "PDOK AHN WMS (DTM 0.5m)"
    assert d["gmm_bron"] == "BRO Geomorfologische kaart (GMM) WMS"
    assert isinstance(d["elapsed_ms"], int)
    assert "nederlandse_naam" in d["advies"][0]


def test_advies_geo_lege_bron_geeft_status_leeg(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch, gmm=(None, {}), ahn=(None, {}))
    r = client.get("/advies/geo", params={"lat": 52.078, "lon": 5.89})
    d = r.json()
    assert d["bronnen_status"]["gmm"] == "leeg"
    assert d["bronnen_status"]["ahn"] == "leeg"
    assert d["gmm"] is None
    assert d["gmm_bron"] == "onbekend"
    assert d["landschap"]["gmm"]["titel"].lower().endswith("onbekend")


def test_kapotte_bron_geeft_geen_500(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch,
                  bodem=RuntimeError("PDOK plat"),
                  nsn=RuntimeError("index stuk"))
    r = client.get("/advies/geo", params={"lat": 52.078, "lon": 5.89})
    assert r.status_code == 200
    d = r.json()
    assert d["bronnen_status"]["bodem"] == "fout"
    assert d["bronnen_status"]["nsn"] == "fout"
    assert d["bronnen_status"]["fgr"] == "ok"
    assert d["bodem"] is None
    assert d["nsn"] is None
    # de kennislaag blijft gewoon werken op wat er wél is
    assert d["landschap"]["fgr"]["titel"] == "Hogere zandgronden"
    assert len(d["aanbevolen_beplanting"]) >= 3


def test_alle_bronnen_leeg(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch, fgr=None, nsn=None, bodem=(None, {}),
                  gwt=(None, {}, None), ahn=(None, {}), gmm=(None, {}))
    r = client.get("/advies/geo", params={"lat": 52.078, "lon": 5.89})
    assert r.status_code == 200
    d = r.json()
    assert d["fgr"] == "Onbekend"
    assert d["wortelbare_diepte"] is None
    assert len(d["aanbevolen_beplanting"]) >= 3
    assert d["bronnen_status"]["fgr"] == "leeg"
    assert d["bronnen_status"]["nsn"] in ("leeg", "ontbreekt")


# ───────────────────── soortenselectie: bodem en vocht (fix QA-1)
# Mini-dataset met de TreeEbb-schrijfwijzen: "zware klei" hoort bij de
# categorie klei, "löss"/"zavel" bij leem. Vroeger werd hier ruw op tekst
# vergeleken, waardoor klei en leem nul soorten opleverden.
def _mini_dataset() -> pd.DataFrame:
    return pd.DataFrame([
        {"naam": "Kleiplant", "wetenschappelijke_naam": "Testus argillae",
         "status_nl": "inheems", "invasief": "nee", "standplaats_licht": "zon",
         "vocht": "vochtig | nat", "grondsoorten": "zware klei | lichte klei"},
        {"naam": "Leemplant", "wetenschappelijke_naam": "Testus limi",
         "status_nl": "inheems", "invasief": "nee", "standplaats_licht": "zon",
         "vocht": "zeer nat", "grondsoorten": "löss | zavel"},
        {"naam": "Zandplant", "wetenschappelijke_naam": "Testus harenae",
         "status_nl": "inheems", "invasief": "nee", "standplaats_licht": "zon",
         "vocht": "droog", "grondsoorten": "zand"},
        {"naam": "Alleplant", "wetenschappelijke_naam": "Testus omnium",
         "status_nl": "inheems", "invasief": "nee", "standplaats_licht": "zon",
         "vocht": "zeer droog", "grondsoorten": "alle grondsoorten"},
    ])


def _namen(client: TestClient, **params) -> list[str]:
    r = client.get("/advies/geo", params={"lat": 52.078, "lon": 5.89, **params})
    assert r.status_code == 200
    return [rij["naam"] for rij in r.json()["advies"]]


@pytest.mark.parametrize("bodem, verwacht", [
    ("klei", {"Kleiplant", "Alleplant"}),
    ("leem", {"Leemplant", "Alleplant"}),
    ("zand", {"Zandplant", "Alleplant"}),
    ("veen", {"Alleplant"}),
])
def test_bodemfilter_canoniseert_treeebb_termen(client: TestClient, monkeypatch,
                                                bodem: str, verwacht: set):
    _mock_bronnen(monkeypatch, bodem=(bodem, {}), gwt=(None, {}, None))
    monkeypatch.setattr(advies_router, "get_df", _mini_dataset)
    assert set(_namen(client)) == verwacht


def test_bodem_zonder_categorie_filtert_niet(client: TestClient, monkeypatch):
    """Een kaartterm die geen zand/klei/leem/veen is, mag de lijst niet legen."""
    _mock_bronnen(monkeypatch, bodem=("Bebouwing", {}), gwt=(None, {}, None))
    monkeypatch.setattr(advies_router, "get_df", _mini_dataset)
    assert len(_namen(client)) == 4


@pytest.mark.parametrize("vocht, verwacht", [
    ("nat", {"Kleiplant"}),
    ("zeer nat", {"Leemplant"}),
    ("droog", {"Zandplant"}),
    ("zeer droog", {"Alleplant"}),
])
def test_vochtfilter_matcht_de_vijf_klassen(client: TestClient, monkeypatch,
                                            vocht: str, verwacht: set):
    _mock_bronnen(monkeypatch, bodem=(None, {}), gwt=(vocht, {}, None))
    monkeypatch.setattr(advies_router, "get_df", _mini_dataset)
    assert set(_namen(client)) == verwacht


@pytest.mark.parametrize("bodem", ["klei", "leem", "zand", "veen"])
def test_echte_dataset_geeft_soorten_voor_elke_bodem(client: TestClient,
                                                     monkeypatch, bodem: str):
    """Regressie: klei en leem gaven op de echte dataset nul soorten."""
    _mock_bronnen(monkeypatch, bodem=(bodem, {}), gwt=("vochtig", {}, "IVu"))
    assert len(_namen(client)) > 0


def test_advies_geo_en_pdf_selecteren_hetzelfde(client: TestClient, monkeypatch):
    """/advies/geo en het PDF-rapport delen dezelfde filterlaag."""
    from plantwijs.services import report

    _mock_bronnen(monkeypatch, bodem=("zware klei", {}), gwt=("nat", {}, "IIIb"))
    uit_geo = _namen(client)

    df, gebruikt = report._soorten(
        {"fgr": None, "nsn": None, "bodem": "zware klei", "vocht": "nat",
         "gt_code": "IIIb", "ahn": None, "gmm": None},
        inheems_only=False, toon_inheems=None, toon_ingeburgerd=None,
        toon_exoot=None, exclude_invasief=True, licht=[], vocht=[], bodem=[],
        beplantingstype=[])

    assert gebruikt["bodem"] == ["zware klei"]
    assert len(uit_geo) > 0
    assert set(uit_geo) == set(df["naam"])


# ───────────────────── bodemkaart-termen en bodem_detail (fix QA-3)
@pytest.mark.parametrize("ruw, verwacht", [
    ("Petgaten", "veen"),
    ("petgat", "veen"),
    ("Moerige podzolgronden", "veen"),
    ("moerige eerdgronden", "veen"),
    ("Zware klei", "klei"),
    ("Duinvaaggronden; fijn zand", "zand"),
    ("Kalkrijke poldervaaggronden; zavel", "leem"),
])
def test_soil_from_text(ruw: str, verwacht: str):
    assert pdok._soil_from_text(ruw) == verwacht


def test_bodem_from_bodemkaart_bewaart_de_ruwe_term(monkeypatch):
    monkeypatch.setattr(pdok, "get_wms_meta", lambda: {"bodem": {"layer": "X"}})
    monkeypatch.setattr(pdok, "_wms_getfeatureinfo",
                        lambda *_a, **_k: {"first_soilname": "Petgaten"})
    waarde, props = pdok.bodem_from_bodemkaart(52.15, 4.85)
    assert waarde == "veen"
    assert props[pdok.RUWE_BODEM_KEY] == "Petgaten"


def test_bodem_detail_alleen_bij_afwijkende_kaartterm(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch, bodem=("veen", {pdok.RUWE_BODEM_KEY: "Petgaten"}))
    r = client.get("/advies/geo", params={"lat": 52.15, "lon": 4.85})
    d = r.json()
    assert d["bodem"] == "veen"
    assert d["bodem_detail"] == "Petgaten"

    _mock_bronnen(monkeypatch, bodem=("zand", {pdok.RUWE_BODEM_KEY: "zand"}))
    d = client.get("/advies/geo", params={"lat": 52.078, "lon": 5.89}).json()
    assert d["bodem"] == "zand"
    assert d["bodem_detail"] is None


def test_bodem_detail_is_altijd_aanwezig(client: TestClient, monkeypatch):
    """Additief veld: ook zonder ruwe term staat de sleutel in de response."""
    _mock_bronnen(monkeypatch)
    d = client.get("/advies/geo", params={"lat": 52.078, "lon": 5.89}).json()
    assert "bodem_detail" in d
    assert d["bodem_detail"] is None


# ───────────────────── /api/context
def test_context_happy_path(client: TestClient):
    r = client.get("/api/context", params={"category": "fgr", "value": "Hogere zandgronden"})
    assert r.status_code == 200
    d = r.json()
    assert set(d) == {"titel", "ontstaan", "versterken", "bron"}
    assert d["titel"] == "Hogere zandgronden"
    assert isinstance(d["versterken"], list) and d["versterken"]


def test_context_nsn_label(client: TestClient):
    r = client.get("/api/context", params={"category": "nsn", "value": "Beekdal zand/leem"})
    assert r.status_code == 200
    assert r.json()["titel"] == "Beekdal op zand en leem"


def test_context_onbekende_waarde_geeft_fallback(client: TestClient):
    r = client.get("/api/context", params={"category": "fgr", "value": "Mordor"})
    assert r.status_code == 200
    assert "onbekend" in r.json()["titel"].lower()


@pytest.mark.parametrize("params", [
    {"category": "bestaatniet", "value": "Hogere zandgronden"},
    {"category": "fgr", "value": ""},
    {"category": "", "value": "x"},
])
def test_context_404(client: TestClient, params: dict):
    r = client.get("/api/context", params=params)
    assert r.status_code == 404
    assert r.json() == {"error": "not_found"}


def test_context_zonder_parameters_is_422(client: TestClient):
    assert client.get("/api/context").status_code == 422

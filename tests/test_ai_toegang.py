"""Tests voor WP6 — AI- en machine-toegankelijkheid.

Dekt: adres-geocoding in /advies/geo, het Markdown-rapport (format=md) en de
drie machine-bestanden /llms.txt, /robots.txt en /sitemap.xml.

Er gaat geen netwerkverkeer overheen: de PDOK/NSN-lookups en de geocoder
worden gemonkeypatcht, volgens hetzelfde patroon als tests/test_advies.py.
"""

from __future__ import annotations

import os
import re
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plantwijs.main import app  # noqa: E402
from plantwijs.routers import advies as advies_router  # noqa: E402
from plantwijs.services import geocode  # noqa: E402
from plantwijs.services.rapport_md import MAX_SOORTEN, rapport_markdown  # noqa: E402

VERWACHTE_KOPPEN = (
    "# Beplantingswijzer-advies voor",
    "## Jouw plek",
    "## Jouw landschap",
    "## Wortelruimte",
    "## Wat kun jij doen",
    "## Passende soorten",
    "## Bronnen en verantwoording",
)

TABELKOP = "| Naam | Wetenschappelijke naam | Type | Licht | Vocht | Hoogte | Status |"

GEVONDEN = {"adres_gevonden": "Loenenseweg 1, 7361 GB Beekbergen",
            "lat": 52.14612744, "lon": 5.98157932}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# ───────────────────── mocks
def _mock_bronnen(monkeypatch, *, fgr="Hogere zandgronden", nsn="Dekzandrug",
                  bodem=("zand", {}), gwt=("droog", {}, "VIo"),
                  ahn=("12.34", {}), gmm=("Dekzandrug", {})):
    def _vast(waarde):
        def _fn(*_a, **_k):
            return waarde
        return _fn

    monkeypatch.setattr(advies_router, "fgr_from_point", _vast(fgr))
    monkeypatch.setattr(advies_router, "nsn_from_point", _vast(nsn))
    monkeypatch.setattr(advies_router, "bodem_from_bodemkaart", _vast(bodem))
    monkeypatch.setattr(advies_router, "vocht_from_gwt", _vast(gwt))
    monkeypatch.setattr(advies_router, "ahn_from_wms", _vast(ahn))
    monkeypatch.setattr(advies_router, "gmm_from_wms", _vast(gmm))


def _mock_geocode(monkeypatch, resultaat=GEVONDEN):
    """Vervang de geocoder en houd bij waarmee hij is aangeroepen."""
    aanroepen = []

    def _fn(adres):
        aanroepen.append(adres)
        return dict(resultaat) if resultaat else None

    monkeypatch.setattr(advies_router, "zoek_adres", _fn)
    return aanroepen


class _NepResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


# ───────────────────── services/geocode.py
def test_zoek_adres_parseert_centroide(monkeypatch):
    payload = {"response": {"numFound": 1, "docs": [{
        "weergavenaam": "Loenenseweg 1, 7361 GB Beekbergen",
        "centroide_ll": "POINT(5.98157932 52.14612744)",
    }]}}
    gebruikt = {}

    def _get(url, **kwargs):
        gebruikt["url"] = url
        gebruikt["timeout"] = kwargs.get("timeout")
        return _NepResponse(payload)

    monkeypatch.setattr(geocode.requests, "get", _get)
    r = geocode.zoek_adres("Loenenseweg 1 Beekbergen")

    assert r == {"adres_gevonden": "Loenenseweg 1, 7361 GB Beekbergen",
                 "lat": 52.14612744, "lon": 5.98157932}
    # POINT is (lon lat): de breedtegraad moet het grootste getal zijn in NL
    assert r["lat"] > r["lon"]
    assert gebruikt["timeout"] == 8
    assert gebruikt["url"].startswith(geocode.LOCATIESERVER_FREE)
    assert "rows=1" in gebruikt["url"]
    assert "Loenenseweg" in gebruikt["url"]


def test_zoek_adres_zonder_treffer_is_none(monkeypatch):
    monkeypatch.setattr(geocode.requests, "get",
                        lambda *a, **k: _NepResponse({"response": {"numFound": 0, "docs": []}}))
    assert geocode.zoek_adres("xyzonzin123") is None


def test_zoek_adres_bij_bronfout_is_none(monkeypatch):
    def _stuk(*_a, **_k):
        raise RuntimeError("PDOK plat")

    monkeypatch.setattr(geocode.requests, "get", _stuk)
    assert geocode.zoek_adres("Domplein 1 Utrecht") is None


def test_zoek_adres_lege_invoer_doet_geen_request(monkeypatch):
    def _nooit(*_a, **_k):
        raise AssertionError("er mag geen request gedaan worden")

    monkeypatch.setattr(geocode.requests, "get", _nooit)
    assert geocode.zoek_adres("   ") is None


@pytest.mark.parametrize("waarde", [None, "", "POINT()", "POINT(abc def)", "5.98 52.14"])
def test_parse_point_ll_onbruikbaar(waarde):
    assert geocode.parse_point_ll(waarde) is None


# ───────────────────── /advies/geo?adres=
def test_adres_flow_geeft_200_met_locatieveld(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    aanroepen = _mock_geocode(monkeypatch)

    r = client.get("/advies/geo", params={"adres": "Loenenseweg 1 Beekbergen"})
    assert r.status_code == 200
    d = r.json()

    assert aanroepen == ["Loenenseweg 1 Beekbergen"]
    assert d["locatie"] == {
        "adres_gevonden": "Loenenseweg 1, 7361 GB Beekbergen",
        "lat": 52.14612744,
        "lon": 5.98157932,
    }
    # de rest van het contract blijft gewoon staan
    assert d["fgr"] == "Hogere zandgronden"
    assert d["advies"] and d["landschap"] and d["aanbevolen_beplanting"]


def test_lat_lon_winnen_van_adres(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    aanroepen = _mock_geocode(monkeypatch)

    r = client.get("/advies/geo",
                   params={"lat": 52.078, "lon": 5.89, "adres": "Domplein 1 Utrecht"})
    assert r.status_code == 200
    d = r.json()
    assert aanroepen == []  # geocoder is niet aangeroepen
    assert d["locatie"] == {"adres_gevonden": None, "lat": 52.078, "lon": 5.89}


def test_locatie_veld_bij_gewone_lat_lon(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    r = client.get("/advies/geo", params={"lat": 52.078, "lon": 5.89})
    assert r.status_code == 200
    assert r.json()["locatie"] == {"adres_gevonden": None, "lat": 52.078, "lon": 5.89}


def test_adres_zonder_match_geeft_404(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    _mock_geocode(monkeypatch, resultaat=None)

    r = client.get("/advies/geo", params={"adres": "xyzonzin123"})
    assert r.status_code == 404
    assert r.json() == {"error": "adres_niet_gevonden"}


@pytest.mark.parametrize("params", [{}, {"lat": 52.078}, {"lon": 5.89}, {"adres": "   "}])
def test_zonder_bruikbare_locatie_geeft_422(client: TestClient, params: dict):
    r = client.get("/advies/geo", params=params)
    assert r.status_code == 422
    d = r.json()
    assert d["error"] == "locatie_ontbreekt"
    assert "lat" in d["detail"] and "adres" in d["detail"]


# ───────────────────── format=md
def _markdown(client: TestClient, params: dict) -> str:
    r = client.get("/advies/geo", params=params)
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/markdown; charset=utf-8"
    return r.text


def test_format_md_geeft_markdown_met_alle_secties(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    _mock_geocode(monkeypatch)

    tekst = _markdown(client, {"adres": "Loenenseweg 1 Beekbergen", "format": "md"})

    for kop in VERWACHTE_KOPPEN:
        assert kop in tekst, kop
    assert tekst.startswith("# Beplantingswijzer-advies voor Loenenseweg 1, 7361 GB Beekbergen")
    # elke sectie heeft inhoud: na een kop komt nooit meteen de volgende kop
    koppen = [i for i, r in enumerate(tekst.splitlines()) if r.startswith("## ")]
    regels = tekst.splitlines()
    for i in koppen:
        inhoud = [r for r in regels[i + 1:i + 6] if r.strip() and not r.startswith("#")]
        assert inhoud, regels[i]


def test_format_md_bevat_soortentabel_met_max_40_rijen(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    tekst = _markdown(client, {"lat": 52.078, "lon": 5.89, "format": "md"})

    assert TABELKOP in tekst
    na_kop = tekst.split(TABELKOP, 1)[1].splitlines()
    rijen = []
    for regel in na_kop:
        if not regel.strip():
            continue
        if regel.startswith("|---"):
            continue
        if not regel.startswith("|"):
            break
        rijen.append(regel)
    assert 0 < len(rijen) <= MAX_SOORTEN == 40
    assert all(len(r.split("|")) == 9 for r in rijen)  # 7 kolommen + rand
    # er zijn er méér dan getoond; dat moet in de tekst staan
    assert "de eerste 40" in tekst


def test_format_md_verwijst_naar_export_en_site(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    tekst = _markdown(client, {"lat": 52.078, "lon": 5.89, "format": "md"})

    assert "http://testserver/export/csv" in tekst
    assert "http://testserver/llms.txt" in tekst
    assert "indicatief" in tekst.lower()  # disclaimer
    assert "Beplantingswijzer" in tekst


def test_format_md_bevat_geen_none_of_null(client: TestClient, monkeypatch):
    """Ook als álle bronnen leeg zijn mag er geen kale None/null in de tekst staan."""
    _mock_bronnen(monkeypatch, fgr=None, nsn=None, bodem=(None, {}),
                  gwt=(None, {}, None), ahn=(None, {}), gmm=(None, {}))
    tekst = _markdown(client, {"lat": 52.078, "lon": 5.89, "format": "md"})

    assert "None" not in tekst
    assert not re.search(r"\bnull\b", tekst, re.IGNORECASE)
    assert "nan" not in tekst.lower().split()
    for kop in VERWACHTE_KOPPEN:
        assert kop in tekst, kop
    assert "niet bepaald" in tekst  # lege waarden krijgen uitleg


def test_format_json_en_default_blijven_json(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    for params in ({"lat": 52.078, "lon": 5.89},
                   {"lat": 52.078, "lon": 5.89, "format": "json"}):
        r = client.get("/advies/geo", params=params)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/json")
        assert "advies" in r.json()


# ───────────────────── statusfilters in het md-rapport
def _statusregel(tekst: str) -> str:
    return next(r for r in tekst.splitlines() if r.startswith("Toegepast statusfilter:"))


def test_md_zonder_statusparams_gebruikt_site_defaults(client: TestClient, monkeypatch):
    """format=md volgt de website: inheems + ingeburgerd, geen exoten."""
    _mock_bronnen(monkeypatch)
    params = {"lat": 52.078, "lon": 5.89}

    tekst = _markdown(client, {**params, "format": "md"})
    assert _statusregel(tekst) == "Toegepast statusfilter: inheems en ingeburgerd."

    # de md-lijst is daardoor korter dan de ongefilterde json-lijst
    json_aantal = len(client.get("/advies/geo", params=params).json()["advies"])
    md_aantal = int(re.search(r"^(\d+) soorten uit de Beplantingswijzer-lijst",
                              tekst, re.M).group(1))
    assert 0 < md_aantal < json_aantal


def test_md_expliciete_statusparams_winnen(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    tekst = _markdown(client, {"lat": 52.078, "lon": 5.89, "format": "md",
                               "toon_inheems": "true"})
    assert _statusregel(tekst) == "Toegepast statusfilter: inheems."


def test_json_gedrag_bij_statusfilters_blijft_ongewijzigd(client: TestClient, monkeypatch):
    """Backwards compat: zonder toon_* toont format=json nog steeds alles."""
    _mock_bronnen(monkeypatch)
    params = {"lat": 52.078, "lon": 5.89}

    alles = client.get("/advies/geo", params=params).json()["advies"]
    statussen = {str(r.get("status_nl") or "").strip().lower() for r in alles}
    assert "exoot" in statussen

    gefilterd = client.get(
        "/advies/geo", params={**params, "toon_inheems": "true"}).json()["advies"]
    assert 0 < len(gefilterd) < len(alles)


def test_rapport_markdown_met_lege_data():
    """De renderer moet ook een vrijwel leeg advies netjes opleveren."""
    tekst = rapport_markdown({
        "fgr": "Onbekend", "bodem": None, "vocht": None, "gt_code": None,
        "ahn": None, "gmm": None, "nsn": None, "advies": [],
        "landschap": {}, "wortelbare_diepte": None, "aanbevolen_beplanting": [],
        "bronnen_status": {}, "locatie": {"adres_gevonden": None, "lat": None, "lon": None},
    })
    for kop in VERWACHTE_KOPPEN:
        assert kop in tekst, kop
    assert "None" not in tekst
    assert not re.search(r"\bnull\b", tekst, re.IGNORECASE)
    assert tekst.startswith("# Beplantingswijzer-advies voor deze locatie")


# ───────────────────── /llms.txt, /robots.txt, /sitemap.xml
def test_llms_txt(client: TestClient):
    r = client.get("/llms.txt")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/plain; charset=utf-8"
    t = r.text
    assert "Beplantingswijzer" in t
    assert "http://testserver/advies/geo?adres=" in t
    assert "http://testserver/advies/geo?lat=" in t
    assert "format=md" in t
    assert "http://testserver/api/plants?q=" in t
    assert "http://testserver/openapi.json" in t
    assert "WGS84" in t and "Netherlands" in t
    assert "cite Beplantingswijzer" in t


def test_robots_txt(client: TestClient):
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/plain; charset=utf-8"
    t = r.text
    assert "User-agent: *" in t
    for agent in ("GPTBot", "ClaudeBot", "Claude-User", "PerplexityBot",
                  "Google-Extended", "CCBot"):
        assert f"User-agent: {agent}" in t, agent
    assert t.count("Allow: /") >= 7
    assert "Disallow: /api/admin" in t
    assert "Sitemap: http://testserver/sitemap.xml" in t


def test_sitemap_xml(client: TestClient):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    t = r.text
    assert t.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "http://testserver" in t  # absolute URL's op basis van de request-host
    for pad in ("http://testserver/", "http://testserver/llms.txt", "http://testserver/docs"):
        assert f"<loc>{pad}</loc>" in t


def test_openapi_metadata(client: TestClient):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"] == "Beplantingswijzer API"
    assert "/llms.txt" in spec["info"]["description"]
    assert spec["info"]["version"]

    geo = spec["paths"]["/advies/geo"]["get"]
    assert geo["summary"]
    assert "format=md" in geo["description"]
    namen = {p["name"] for p in geo["parameters"]}
    assert {"lat", "lon", "adres", "format"} <= namen

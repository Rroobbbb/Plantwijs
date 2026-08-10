"""Smoke-tests voor de PlantWijs-API.

Geen netwerk nodig: alleen endpoints die op de lokale CSV / statics draaien.
De TestClient wordt bewust NIET als context manager gebruikt, zodat de lifespan
(NSN-index bouwen) niet draait.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plantwijs.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_app_importeert():
    from api import app as shim_app  # compat-shim moet dezelfde app teruggeven

    assert shim_app is app


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["dataset"]["rows"] > 0
    assert data["nsn"]["status"] in ("ok", "index_bouwt", "ontbreekt")
    assert isinstance(data["versie"], str)
    # De frontend zet hiermee de PDF-knop aan; reportlab zit in requirements.txt.
    assert data["pdf_beschikbaar"] is True


def test_health_pdf_beschikbaar_bij_ontbrekende_module(client: TestClient, monkeypatch):
    """Zonder reportlab (import faalt) meldt health netjes False in plaats van 500."""
    from plantwijs.routers import plants as plants_router

    def _stuk(_naam):
        raise ImportError("reportlab ontbreekt")

    monkeypatch.setattr(plants_router.importlib, "import_module", _stuk)
    data = client.get("/api/health").json()
    assert data["pdf_beschikbaar"] is False
    assert data["ok"] is True


def test_plants_zonder_filter(client: TestClient):
    r = client.get("/api/plants")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    assert len(data["items"]) == data["count"]
    assert "naam" in data["items"][0]


def test_plants_zoekterm(client: TestClient):
    # Sinds WP2b krijgt de dataset Nederlandse namen uit SL2020; zoeken op
    # "eik" werkt daardoor ook (zie tests/test_dataset_namen.py). Hier testen
    # we de wetenschappelijke naam, die ongewijzigd blijft werken.
    r = client.get("/api/plants", params={"q": "quercus"})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    assert all("quercus" in (it.get("wetenschappelijke_naam") or "").lower()
               or "quercus" in (it.get("naam") or "").lower()
               for it in data["items"])


def test_index_geeft_html(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "PlantWijs" in r.text


def test_legacy_geeft_html(client: TestClient):
    r = client.get("/legacy")
    assert r.status_code == 200
    assert "<!doctype html>" in r.text.lower()


def test_context_onbekende_categorie_404(client: TestClient):
    # Sinds WP2b is /api/context geïmplementeerd; alleen een onbekende
    # categorie (of lege waarde) geeft nog 404. De happy path staat in
    # tests/test_advies.py.
    r = client.get("/api/context", params={"category": "bestaatniet", "value": "x"})
    assert r.status_code == 404
    assert r.json() == {"error": "not_found"}


def test_pdf_route_bestaat(client: TestClient):
    # Sinds WP4 geeft /advies/pdf een echt rapport in plaats van de 501-stub.
    # Het genereren zelf staat in tests/test_report.py (met gemockte kaartbronnen);
    # hier alleen de contractcheck die zonder netwerk kan: lat/lon zijn verplicht.
    assert client.get("/advies/pdf").status_code == 422
    assert any(r.path == "/advies/pdf" for r in app.routes if hasattr(r, "path"))


def test_admin_reload_zonder_key(client: TestClient):
    r = client.get("/api/admin/reload", params={"key": "fout"})
    assert r.status_code == 401

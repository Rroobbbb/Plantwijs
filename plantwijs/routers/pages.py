"""Pagina-routes: / (nieuwe frontend als die er is) en /legacy (oude UI)."""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ..config import INDEX_HTML, LEGACY_HTML, NO_STORE_HEADERS

router = APIRouter(tags=["pages"])


def _read_html(path: str) -> str:
    # newline="" → geen newline-vertaling, zodat de output byte-identiek blijft.
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def _html_response(path: str) -> HTMLResponse:
    if not os.path.exists(path):
        return HTMLResponse(
            content="<!doctype html><meta charset=utf-8><title>Beplantingswijzer</title>"
                    "<p>Frontend-bestand niet gevonden.</p>",
            status_code=404,
            headers=dict(NO_STORE_HEADERS),
        )
    return HTMLResponse(content=_read_html(path), headers=dict(NO_STORE_HEADERS))


@router.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Nieuwe frontend (static/index.html) zodra WP3 die levert, anders de legacy-UI."""
    path = INDEX_HTML if os.path.exists(INDEX_HTML) else LEGACY_HTML
    return _html_response(path)


@router.get("/legacy", response_class=HTMLResponse)
def legacy() -> HTMLResponse:
    """Altijd de oude, uit api.py geëxtraheerde UI."""
    return _html_response(LEGACY_HTML)

"""Compat-shim voor PlantWijs.

De applicatie is verhuisd naar het package `plantwijs/` (zie docs/PLAN.md).
Dit bestand blijft bestaan zodat bestaande startcommando's blijven werken:

    uvicorn api:app --reload --port 9000

Nieuwe code importeert bij voorkeur rechtstreeks:

    from plantwijs.main import app, create_app
"""

from __future__ import annotations

from plantwijs.main import app, create_app

__all__ = ["app", "create_app"]

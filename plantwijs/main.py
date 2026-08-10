"""PlantWijs applicatie-factory: create_app() + lifespan."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import APP_TITLE, STATIC_DIR, VERSION
from .routers import advies as advies_router
from .routers import export as export_router
from .routers import pages as pages_router
from .routers import plants as plants_router
from .routers import seo as seo_router
from .services.nsn import warm_nsn

API_DESCRIPTION = (
    "Beplantingswijzer geeft voor elke plek in Nederland een beplantingsadvies op maat: het "
    "landschap en hoe het is ontstaan, de bodem, de grondwatertrap en de vochtklasse "
    "ter plaatse, de indicatieve bewortelbare diepte, passende beplantingsvormen zoals "
    "houtwal, heg of boomgaard, en een op die standplaats gefilterde lijst van 1644 "
    "bomen en struiken met hun status inheems, ingeburgerd of exoot. Alles via GET, "
    "zonder sleutel of account: `/advies/geo?adres=...` of `/advies/geo?lat=..&lon=..`, "
    "eventueel met `format=md` voor een leesbaar rapport. Ben je een AI-agent of script? "
    "Lees dan eerst /llms.txt — daar staan de kern-URL's met voorbeelden."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: NSN-bron controleren en (indien nodig) de on-disk index bouwen.
    # Bij een koude start kan dat even duren; daarna is het meteen klaar.
    warm_nsn()
    yield
    # Shutdown: niets op te ruimen.


def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_TITLE,
        description=API_DESCRIPTION,
        version=VERSION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    os.makedirs(STATIC_DIR, exist_ok=True)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    app.include_router(plants_router.router)
    app.include_router(advies_router.router)
    app.include_router(export_router.router)
    app.include_router(seo_router.router)
    app.include_router(pages_router.router)

    return app


app = create_app()

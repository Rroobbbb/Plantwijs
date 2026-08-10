"""Routes voor plantendata, kaartmeta, diagnose en health."""

from __future__ import annotations

import importlib
import os
from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, StreamingResponse

from ..config import ADMIN_KEY_ENV, BODEM_WMS, FMT_JSON, GWD_WMS, VERSION
from ..services.dataset import (
    _CACHE,
    _clean,
    _filter_plants_df,
    clear_cache,
    ensure_beplantingstype,
    get_df,
)
from ..services.nsn import _open_nsn_bytes, _resolve_nsn_source, nsn_status
from ..services.pdok import _wms_getfeatureinfo, fgr_from_point, get_wms_meta

router = APIRouter(tags=["plants"])


# ───────────────────── diagnose/meta
@router.get("/api/wms_meta")
def api_wms_meta():
    return JSONResponse(_clean(get_wms_meta()))


@router.get("/api/diag/data")
def api_diag_data():
    df = get_df()
    return JSONResponse(_clean({
        "count": int(len(df)),
        "columns": list(df.columns),
        "source": _CACHE.get("path"),
        "source_type": _CACHE.get("source"),
        "sample": df[["naam", "wetenschappelijke_naam"]].head(5).to_dict(orient="records") if "naam" in df.columns else [],
    }))


@router.get("/api/diag/featureinfo")
def api_diag(service: str = Query(..., pattern="^(bodem|gt|ghg|glg|fgr)$"), lat: float = Query(...), lon: float = Query(...)):
    if service == "fgr":
        return JSONResponse({"fgr": fgr_from_point(lat, lon)})
    base = {"bodem": BODEM_WMS, "gt": GWD_WMS, "ghg": GWD_WMS, "glg": GWD_WMS}[service]
    layer = get_wms_meta().get(service, {}).get("layer")
    props = _wms_getfeatureinfo(base, layer, lat, lon)
    return JSONResponse(_clean({"base": base, "layer": layer, "props": props}))


def _pdf_beschikbaar() -> bool:
    """Kan de server een PDF-rapport bouwen?

    Waar zodra `services.report` importeert; dat vereist reportlab en Pillow.
    De frontend gebruikt dit veld om de PDF-knop aan of uit te zetten, zodat
    daar geen mislukte probe-request meer voor nodig is.
    """
    try:
        importlib.import_module("plantwijs.services.report")
        return True
    except Exception as e:
        print("[HEALTH] PDF-rapport niet beschikbaar:", e)
        return False


@router.get("/api/health")
def api_health():
    """Snelle statuscheck; doet geen netwerk-calls en bouwt geen NSN-index."""
    ok = True
    try:
        df = get_df()
        dataset = {"rows": int(len(df)), "source": str(_CACHE.get("path") or "")}
    except Exception as e:
        ok = False
        dataset = {"rows": 0, "source": f"fout: {e}"}
    return JSONResponse(_clean({
        "ok": ok,
        "dataset": dataset,
        "nsn": {"status": nsn_status()},
        "pdf_beschikbaar": _pdf_beschikbaar(),
        "versie": VERSION,
    }))


@router.get("/api/nsn")
def api_nsn():
    """
    Retourneer GeoJSON voor Natuurlijk Systeem Nederland (NSN) als vectorlaag.

    Belangrijk: dit bestand is erg groot. Daarom streamen we de bytes (geen json.load in RAM).
    Bron:
      - data/nsn_natuurlijk_systeem.geojson (dev), of
      - een .zip in data/ met een .geojson erin (prod), bijv. data/LBK_BKNSN_2023.zip
    """
    kind, path, member = _resolve_nsn_source()
    if kind == "missing":
        return JSONResponse({"error": "nsn_source_not_found"}, status_code=404)

    def _iter_bytes():
        try:
            with _open_nsn_bytes() as bf:
                while True:
                    chunk = bf.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            # Stream errors zijn lastig aan client te melden; loggen is het best wat kan.
            print("[NSN] stream fout:", e)
            return

    return StreamingResponse(_iter_bytes(), media_type=FMT_JSON)


# ───────────────────── data
@router.get("/api/plants")
def api_plants(
    q: str = Query(""),
    inheems_only: bool = Query(False),
    toon_inheems: Optional[bool] = Query(None),
    toon_ingeburgerd: Optional[bool] = Query(None),
    toon_exoot: Optional[bool] = Query(None),
    exclude_invasief: bool = Query(True),
    licht: List[str] = Query(default=[]),
    vocht: List[str] = Query(default=[]),
    bodem: List[str] = Query(default=[]),
    beplantingstype: List[str] = Query(default=[]),
    limit: Optional[int] = Query(None),  # genegeerd → geen limiet
    sort: str = Query("naam"),
    desc: bool = Query(False),
):
    df = _filter_plants_df(q, inheems_only, toon_inheems, toon_ingeburgerd, toon_exoot, exclude_invasief, licht, vocht, bodem, beplantingstype, sort, desc)
    # Zorg dat beplantingstype kolom bestaat voor UI
    df = ensure_beplantingstype(df)
    cols = [c for c in (
        "naam", "wetenschappelijke_naam", "nederlandse_naam", "beplantingstype", "status_nl", "invasief",
        "standplaats_licht", "vocht", "bodem",
        "ellenberg_l", "ellenberg_f", "ellenberg_t", "ellenberg_n", "ellenberg_r", "ellenberg_s",
        "ellenberg_l_min", "ellenberg_l_max", "ellenberg_f_min", "ellenberg_f_max",
        "ellenberg_t_min", "ellenberg_t_max", "ellenberg_n_min", "ellenberg_n_max",
        "ellenberg_r_min", "ellenberg_r_max", "ellenberg_s_min", "ellenberg_s_max",
        "hoogte", "breedte", "winterhardheidszone", "grondsoorten", "ecowaarde"
    ) if c in df.columns]
    items = df[cols].to_dict(orient="records")
    return JSONResponse(_clean({"count": int(len(df)), "items": items}))


# ───────────────────── admin
@router.get("/api/admin/reload")
def api_admin_reload(key: str = Query(...)):
    """Wist de dataset-cache en laadt de CSV opnieuw.
    Beveiligd met een simpele key in env: PLANTWIJS_ADMIN_KEY
    """
    admin_key = os.getenv(ADMIN_KEY_ENV, "")
    if not admin_key or key != admin_key:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    try:
        clear_cache()
        get_df()  # meteen opnieuw inlezen zodat de eerste request niet wacht
        return JSONResponse({"ok": True, "msg": "dataset cache cleared/refreshed"})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

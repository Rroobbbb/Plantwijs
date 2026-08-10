"""Export-routes: /export/csv, /export/xlsx en /advies/pdf."""

from __future__ import annotations

import io
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Query
from fastapi.responses import Response, StreamingResponse

from ..services.dataset import _filter_plants_df, rapport_status_defaults
from ..services.report import BESTANDSNAAM, maak_rapport

router = APIRouter(tags=["export"])


@router.get("/export/csv")
def export_csv(
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
    sort: str = Query("naam"),
    desc: bool = Query(False),
):
    df = _filter_plants_df(q, inheems_only, toon_inheems, toon_ingeburgerd, toon_exoot, exclude_invasief, licht, vocht, bodem, beplantingstype, sort, desc)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    filename = "beplantingswijzer_export.csv"
    return StreamingResponse(iter([buf.getvalue()]),
                             media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/export/xlsx")
def export_xlsx(
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
    sort: str = Query("naam"),
    desc: bool = Query(False),
):
    df = _filter_plants_df(q, inheems_only, toon_inheems, toon_ingeburgerd, toon_exoot, exclude_invasief, licht, vocht, bodem, beplantingstype, sort, desc)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="Beplantingswijzer")
    buf.seek(0)
    filename = "beplantingswijzer_export.xlsx"
    return StreamingResponse(buf,
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/advies/pdf")
def advies_pdf(
    lat: float = Query(...),
    lon: float = Query(...),
    inheems_only: bool = Query(False),
    toon_inheems: Optional[bool] = Query(None),
    toon_ingeburgerd: Optional[bool] = Query(None),
    toon_exoot: Optional[bool] = Query(None),
    exclude_invasief: bool = Query(True),
    licht: List[str] = Query(default=[]),
    vocht: List[str] = Query(default=[]),
    bodem: List[str] = Query(default=[]),
    beplantingstype: List[str] = Query(default=[]),
):
    """PDF-locatierapport voor één punt (docs/API.md § GET /advies/pdf).

    Zelfde parameters als /advies/geo, plus de filters van /api/plants. Een
    ontbrekende of ongeldige lat/lon levert de standaard 422 van FastAPI op;
    een uitgevallen kaartbron levert "niet gevonden" in het rapport op en
    nooit een 500 (zie services/report.py).

    Worden er géén `toon_*`-parameters meegegeven, dan gebruikt het rapport de
    standaardkeuze van de website: inheems en ingeburgerd aan, exoot uit.
    Expliciete parameters winnen altijd.
    """
    toon_inheems, toon_ingeburgerd, toon_exoot = rapport_status_defaults(
        toon_inheems, toon_ingeburgerd, toon_exoot)
    pdf = maak_rapport(
        lat, lon,
        inheems_only=inheems_only,
        toon_inheems=toon_inheems,
        toon_ingeburgerd=toon_ingeburgerd,
        toon_exoot=toon_exoot,
        exclude_invasief=exclude_invasief,
        licht=licht,
        vocht=vocht,
        bodem=bodem,
        beplantingstype=beplantingstype,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{BESTANDSNAAM}"',
            "Content-Length": str(len(pdf)),
            "Cache-Control": "no-store",
        },
    )

"""Advies-routes: /advies/geo en /api/context."""

from __future__ import annotations

import time
import urllib.parse
from typing import Any, Callable, Dict, Optional, Tuple

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from ..services.advies import verrijk_advies
from ..services.context import beschrijf, categorieen
from ..services.dataset import (
    _apply_status_nl_filter,
    _clean,
    ensure_beplantingstype,
    filter_standplaats,
    get_df,
    rapport_status_defaults,
    status_filter_labels,
)
from ..services.geocode import zoek_adres
from ..services.nsn import nsn_from_point, nsn_status
from ..services.pdok import (
    RUWE_BODEM_KEY,
    ahn_from_wms,
    bodem_from_bodemkaart,
    fgr_from_point,
    gmm_from_wms,
    vocht_from_gwt,
)
from ..services.rapport_md import rapport_markdown

router = APIRouter(tags=["advies"])


def _veilig(bron: str, status: Dict[str, str], fn: Callable[[], Any], leeg: Any) -> Any:
    """Voer een bronlookup uit en noteer de status; nooit een exception naar buiten.

    Eén kapotte PDOK/NSN-bron mag volgens docs/API.md nooit een 500 opleveren.
    `fout` betekent: de lookup gooide een exception. `leeg`: de bron antwoordde,
    maar zonder bruikbare waarde.
    """
    try:
        waarde = fn()
    except Exception as e:
        print(f"[ADVIES] bron '{bron}' faalde:", e)
        status[bron] = "fout"
        return leeg
    hoofdwaarde = waarde[0] if isinstance(waarde, tuple) else waarde
    status[bron] = "ok" if hoofdwaarde not in (None, "") else "leeg"
    return waarde


def _links(request: Request, vocht: Any, bodem: Any, exclude_invasief: bool) -> Tuple[str, str, str]:
    """(basis-url, csv-url, json-url) voor de verwijzingen in het md-rapport.

    De basis komt uit `request.base_url`, zodat de links kloppen op localhost,
    op Render en achter een eigen domein.
    """
    try:
        basis = str(request.base_url).rstrip("/")
    except Exception:
        return "", "", ""

    csv_params = [("exclude_invasief", "true" if exclude_invasief else "false")]
    if vocht:
        csv_params.append(("vocht", str(vocht)))
    if bodem:
        csv_params.append(("bodem", str(bodem)))
    csv_url = f"{basis}/export/csv?{urllib.parse.urlencode(csv_params)}"

    try:
        json_params = [(k, v) for k, v in request.query_params.multi_items() if k != "format"]
    except Exception:
        json_params = []
    json_params.append(("format", "json"))
    json_url = f"{basis}/advies/geo?{urllib.parse.urlencode(json_params)}"
    return basis, csv_url, json_url


@router.get(
    "/advies/geo",
    summary="Volledig beplantingsadvies voor één locatie in Nederland",
    description=(
        "Geeft voor één punt het complete locatieprofiel (fysisch-geografische regio, "
        "bodem, grondwatertrap en vochtklasse, maaiveldhoogte, geomorfologie en "
        "natuurlijk systeem), het bijbehorende landschapsverhaal, de indicatieve "
        "bewortelbare diepte, passende beplantingsvormen en een op de standplaats "
        "gefilterde soortenlijst.\n\n"
        "Geef de locatie op als `lat` + `lon` (WGS84, decimale graden) óf als `adres` "
        "(server-side geocoding via de PDOK Locatieserver). Worden beide meegegeven, "
        "dan winnen `lat`/`lon`. Zonder locatie volgt een 422, bij een adres zonder "
        "treffer een 404.\n\n"
        "Met `format=md` komt hetzelfde advies terug als leesbaar Markdown-rapport "
        "(`text/markdown`) — handig voor AI-agents en voor direct gebruik in een "
        "document. `format=json` (standaard) geeft de JSON hierboven. Zie /llms.txt.\n\n"
        "Zonder `toon_*`-parameters toont het Markdown-rapport, net als de website, "
        "inheemse en ingeburgerde soorten en geen exoten; `format=json` toont dan "
        "alle soorten. Opgegeven `toon_*`-parameters winnen in beide gevallen."
    ),
    responses={
        200: {"content": {"application/json": {}, "text/markdown": {}}},
        404: {"description": "adres_niet_gevonden — geen enkele treffer voor `adres`"},
        422: {"description": "locatie_ontbreekt — geef lat+lon of adres op"},
    },
)
def advies_geo(
    request: Request,
    lat: Optional[float] = Query(None, description="Breedtegraad (WGS84, decimale graden), bijv. 52.078"),
    lon: Optional[float] = Query(None, description="Lengtegraad (WGS84, decimale graden), bijv. 5.89"),
    adres: Optional[str] = Query(None, description="Adres of plaatsnaam in Nederland, bijv. 'Loenenseweg 1 Beekbergen'. Alternatief voor lat/lon."),
    format: str = Query("json", description="`json` (standaard) of `md` voor een Markdown-rapport."),
    inheems_only: bool = Query(False),
    toon_inheems: Optional[bool] = Query(None),
    toon_ingeburgerd: Optional[bool] = Query(None),
    toon_exoot: Optional[bool] = Query(None),
    exclude_invasief: bool = Query(True),
    limit: Optional[int] = Query(None),  # genegeerd
):
    t0 = time.time()
    bronnen_status: Dict[str, str] = {}

    fmt = str(format or "json").strip().lower()

    # ── locatie bepalen: lat/lon wint, anders adres, anders 422
    adres_gevonden: Optional[str] = None
    if lat is None or lon is None:
        if str(adres or "").strip():
            treffer = zoek_adres(adres or "")
            if not treffer:
                return JSONResponse({"error": "adres_niet_gevonden"}, status_code=404)
            lat = float(treffer["lat"])
            lon = float(treffer["lon"])
            adres_gevonden = treffer["adres_gevonden"]
        else:
            return JSONResponse(
                {
                    "error": "locatie_ontbreekt",
                    "detail": (
                        "Geef een locatie op: lat én lon (WGS84, decimale graden) of "
                        "adres. Bijvoorbeeld /advies/geo?lat=52.078&lon=5.89 of "
                        "/advies/geo?adres=Domplein 1 Utrecht."
                    ),
                },
                status_code=422,
            )

    fgr = _veilig("fgr", bronnen_status, lambda: fgr_from_point(lat, lon), None) or "Onbekend"
    nsn_val = _veilig("nsn", bronnen_status, lambda: nsn_from_point(lat, lon), None)
    if bronnen_status.get("nsn") == "leeg":
        try:
            if nsn_status() == "ontbreekt":
                bronnen_status["nsn"] = "ontbreekt"
        except Exception:
            bronnen_status["nsn"] = "ontbreekt"

    bodem_raw, _props_bodem = _veilig(
        "bodem", bronnen_status, lambda: bodem_from_bodemkaart(lat, lon), (None, {}))
    vocht_raw, _props_gwt, gt_code = _veilig(
        "gwt", bronnen_status, lambda: vocht_from_gwt(lat, lon), (None, {}, None))
    ahn_val, _props_ahn = _veilig(
        "ahn", bronnen_status, lambda: ahn_from_wms(lat, lon), (None, {}))
    gmm_val, _props_gmm = _veilig(
        "gmm", bronnen_status, lambda: gmm_from_wms(lat, lon), (None, {}))

    bodem_val = bodem_raw
    vocht_val = vocht_raw

    # De ruwe bodemkaart-term is voor de uitleg in de UI waardevol ("Petgaten"),
    # maar filteren doen we op de gecanoniseerde categorie. Alleen meesturen als
    # hij iets toevoegt (zie services/pdok.py → RUWE_BODEM_KEY).
    bodem_detail: Optional[str] = None
    if isinstance(_props_bodem, dict):
        ruw = str(_props_bodem.get(RUWE_BODEM_KEY) or "").strip()
        if ruw and ruw.lower() != str(bodem_val or "").strip().lower():
            bodem_detail = ruw

    # Rapporten (format=md) volgen de standaardkeuze van de website; JSON blijft
    # ongewijzigd "alles tonen" als er niets is meegegeven (backwards compat).
    if fmt in ("md", "markdown"):
        toon_inheems, toon_ingeburgerd, toon_exoot = rapport_status_defaults(
            toon_inheems, toon_ingeburgerd, toon_exoot)
    statusfilters = status_filter_labels(
        inheems_only, toon_inheems, toon_ingeburgerd, toon_exoot)

    df = get_df()
    df = _apply_status_nl_filter(df, inheems_only, toon_inheems, toon_ingeburgerd, toon_exoot)
    if exclude_invasief and "invasief" in df.columns:
        df = df[(df["invasief"].astype(str).str.lower() != "ja") | (df["invasief"].isna())]

    df = filter_standplaats(
        df,
        vocht=[vocht_val] if vocht_val else [],
        bodem=[bodem_val] if bodem_val else [],
    )

    # beplantingstype + status_nl horen bij de itemvorm van /api/plants en zijn
    # de kolommen "Type" en "Status" in het md-rapport.
    df = ensure_beplantingstype(df)
    cols = [c for c in (
        "naam", "wetenschappelijke_naam", "nederlandse_naam", "beplantingstype",
        "status_nl", "inheems", "invasief",
        "standplaats_licht", "vocht", "bodem",
        "ellenberg_l", "ellenberg_f", "ellenberg_t", "ellenberg_n", "ellenberg_r", "ellenberg_s",
        "hoogte", "breedte", "winterhardheidszone", "grondsoorten", "ecowaarde"
    ) if c in df.columns]
    items = df[cols].to_dict(orient="records")

    out = {
        "fgr": fgr,
        "bodem": bodem_val,
        # ── additief: de ruwe kaartterm als die afwijkt van de categorie
        "bodem_detail": bodem_detail,
        "bodem_bron": "BRO Bodemkaart WMS" if bodem_raw else "onbekend",
        "gt_code": gt_code,
        "vocht": vocht_raw,
        "vocht_bron": "BRO Gt/GLG WMS" if vocht_raw else "onbekend",
        "ahn": ahn_val,
        "ahn_bron": "PDOK AHN WMS (DTM 0.5m)" if ahn_val else "onbekend",
        "gmm": gmm_val,
        "gmm_bron": "BRO Geomorfologische kaart (GMM) WMS" if gmm_val else "onbekend",
        "nsn": nsn_val,
        "advies": items,
        # ── additief (WP6): waar dit advies over gaat
        "locatie": {"adres_gevonden": adres_gevonden, "lat": lat, "lon": lon},
        "elapsed_ms": int((time.time()-t0)*1000),
    }

    # ── additief (WP2b): kennislaag + bronstatus
    try:
        out.update(verrijk_advies(
            fgr=None if fgr == "Onbekend" else fgr,
            nsn=nsn_val,
            gmm=gmm_val,
            bodem=bodem_val,
            vocht=vocht_val,
            gt_code=gt_code,
        ))
    except Exception as e:  # kennislaag mag de rest nooit slopen
        print("[ADVIES] kennislaag faalde:", e)
        out.setdefault("landschap", {})
        out.setdefault("wortelbare_diepte", None)
        out.setdefault("aanbevolen_beplanting", [])
    out["bronnen_status"] = bronnen_status
    out["elapsed_ms"] = int((time.time()-t0)*1000)

    data = _clean(out)

    # ── additief (WP6): hetzelfde advies als leesbaar Markdown-rapport
    if fmt in ("md", "markdown"):
        basis, csv_url, json_url = _links(request, vocht_val, bodem_val, exclude_invasief)
        try:
            markdown = rapport_markdown(
                data, basis_url=basis, csv_url=csv_url, json_url=json_url,
                statusfilters=statusfilters)
        except Exception as e:  # rapportopmaak mag het advies nooit slopen
            print("[ADVIES] markdown-rapport faalde:", e)
            return JSONResponse(data)
        return PlainTextResponse(markdown, media_type="text/markdown; charset=utf-8")

    return JSONResponse(data)


@router.get("/api/context")
def api_context(
    category: str = Query(...),
    value: str = Query(...),
):
    """Landschapsverhaal per kaartwaarde (content/context_descriptions.yaml).

    Onbekende categorie of geen passende entry ⇒ 404 {"error": "not_found"}.
    Een onbekende waarde die op de fallback-entry uitkomt is een geldig
    resultaat en wordt gewoon teruggegeven.
    """
    cat = str(category or "").strip().lower()
    if cat not in categorieen() or not str(value or "").strip():
        return JSONResponse({"error": "not_found"}, status_code=404)
    data = beschrijf(cat, value)
    if not data:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(_clean(data))

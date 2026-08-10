"""Tests voor het PDF-locatierapport (WP4).

Er gaat geen netwerkverkeer aan te pas: de PDOK/NSN-lookups én het ophalen van
de OSM-tiles worden gemonkeypatcht, net als in tests/test_advies.py.

Om de inhoud van het rapport te kunnen controleren zit hier een kleine
tekstextractor in: reportlab schrijft zijn content-streams als ASCII85 +
Flate, met WinAnsi-tekst. Dat is genoeg om te controleren of de juiste
secties, waarden en soorten in de PDF staan.
"""

from __future__ import annotations

import base64
import os
import re
import sys
import zlib
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plantwijs.main import app  # noqa: E402
from plantwijs.services import report  # noqa: E402

PDF_MAGIC = b"%PDF"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# ───────────────────── mocks (geen netwerk)
def _mock_bronnen(monkeypatch, *, fgr="Hogere zandgronden", nsn="Dekzandrug",
                  bodem=("zand", {}), gwt=("droog", {}, "VIo"),
                  ahn=("12.34", {}), gmm=("Dekzandrug", {})):
    def _of_raise(waarde):
        def _fn(*_a, **_k):
            if isinstance(waarde, Exception):
                raise waarde
            return waarde
        return _fn

    monkeypatch.setattr(report, "fgr_from_point", _of_raise(fgr))
    monkeypatch.setattr(report, "nsn_from_point", _of_raise(nsn))
    monkeypatch.setattr(report, "bodem_from_bodemkaart", _of_raise(bodem))
    monkeypatch.setattr(report, "vocht_from_gwt", _of_raise(gwt))
    monkeypatch.setattr(report, "ahn_from_wms", _of_raise(ahn))
    monkeypatch.setattr(report, "gmm_from_wms", _of_raise(gmm))


def _tegel_png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (256, 256), (226, 234, 224)).save(buf, format="PNG")
    return buf.getvalue()


def _mock_tiles(monkeypatch, *, gedrag="ok"):
    """`ok` levert een neptegel, `leeg` een 404-achtig antwoord, `fout` een exception."""
    def _fn(_z, _x, _y):
        if gedrag == "fout":
            raise ConnectionError("tile-server onbereikbaar")
        if gedrag == "leeg":
            return None
        return _tegel_png()

    monkeypatch.setattr(report, "_tile_png", _fn)


# ───────────────────── mini PDF-tekstextractie
_PDF_STRING = re.compile(rb"\((?:[^()\\]|\\.)*\)", re.S)
_OCTAAL = re.compile(rb"[0-7]{1,3}")


def _unescape(ruw: bytes) -> str:
    uit = bytearray()
    i = 0
    while i < len(ruw):
        if ruw[i] == 0x5C and i + 1 < len(ruw):  # backslash
            m = _OCTAAL.match(ruw, i + 1)
            if m:
                uit.append(int(m.group(0), 8) & 0xFF)
                i = m.end()
                continue
            uit.append(ruw[i + 1])
            i += 2
            continue
        uit.append(ruw[i])
        i += 1
    return uit.decode("cp1252", errors="replace")


def _pdf_tekst(pdf: bytes) -> str:
    delen = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        blok = m.group(1)
        try:
            blok = base64.a85decode(blok.strip(), adobe=True)
        except Exception:
            pass
        try:
            blok = zlib.decompress(blok)
        except Exception:
            pass
        if b"Tj" not in blok and b"TJ" not in blok:
            continue
        delen.extend(_unescape(s[1:-1]) for s in _PDF_STRING.findall(blok))
    return " ".join(delen)


def _paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


def _is_geldige_pdf(pdf: bytes) -> bool:
    return pdf.startswith(PDF_MAGIC) and pdf.rstrip().endswith(b"%%EOF") and _paginas(pdf) >= 1


# ───────────────────── (a) endpoint levert een PDF
def test_pdf_endpoint_geeft_pdf(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    _mock_tiles(monkeypatch)
    r = client.get("/advies/pdf", params={"lat": 52.078, "lon": 5.89})

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.headers["content-disposition"] == 'attachment; filename="beplantingswijzer_rapport.pdf"'
    assert r.content.startswith(PDF_MAGIC)
    assert _is_geldige_pdf(r.content)
    assert len(r.content) > 20_000  # met kaart erin


def test_pdf_bevat_alle_secties(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    _mock_tiles(monkeypatch)
    tekst = _pdf_tekst(client.get("/advies/pdf",
                                  params={"lat": 52.078, "lon": 5.89}).content)

    for kop in ("Beplantingswijzer — Locatierapport", "Jouw plek", "Jouw landschap",
                "Wortelruimte", "Wat kun jij doen", "Passende soorten",
                "Over dit rapport", "Gebruikte bronnen"):
        assert kop in tekst, kop

    # kop: coördinaten met 5 decimalen + paginanummering
    assert "52.07800, 5.89000" in tekst
    assert "pagina 1 van" in tekst

    # locatieprofiel met bronvermelding
    assert "Hogere zandgronden" in tekst
    assert "12.34 m t.o.v. NAP" in tekst
    assert "grondwatertrap VIo" in tekst
    assert "BRO Bodemkaart WMS" in tekst
    assert "BKNSN 2023" in tekst

    # kennislaag + kaartattributie + disclaimer
    assert "Zo versterk je dit landschap" in tekst
    assert "OpenStreetMap" in tekst
    assert "kaartinterpretatie" in tekst
    assert "CSV-export" in tekst


# ───────────────────── (b) rapport zonder enkele brondata
def test_rapport_zonder_brondata(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch, fgr=None, nsn=None, bodem=(None, {}),
                  gwt=(None, {}, None), ahn=(None, {}), gmm=(None, {}))
    _mock_tiles(monkeypatch)
    r = client.get("/advies/pdf", params={"lat": 52.078, "lon": 5.89})

    assert r.status_code == 200
    assert _is_geldige_pdf(r.content)
    tekst = _pdf_tekst(r.content)
    assert tekst.count("niet gevonden") == 6      # elke regel van "Jouw plek"
    assert "onbekend" in tekst.lower()            # fallback-verhalen uit de kennislaag
    assert "Passende soorten" in tekst            # de soortentabel blijft staan


def test_kapotte_bron_geeft_geen_500(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch,
                  bodem=RuntimeError("PDOK plat"),
                  nsn=RuntimeError("index stuk"))
    _mock_tiles(monkeypatch)
    r = client.get("/advies/pdf", params={"lat": 52.078, "lon": 5.89})

    assert r.status_code == 200
    assert _is_geldige_pdf(r.content)
    tekst = _pdf_tekst(r.content)
    assert "niet gevonden" in tekst
    assert "Hogere zandgronden" in tekst  # de bronnen die het wél deden blijven staan


def test_kennislaag_kapot_geeft_geen_500(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    _mock_tiles(monkeypatch)
    monkeypatch.setattr(report, "verrijk_advies",
                        lambda **_k: (_ for _ in ()).throw(RuntimeError("yaml stuk")))
    r = client.get("/advies/pdf", params={"lat": 52.078, "lon": 5.89})

    assert r.status_code == 200
    assert _is_geldige_pdf(r.content)
    assert "Passende soorten" in _pdf_tekst(r.content)


# ───────────────────── (c) soortentabel respecteert de filters
def _profiel() -> dict:
    return {"fgr": "Hogere zandgronden", "nsn": "Dekzandrug", "bodem": "zand",
            "vocht": "droog", "gt_code": "VIo", "ahn": "12.34", "gmm": "Dekzandrug"}


# Zonder toon_*-parameters gebruikt /advies/pdf de standaardkeuze van de
# website: inheems + ingeburgerd, geen exoten (services.dataset →
# rapport_status_defaults). Wie report._soorten rechtstreeks aanroept moet dat
# dus meegeven om dezelfde selectie te krijgen als het endpoint.
RAPPORT_STATUS = {"toon_inheems": True, "toon_ingeburgerd": True, "toon_exoot": False}


def _eerste_schaduwsoort() -> str:
    """Een soort in de top-40 van het rapport die géén 'zon' verdraagt."""
    df, _ = report._soorten(
        _profiel(), inheems_only=False, **RAPPORT_STATUS,
        exclude_invasief=True, licht=[], vocht=[], bodem=[],
        beplantingstype=[])
    for _, r in df.head(report.MAX_SOORTEN).iterrows():
        if "zon" not in str(r.get("standplaats_licht", "")).lower():
            return str(r.get("naam"))
    return ""


def test_soortentabel_respecteert_licht_filter(client: TestClient, monkeypatch):
    schaduwsoort = _eerste_schaduwsoort()
    assert schaduwsoort, "dataset zonder schaduwsoort in de top-40; test niet zinvol"

    _mock_bronnen(monkeypatch)
    _mock_tiles(monkeypatch)
    params = {"lat": 52.078, "lon": 5.89}

    zonder = _pdf_tekst(client.get("/advies/pdf", params=params).content)
    met = _pdf_tekst(client.get("/advies/pdf",
                                params={**params, "licht": "zon"}).content)

    assert schaduwsoort in zonder
    assert schaduwsoort not in met
    assert "licht: zon" in met


def test_soortentabel_maximaal_40_rijen(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    _mock_tiles(monkeypatch)
    df, gebruikt = report._soorten(
        _profiel(), inheems_only=False, **RAPPORT_STATUS,
        exclude_invasief=True, licht=[], vocht=[], bodem=[],
        beplantingstype=[])

    # zonder eigen filters gelden de kaartwaarden, net als bij /advies/geo
    assert gebruikt["vocht"] == ["droog"]
    assert gebruikt["bodem"] == ["zand"]
    assert len(df) > report.MAX_SOORTEN

    tekst = _pdf_tekst(client.get("/advies/pdf",
                                  params={"lat": 52.078, "lon": 5.89}).content)
    assert f"{report.MAX_SOORTEN} van de {len(df)} soorten" in tekst
    # elke soort in de tabel staat maar één keer in de PDF
    namen = [str(n) for n in df.head(report.MAX_SOORTEN)["naam"]]
    assert len(namen) == report.MAX_SOORTEN
    assert all(n in tekst for n in namen)


def test_eigen_vochtfilter_overschrijft_de_kaartwaarde():
    _df, gebruikt = report._soorten(
        _profiel(), inheems_only=False, toon_inheems=None, toon_ingeburgerd=None,
        toon_exoot=None, exclude_invasief=True, licht=[], vocht=["nat"],
        bodem=[], beplantingstype=[])
    assert gebruikt["vocht"] == ["nat"]
    assert gebruikt["bodem"] == ["zand"]  # bodem blijft van de kaart komen


# ───────────────────── (c2) statusfilters: site-defaults in het rapport
def test_pdf_zonder_statusparams_gebruikt_site_defaults(client: TestClient, monkeypatch):
    """Geen toon_*-parameters ⇒ inheems + ingeburgerd, geen exoten."""
    _mock_bronnen(monkeypatch)
    _mock_tiles(monkeypatch)
    tekst = _pdf_tekst(client.get("/advies/pdf",
                                  params={"lat": 52.078, "lon": 5.89}).content)

    assert "status: inheems, ingeburgerd" in tekst

    df, _ = report._soorten(
        _profiel(), inheems_only=False, **RAPPORT_STATUS, exclude_invasief=True,
        licht=[], vocht=[], bodem=[], beplantingstype=[])
    assert f"{report.MAX_SOORTEN} van de {len(df)} soorten" in tekst
    statussen = {str(s).strip().lower() for s in df["status_nl"].head(200)}
    assert "exoot" not in statussen


def test_pdf_expliciete_statusparams_winnen(client: TestClient, monkeypatch):
    _mock_bronnen(monkeypatch)
    _mock_tiles(monkeypatch)
    tekst = _pdf_tekst(client.get(
        "/advies/pdf",
        params={"lat": 52.078, "lon": 5.89, "toon_exoot": "true"}).content)

    # alleen exoot is meegegeven; inheems/ingeburgerd blijven dus uit
    assert "status: exoot" in tekst
    assert "status: inheems" not in tekst


def test_status_filter_labels():
    from plantwijs.services.dataset import status_filter_labels

    assert status_filter_labels(False, None, None, None) == []
    assert status_filter_labels(False, True, True, False) == ["inheems", "ingeburgerd"]
    assert status_filter_labels(False, False, False, True) == ["exoot"]
    assert status_filter_labels(True, None, None, None) == ["inheems"]


# ───────────────────── (d) kaartfout ⇒ nog steeds een geldige PDF
@pytest.mark.parametrize("gedrag", ["fout", "leeg"])
def test_kaartfout_geeft_toch_geldige_pdf(client: TestClient, monkeypatch, gedrag: str):
    _mock_bronnen(monkeypatch)
    _mock_tiles(monkeypatch, gedrag=gedrag)
    r = client.get("/advies/pdf", params={"lat": 52.078, "lon": 5.89})

    assert r.status_code == 200
    assert _is_geldige_pdf(r.content)
    tekst = _pdf_tekst(r.content)
    assert "Kaartuitsnede niet beschikbaar" in tekst
    assert "Jouw plek" in tekst  # de rest van het rapport staat er gewoon


def test_kaart_wordt_ingesloten_als_de_tiles_werken(monkeypatch):
    _mock_bronnen(monkeypatch)
    _mock_tiles(monkeypatch)
    met_kaart = report.maak_rapport(52.078, 5.89)

    _mock_tiles(monkeypatch, gedrag="fout")
    zonder_kaart = report.maak_rapport(52.078, 5.89)

    assert b"/Image" in met_kaart
    assert len(met_kaart) > len(zonder_kaart)
    assert "Kaartuitsnede niet beschikbaar" not in _pdf_tekst(met_kaart)


def test_marker_staat_op_het_punt(monkeypatch):
    """De uitsnede is op de coördinaat gecentreerd, niet op een tilehoek."""
    _mock_tiles(monkeypatch)
    beeld = report._static_map_image(52.078, 5.89)
    assert beeld is not None
    img = Image.open(beeld)
    assert img.size == (report.KAART_PX, report.KAART_PX)
    midden = img.convert("RGB").getpixel((report.KAART_PX // 2, report.KAART_PX // 2))
    assert midden == (29, 92, 63)  # huisstijlgroen van de marker


# ───────────────────── overige contractafspraken
def test_ontbrekende_coordinaten_is_422(client: TestClient):
    assert client.get("/advies/pdf").status_code == 422
    assert client.get("/advies/pdf", params={"lat": 52.078}).status_code == 422
    assert client.get("/advies/pdf", params={"lat": "x", "lon": "y"}).status_code == 422


def test_maak_rapport_geeft_bytes(monkeypatch):
    _mock_bronnen(monkeypatch)
    _mock_tiles(monkeypatch, gedrag="leeg")
    pdf = report.maak_rapport(52.078, 5.89, licht=["zon"], beplantingstype=["boom"])
    assert isinstance(pdf, bytes)
    assert _is_geldige_pdf(pdf)

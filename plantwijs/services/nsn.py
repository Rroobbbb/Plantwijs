"""NSN-service (Natuurlijk Systeem Nederland / BKNSN).

Bron: losse .geojson of een .zip met .geojson in data/.
Lookups gaan via een on-disk SQLite R-tree index (in %TEMP%/plantwijs_nsn),
met een stream-scan als trage fallback.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sqlite3
import threading
import time
import zipfile
import zlib
from contextlib import contextmanager
from typing import List, Optional, Tuple

from ..config import (
    NSN_DATA_DIR,
    NSN_GEOJSON_IS_RD,
    NSN_GEOJSON_PATH,
    NSN_INDEX_DB,
    NSN_INDEX_DIR,
    NSN_ZIP_PATH,
    TX_WGS84_RD,
)

# NSN bron-resolutie (geen full in-memory cache; Render 512MB)
_NSN_SOURCE: Optional[Tuple[str, str, Optional[str]]] = None  # ("geojson"|"zip"|"missing", path, membername)

_NSN_INDEX_LOCK = threading.Lock()


def _resolve_nsn_source() -> Tuple[str, str, Optional[str]]:
    """Bepaal waar NSN-data vandaan komt (losse geojson of zip). Cache alleen metadata."""
    global _NSN_SOURCE
    if _NSN_SOURCE is not None:
        return _NSN_SOURCE

    # 1) Losse geojson (dev)
    if os.path.exists(NSN_GEOJSON_PATH):
        _NSN_SOURCE = ("geojson", NSN_GEOJSON_PATH, None)
        return _NSN_SOURCE

    # 2) ZIP (prod): eerst default, dan elke .zip in data/
    zips: List[str] = []
    if os.path.exists(NSN_ZIP_PATH):
        zips.append(NSN_ZIP_PATH)
    try:
        for fn in os.listdir(NSN_DATA_DIR):
            if fn.lower().endswith(".zip"):
                p = os.path.join(NSN_DATA_DIR, fn)
                if p not in zips:
                    zips.append(p)
    except Exception:
        pass

    for zp in zips:
        try:
            with zipfile.ZipFile(zp, "r") as zf:
                names = zf.namelist()
                geo = [n for n in names if n.lower().endswith(".geojson") or n.lower().endswith(".json")]
                if geo:
                    _NSN_SOURCE = ("zip", zp, geo[0])
                    return _NSN_SOURCE
        except Exception:
            continue

    _NSN_SOURCE = ("missing", "", None)
    return _NSN_SOURCE


@contextmanager
def _open_nsn_bytes():
    """Open de NSN-geojson als bytes-stream (los bestand of uit ZIP)."""
    kind, path, member = _resolve_nsn_source()
    if kind == "geojson":
        f = open(path, "rb")
        try:
            yield f
        finally:
            try:
                f.close()
            except Exception:
                pass
        return

    if kind == "zip":
        zf = zipfile.ZipFile(path, "r")
        bf = zf.open(member, "r")
        try:
            yield bf
        finally:
            try:
                bf.close()
            except Exception:
                pass
            try:
                zf.close()
            except Exception:
                pass
        return

    raise FileNotFoundError("NSN bron niet gevonden. Voeg een .zip met .geojson toe in PlantWijs/data/.")


def _iter_nsn_features():
    """
    Stream features uit een (grote) GeoJSON FeatureCollection zonder alles in RAM te laden.

    We zoeken de 'features' array en decoderen Feature-objecten één voor één met json.JSONDecoder.raw_decode().
    """
    decoder = json.JSONDecoder()
    with _open_nsn_bytes() as bf:
        tf = io.TextIOWrapper(bf, encoding="utf-8", errors="ignore")
        buf = ""
        in_features = False
        pos = 0

        while True:
            chunk = tf.read(1024 * 256)  # 256KB tekst
            if not chunk:
                break
            buf += chunk

            if not in_features:
                idx = buf.find('"features"')
                if idx == -1:
                    # houd buffer beperkt
                    if len(buf) > 2_000_000:
                        buf = buf[-1_000_000:]
                    continue
                # vind de '[' na "features":
                br = buf.find("[", idx)
                if br == -1:
                    continue
                in_features = True
                pos = br + 1

            # decode features
            while True:
                # skip whitespace/commas
                n = len(buf)
                while pos < n and buf[pos] in " \r\n\t,":
                    pos += 1
                if pos >= n:
                    break
                if buf[pos] == "]":
                    return  # einde array

                try:
                    obj, end = decoder.raw_decode(buf, pos)
                    pos = end
                    if isinstance(obj, dict) and obj.get("type") == "Feature":
                        yield obj
                except json.JSONDecodeError:
                    # niet genoeg data in buffer → lees verder
                    break

            # trim buffer om geheugen laag te houden
            if pos > 1_000_000:
                buf = buf[pos:]
                pos = 0


def _point_in_polygon(px: float, py: float, ring) -> bool:
    """
    Standaard ray‑casting point‑in‑polygon test op basis van de buitenring.
    """
    inside = False
    n = len(ring)
    if n < 3:
        return False
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        # Kijk of de horizontale lijn door het segment gaat
        if ((y1 > py) != (y2 > py)):
            x_intersect = (x2 - x1) * (py - y1) / (y2 - y1 + 1e-9) + x1
            if px < x_intersect:
                inside = not inside
    return inside


# ───────────────────── snelle on-disk index
def _nsn_source_signature() -> str:
    """Unieke signature van de NSN-bron zodat we index kunnen hergebruiken."""
    kind, path, member = _resolve_nsn_source()
    if kind == "missing":
        return "missing"
    try:
        st = os.stat(path) if path else None
        mtime = int(st.st_mtime) if st else 0
        size = int(st.st_size) if st else 0
    except Exception:
        mtime = 0
        size = 0
    raw = f"{kind}|{path}|{member or ''}|{mtime}|{size}|RD={int(bool(NSN_GEOJSON_IS_RD))}"
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def _db_connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path, timeout=60)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA temp_store=MEMORY;")
    con.execute("PRAGMA cache_size=-20000;")  # ~20MB cache (negatief = KB)
    return con


def _ensure_nsn_index() -> bool:
    """Zorg dat de NSN index bestaat en bij de huidige bron hoort."""
    kind, _, _ = _resolve_nsn_source()
    if kind == "missing":
        return False

    os.makedirs(NSN_INDEX_DIR, exist_ok=True)
    sig = _nsn_source_signature()

    with _NSN_INDEX_LOCK:
        # snelle check: bestaat DB + meta signature match?
        if os.path.exists(NSN_INDEX_DB):
            try:
                con = _db_connect(NSN_INDEX_DB)
                try:
                    con.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);")
                    row = con.execute("SELECT value FROM meta WHERE key='sig'").fetchone()
                    if row and row[0] == sig:
                        return True
                finally:
                    con.close()
            except Exception:
                pass  # rebuild

        # rebuild
        t0 = time.time()
        try:
            if os.path.exists(NSN_INDEX_DB):
                try:
                    os.remove(NSN_INDEX_DB)
                except Exception:
                    pass
            con = _db_connect(NSN_INDEX_DB)
            try:
                con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);")
                con.execute("CREATE TABLE feats(id INTEGER PRIMARY KEY, label TEXT, geom BLOB, bbox_area REAL);")
                # RTree index op bbox
                con.execute("CREATE VIRTUAL TABLE rtree USING rtree(id, minx, maxx, miny, maxy);")

                def _bbox_of_coords(coords) -> tuple[float, float, float, float] | None:
                    minx = miny = float("inf")
                    maxx = maxy = float("-inf")

                    def _acc(ring):
                        nonlocal minx, miny, maxx, maxy
                        for x, y in ring:
                            if x < minx: minx = x
                            if y < miny: miny = y
                            if x > maxx: maxx = x
                            if y > maxy: maxy = y
                    # coords kan Polygon of MultiPolygon structuur hebben
                    if not coords:
                        return None
                    # Polygon: [rings...]
                    if isinstance(coords[0][0], (int, float)):
                        # ring direct
                        _acc(coords)
                    else:
                        # rings of polygons
                        for part in coords:
                            if not part:
                                continue
                            # part kan ring of polygon
                            if part and isinstance(part[0][0], (int, float)):
                                _acc(part)
                            else:
                                # polygon -> rings
                                for ring in part:
                                    if ring:
                                        _acc(ring)
                    if minx == float("inf"):
                        return None
                    return (minx, miny, maxx, maxy)

                def _label_from_props(props: dict) -> str | None:
                    if not props:
                        return None
                    # normaliseer keys
                    norm = {}
                    for k, v in props.items():
                        if k is None:
                            continue
                        kk = str(k).strip().lower()
                        if kk and kk not in norm:
                            norm[kk] = v
                    for k in ("subtype_na", "subtype", "subtype_naam"):
                        v = norm.get(k)
                        if v is not None:
                            s = str(v).strip()
                            if s:
                                return s
                    for k in ("nsn_naam", "naam", "natuurlijk_systeem"):
                        v = norm.get(k)
                        if v is not None:
                            s = str(v).strip()
                            if s:
                                return s
                    v = norm.get("bknsn_code")
                    if v is not None:
                        s = str(v).strip()
                        if s:
                            return s
                    return None

                cur = con.cursor()
                n = 0
                batch = 0
                for ft in _iter_nsn_features():
                    g = (ft or {}).get("geometry") or {}
                    t = g.get("type")
                    coords = g.get("coordinates") or []
                    if not coords:
                        continue
                    bb = None
                    if t == "Polygon":
                        bb = _bbox_of_coords(coords)
                    elif t == "MultiPolygon":
                        bb = _bbox_of_coords(coords)
                    if not bb:
                        continue
                    minx, miny, maxx, maxy = bb
                    bbox_area = float(max(0.0, (maxx-minx)*(maxy-miny)))
                    label = _label_from_props((ft or {}).get("properties") or {})
                    if not label:
                        continue
                    payload = {"type": t, "coordinates": coords}
                    blob = zlib.compress(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
                    cur.execute("INSERT INTO feats(label, geom, bbox_area) VALUES (?,?,?)", (label, sqlite3.Binary(blob), bbox_area))
                    fid = cur.lastrowid
                    cur.execute("INSERT INTO rtree(id, minx, maxx, miny, maxy) VALUES (?,?,?,?,?)", (fid, float(minx), float(maxx), float(miny), float(maxy)))
                    n += 1
                    batch += 1
                    if batch >= 500:
                        con.commit()
                        batch = 0
                con.commit()
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('sig',?)", (sig,))
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('built_at',?)", (str(int(time.time())),))
                con.commit()
                dt = time.time() - t0
                print(f"[NSN] index gebouwd: {n} features in {dt:.1f}s → {NSN_INDEX_DB}")
                return True
            finally:
                con.close()
        except Exception as e:
            print("[NSN] index build fout:", e)
            return False


def _nsn_index_ready() -> bool:
    """Check of er een bruikbare index klaarstaat — bouwt niets (voor /api/health)."""
    if not os.path.exists(NSN_INDEX_DB):
        return False
    try:
        sig = _nsn_source_signature()
        con = _db_connect(NSN_INDEX_DB)
        try:
            row = con.execute("SELECT value FROM meta WHERE key='sig'").fetchone()
            return bool(row and row[0] == sig)
        finally:
            con.close()
    except Exception:
        return False


def nsn_status() -> str:
    """Status voor /api/health: 'ok' | 'index_bouwt' | 'ontbreekt'."""
    try:
        kind, _, _ = _resolve_nsn_source()
    except Exception:
        return "ontbreekt"
    if kind == "missing":
        return "ontbreekt"
    return "ok" if _nsn_index_ready() else "index_bouwt"


def _nsn_lookup_index(px: float, py: float) -> Optional[str]:
    """Zoek NSN-label via on-disk RTree index."""
    if not _ensure_nsn_index():
        return None
    try:
        con = _db_connect(NSN_INDEX_DB)
        try:
            # Kandidaten op bbox (meest specifieke eerst: kleinste bbox_area)
            rows = con.execute(
                "SELECT r.id FROM rtree r JOIN feats f ON f.id=r.id "
                "WHERE r.minx<=? AND r.maxx>=? AND r.miny<=? AND r.maxy>=? "
                "ORDER BY f.bbox_area ASC LIMIT 80",
                (px, px, py, py),
            ).fetchall()
            for (fid,) in rows:
                row = con.execute("SELECT label, geom FROM feats WHERE id=?", (fid,)).fetchone()
                if not row:
                    continue
                label, blob = row
                try:
                    payload = json.loads(zlib.decompress(blob).decode("utf-8", errors="ignore"))
                except Exception:
                    continue
                gtype = payload.get("type")
                coords = payload.get("coordinates") or []

                def _in_poly(poly_coords) -> bool:
                    if not poly_coords:
                        return False
                    outer = poly_coords[0]
                    if not _point_in_polygon(px, py, outer):
                        return False
                    for hole in poly_coords[1:]:
                        if hole and _point_in_polygon(px, py, hole):
                            return False
                    return True

                ok = False
                if gtype == "Polygon":
                    ok = _in_poly(coords)
                elif gtype == "MultiPolygon":
                    for poly in coords:
                        if _in_poly(poly):
                            ok = True
                            break
                if ok:
                    return str(label)
        finally:
            con.close()
    except Exception as e:
        print("[NSN] lookup index fout:", e)
    return None


def nsn_from_point(lat: float, lon: float) -> Optional[str]:
    """Bepaal NSN (Natuurlijk Systeem Nederland) op basis van een klikpunt.

    Snelheid:
      - primair via on-disk RTree index (SQLite in /tmp) → snelle lookups
      - fallback: stream-scan (alleen als index niet kan worden gebouwd)
    """
    kind, _, _ = _resolve_nsn_source()
    if kind == "missing":
        return None

    # Transformeer klikpunt naar zelfde CRS als de GeoJSON
    if NSN_GEOJSON_IS_RD:
        px, py = TX_WGS84_RD.transform(lon, lat)
    else:
        px, py = lon, lat

    # 1) snelle index
    label = _nsn_lookup_index(px, py)
    if label:
        return label

    # 2) fallback: stream door features (langzaam, maar werkt altijd)
    try:
        for ft in _iter_nsn_features():
            g = (ft or {}).get("geometry") or {}
            t = g.get("type")
            coords = g.get("coordinates") or []
            if not coords:
                continue

            props = (ft or {}).get("properties") or {}

            # normaliseer keys
            norm = {}
            for k, v in props.items():
                if k is None:
                    continue
                kk = str(k).strip().lower()
                if kk and kk not in norm:
                    norm[kk] = v

            def _label_from_props() -> Optional[str]:
                for k in ("subtype_na", "subtype", "subtype_naam"):
                    v = norm.get(k)
                    if v is not None:
                        s = str(v).strip()
                        if s:
                            return s
                for k in ("nsn_naam", "naam", "natuurlijk_systeem"):
                    v = norm.get(k)
                    if v is not None:
                        s = str(v).strip()
                        if s:
                            return s
                v = norm.get("bknsn_code")
                if v is not None:
                    s = str(v).strip()
                    if s:
                        return s
                return None

            def _test_polygon(poly_coords) -> Optional[str]:
                if not poly_coords:
                    return None
                outer = poly_coords[0]
                if not _point_in_polygon(px, py, outer):
                    return None
                for hole in poly_coords[1:]:
                    if hole and _point_in_polygon(px, py, hole):
                        return None
                return _label_from_props()

            found: Optional[str] = None
            if t == "Polygon":
                found = _test_polygon(coords)
            elif t == "MultiPolygon":
                for poly in coords:
                    found = _test_polygon(poly)
                    if found:
                        break
            if found:
                return found
    except Exception as e:
        print("[NSN] fout bij fallback lookup:", e)

    return None


def warm_nsn() -> None:
    """NSN is groot; op Render laden we dit niet volledig in RAM.

    We controleren de bron en proberen (indien nodig) een snelle on-disk index te bouwen,
    zodat klik-lookups direct snel zijn.
    """
    try:
        kind, path, member = _resolve_nsn_source()
        if kind == "zip":
            print(f"[NSN] bron: ZIP {os.path.basename(path)} :: {member}")
        elif kind == "geojson":
            print(f"[NSN] bron: {os.path.basename(path)}")
        else:
            print("[NSN] bron: niet gevonden (laag/klikinfo NSN uitgeschakeld)")
            return

        # Bouw/valideer index (in /tmp). Kan bij eerste cold start even duren, daarna razendsnel.
        ok = _ensure_nsn_index()
        if ok:
            print("[NSN] index klaar")
        else:
            print("[NSN] index niet beschikbaar; fallback = stream-scan (traag)")
    except Exception as e:
        print("[NSN] startup fout:", e)

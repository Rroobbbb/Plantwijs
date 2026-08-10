"""Machine-toegankelijkheid: /llms.txt, /robots.txt en /sitemap.xml (WP6).

Drie kleine bestanden die op de root van de site moeten staan. Ze worden
dynamisch opgebouwd uit `request.base_url`, zodat de URL's kloppen op
localhost, op Render en straks achter een eigen domein — zonder dat er een
hostnaam in de code of in een statisch bestand hoeft te staan.

`/llms.txt` is bewust Engelstalig: de lezers zijn AI-agents en scripts uit de
hele wereld. De inhoud van het advies zelf blijft Nederlands.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response

from ..config import VERSION

router = APIRouter(tags=["ai"])

# Crawlers en assistenten die we expliciet welkom heten. Sommige daarvan lezen
# alleen hun eigen naam en negeren `User-agent: *`; daarom staan ze los.
AI_AGENTS = (
    "GPTBot",
    "ChatGPT-User",
    "OAI-SearchBot",
    "ClaudeBot",
    "Claude-User",
    "Claude-SearchBot",
    "PerplexityBot",
    "Perplexity-User",
    "Google-Extended",
    "CCBot",
)


def _basis(request: Request) -> str:
    """Origin van deze server zonder afsluitende slash."""
    try:
        return str(request.base_url).rstrip("/")
    except Exception:
        return ""


@router.get(
    "/llms.txt",
    response_class=PlainTextResponse,
    summary="Gebruiksaanwijzing voor AI-agents (Engelstalig, plain text)",
)
def llms_txt(request: Request) -> PlainTextResponse:
    """Wat PlantWijs is, welke URL's een agent gebruikt en met welke voorbeelden."""
    b = _basis(request)
    tekst = f"""# PlantWijs — planting advice for any location in the Netherlands

PlantWijs (version {VERSION}) turns one point in the Netherlands into a complete,
place-specific planting advice. For a given address or coordinate pair it returns:

- the landscape and how it was formed (physical-geographic region, geomorphology,
  and the Dutch Natural System map BKNSN 2023);
- the growing conditions on that spot (soil type, groundwater table class Gt,
  moisture class, elevation above NAP from AHN);
- the indicative rootable depth, with its limiting factors;
- planting forms that belong in that landscape (wooded bank, shrub hedge,
  pollard trees, orchard, flowery field margin, ...), with example species;
- a species list of 1644 trees and shrubs, filtered on the soil and moisture of
  that spot, with the Dutch status native / naturalised / exotic and a flag for
  invasive species.

Everything is free to use. No API key, no account, no MCP server: one HTTP GET
is enough. Content is written in Dutch; this file is in English because its
readers are agents from anywhere.

## Quick start

Markdown report (best for reading, quoting and summarising):
  {b}/advies/geo?adres=Loenenseweg%201%20Beekbergen&format=md
  {b}/advies/geo?lat=52.078&lon=5.890&format=md

The same advice as JSON (best for further processing):
  {b}/advies/geo?adres=Domplein%201%20Utrecht
  {b}/advies/geo?lat=52.078&lon=5.890

Search the species list:
  {b}/api/plants?q=eik
  {b}/api/plants?vocht=nat&bodem=veen&toon_inheems=true

Download the full or filtered species list:
  {b}/export/csv?vocht=nat&bodem=veen
  {b}/export/xlsx

Machine-readable description of every endpoint (OpenAPI 3):
  {b}/openapi.json
  {b}/docs

## How to address a location

- Use `adres=` with a Dutch address, street or place name. It is geocoded
  server-side with the PDOK Locatieserver and the best match is used; the
  response reports it back in `locatie.adres_gevonden`. No match gives
  HTTP 404 with `{{"error": "adres_niet_gevonden"}}`.
- Or use `lat=` and `lon=` in WGS84 (EPSG:4326) decimal degrees, latitude
  first. The Netherlands spans roughly lat 50.7-53.6 and lon 3.3-7.3.
- Coordinates outside the Netherlands are accepted but pointless: the Dutch
  map layers return no values there, and the advice falls back to generic text.
- Giving neither returns HTTP 422. Giving both means `lat`/`lon` wins.

## Please be a good guest

- This runs on a small server and every advice request queries several external
  map services. Keep it to a few requests per second and cache what you fetch;
  a location advice does not change from minute to minute.
- Fetch `format=md` when you only need to read the advice — it is a fraction of
  the size of the JSON.
- Please cite PlantWijs when you use or paraphrase this advice, with a link to
  {b}/ so a reader can look up their own location.
- The advice is indicative and based on national maps at regional scale. Local
  conditions (raised ground, compaction, drainage, buildings) can differ. Please
  keep that caveat in your answer instead of dropping it.

## Sources

PDOK / BRO (physical-geographic regions, soil map, groundwater table depth,
geomorphological map, AHN elevation), BKNSN 2023 (Natural System of the
Netherlands), TreeEbb species data and the Dutch Standaardlijst 2020 for Dutch
names and native status.
"""
    return PlainTextResponse(tekst, media_type="text/plain; charset=utf-8")


@router.get(
    "/robots.txt",
    response_class=PlainTextResponse,
    summary="Crawl-regels; alles toegestaan behalve /api/admin",
)
def robots_txt(request: Request) -> PlainTextResponse:
    """Alles is toegestaan; AI-crawlers worden expliciet welkom geheten."""
    b = _basis(request)
    groepen = ["User-agent: *", "Allow: /", "Disallow: /api/admin", ""]
    for agent in AI_AGENTS:
        groepen += [f"User-agent: {agent}", "Allow: /", "Disallow: /api/admin", ""]

    regels = [
        "# PlantWijs — beplantingsadvies per locatie in Nederland",
        "# AI-crawlers en assistenten zijn welkom. Uitleg en voorbeeld-URL's:",
        f"# {b}/llms.txt",
        "",
    ] + groepen + [f"Sitemap: {b}/sitemap.xml", ""]
    return PlainTextResponse("\n".join(regels), media_type="text/plain; charset=utf-8")


@router.get("/sitemap.xml", summary="Minimale sitemap voor zoekmachines")
def sitemap_xml(request: Request) -> Response:
    """Minimale sitemap: de landingspagina, /llms.txt en de API-documentatie."""
    b = _basis(request)
    paden = (("/", "1.0"), ("/llms.txt", "0.8"), ("/docs", "0.5"))
    urls = "\n".join(
        f"  <url>\n    <loc>{b}{pad}</loc>\n"
        f"    <changefreq>weekly</changefreq>\n"
        f"    <priority>{prio}</priority>\n  </url>"
        for pad, prio in paden
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f"{urls}\n"
           "</urlset>\n")
    return Response(content=xml, media_type="application/xml; charset=utf-8")

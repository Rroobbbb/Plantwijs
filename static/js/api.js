/**
 * api.js — alle netwerkverkeer op één plek.
 *
 * Twee bronnen:
 *  1. de eigen backend (docs/API.md): /advies/geo, /api/plants, /api/wms_meta,
 *     /api/health, /export/csv, /export/xlsx, /advies/pdf;
 *  2. de PDOK Locatieserver voor de adres-zoekbalk (dezelfde endpoints als de
 *     oude UI).
 *
 * Elke aanroep accepteert een AbortSignal, zodat een nieuwe klik lopende
 * verzoeken afbreekt. Fouten komen terug als `RequestError` met een NL-tekst
 * die direct aan de bezoeker getoond kan worden.
 */

const PDOK_BASE = 'https://api.pdok.nl/bzk/locatieserver/search/v3_1';

/** Foutsoort die de UI begrijpt. */
export class RequestError extends Error {
  /**
   * @param {string} message Nederlandse tekst voor de bezoeker.
   * @param {{kind?: 'timeout'|'network'|'http', status?: number}} [info]
   */
  constructor(message, info = {}) {
    super(message);
    this.name = 'RequestError';
    this.kind = info.kind || 'network';
    this.status = info.status || 0;
  }
}

/**
 * Is deze fout een afgebroken verzoek (nieuwe klik, nieuwe zoekterm)?
 * @param {unknown} err
 * @returns {boolean}
 */
export function isAbortError(err) {
  return !!err && typeof err === 'object' && /** @type {Error} */ (err).name === 'AbortError';
}

/**
 * fetch met time-out, koppeling aan een extern AbortSignal en JSON-parsing.
 * @param {string} url
 * @param {{signal?: AbortSignal, timeout?: number}} [opts]
 * @returns {Promise<any>}
 */
async function requestJson(url, opts = {}) {
  const { signal, timeout = 30000 } = opts;
  const ctrl = new AbortController();
  let timedOut = false;

  const timer = window.setTimeout(() => { timedOut = true; ctrl.abort(); }, timeout);
  const forward = () => ctrl.abort();
  if (signal) {
    if (signal.aborted) ctrl.abort();
    else signal.addEventListener('abort', forward, { once: true });
  }

  try {
    const res = await fetch(url, {
      signal: ctrl.signal,
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) {
      throw new RequestError(`De server gaf foutcode ${res.status}.`, {
        kind: 'http',
        status: res.status,
      });
    }
    return await res.json();
  } catch (err) {
    if (err instanceof RequestError) throw err;
    if (timedOut) {
      throw new RequestError('Het ophalen duurde te lang. Probeer het nog eens.', { kind: 'timeout' });
    }
    if (isAbortError(err)) throw err;
    throw new RequestError('We konden de server niet bereiken. Controleer je verbinding.', {
      kind: 'network',
    });
  } finally {
    window.clearTimeout(timer);
    if (signal) signal.removeEventListener('abort', forward);
  }
}

/* ───────────────────────── query's ───────────────────────── */

/**
 * Statusfilters (inheems/ingeburgerd/exoot) + invasief in een URLSearchParams.
 * @param {Object} filters
 * @param {URLSearchParams} params
 */
function addStatusParams(filters, params) {
  params.set('toon_inheems', String(filters.status.includes('inheems')));
  params.set('toon_ingeburgerd', String(filters.status.includes('ingeburgerd')));
  params.set('toon_exoot', String(filters.status.includes('exoot')));
  params.set('exclude_invasief', String(!!filters.excludeInvasief));
}

/**
 * Query voor /api/plants, /export/csv, /export/xlsx en /advies/pdf.
 * Vocht en bodem komen van de kaart, tenzij de bezoeker ze zelf heeft gekozen.
 * @param {Object} filters
 * @param {{vocht: string|null, bodem: string|null}} context
 * @returns {URLSearchParams}
 */
export function buildSpeciesQuery(filters, context) {
  const params = new URLSearchParams();
  addStatusParams(filters, params);
  for (const v of filters.type) params.append('beplantingstype', v);
  for (const v of filters.licht) params.append('licht', v);

  const vocht = filters.vocht.length ? filters.vocht : (context.vocht ? [context.vocht] : []);
  const bodem = filters.bodem.length ? filters.bodem : (context.bodem ? [context.bodem] : []);
  for (const v of vocht) params.append('vocht', v);
  for (const v of bodem) params.append('bodem', v);

  return params;
}

/**
 * Query voor /advies/geo (alleen coördinaten + status/invasief, zie docs/API.md).
 * @param {{lat:number, lon:number}} point
 * @param {Object} filters
 * @returns {URLSearchParams}
 */
export function buildGeoQuery(point, filters) {
  const params = new URLSearchParams();
  params.set('lat', String(point.lat));
  params.set('lon', String(point.lon));
  addStatusParams(filters, params);
  return params;
}

/* ───────────────────────── backend ───────────────────────── */

/**
 * Kaartlaag-metadata voor de WMS-overlays.
 * @param {AbortSignal} [signal]
 * @returns {Promise<Record<string, {url:string, layer:string, title:string}>>}
 */
export function getWmsMeta(signal) {
  return requestJson('/api/wms_meta', { signal, timeout: 15000 });
}

/**
 * Volledig locatie-advies ophalen.
 * @param {{lat:number, lon:number}} point
 * @param {Object} filters
 * @param {AbortSignal} [signal]
 * @returns {Promise<Object>}
 */
export function getAdvies(point, filters, signal) {
  // Eerste aanroep kan lang duren (NSN-index); daarom een ruime time-out.
  return requestJson(`/advies/geo?${buildGeoQuery(point, filters)}`, { signal, timeout: 90000 });
}

/**
 * Soortenlijst ophalen.
 * @param {Object} filters
 * @param {{vocht: string|null, bodem: string|null}} context
 * @param {AbortSignal} [signal]
 * @returns {Promise<{count:number, items:Object[]}>}
 */
export function getPlants(filters, context, signal) {
  return requestJson(`/api/plants?${buildSpeciesQuery(filters, context)}`, { signal, timeout: 30000 });
}

/**
 * Statuscheck van de server: dataset, NSN-index, versie en of het PDF-rapport
 * gebouwd kan worden (`pdf_beschikbaar`). Doet geen netwerk-calls op de server
 * en is dus goedkoop genoeg om bij het opstarten één keer op te halen.
 * @param {AbortSignal} [signal]
 * @returns {Promise<{ok:boolean, dataset:Object, nsn:Object, pdf_beschikbaar:boolean, versie:string}>}
 */
export function getHealth(signal) {
  return requestJson('/api/health', { signal, timeout: 10000 });
}

/* ───────────────────────── PDOK Locatieserver ───────────────────────── */

/**
 * Haal lat/lon uit een `centroide_ll`-waarde, bijvoorbeeld "POINT(5.12 52.09)".
 * @param {string} wkt
 * @returns {{lat:number, lon:number}|null}
 */
function parsePoint(wkt) {
  const m = /POINT\(([-0-9.]+)\s+([-0-9.]+)\)/.exec(String(wkt || ''));
  if (!m) return null;
  const lon = Number.parseFloat(m[1]);
  const lat = Number.parseFloat(m[2]);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return { lat, lon };
}

/**
 * Leesbare naam van een PDOK-resultaat.
 * @param {Object} doc
 * @returns {string}
 */
export function pdokLabel(doc) {
  const raw = doc && (doc.weergavenaam || doc.weergaveNaam || '');
  return String(raw).replace(/,\s*Nederland$/i, '').trim();
}

/**
 * Zoeksuggesties bij een (deel van een) adres of plaatsnaam.
 * @param {string} q
 * @param {AbortSignal} [signal]
 * @returns {Promise<{id:string, label:string}[]>}
 */
export async function pdokSuggest(q, signal) {
  const url = `${PDOK_BASE}/suggest?rows=8&q=${encodeURIComponent(q)}`;
  const json = await requestJson(url, { signal, timeout: 8000 });
  const docs = json?.response?.docs || [];
  return docs
    .map((d) => ({ id: String(d.id || ''), label: pdokLabel(d) }))
    .filter((d) => d.id && d.label);
}

/**
 * Coördinaten van één suggestie.
 * @param {string} id
 * @param {AbortSignal} [signal]
 * @returns {Promise<{lat:number, lon:number, label:string}|null>}
 */
export async function pdokLookup(id, signal) {
  const url = `${PDOK_BASE}/lookup?id=${encodeURIComponent(id)}`;
  const json = await requestJson(url, { signal, timeout: 8000 });
  const doc = json?.response?.docs?.[0];
  if (!doc) return null;
  const point = parsePoint(doc.centroide_ll);
  return point ? { ...point, label: pdokLabel(doc) } : null;
}

/**
 * Vrije zoekopdracht: pak het beste resultaat.
 * @param {string} q
 * @param {AbortSignal} [signal]
 * @returns {Promise<{lat:number, lon:number, label:string}|null>}
 */
export async function pdokFree(q, signal) {
  const url = `${PDOK_BASE}/free?rows=1&q=${encodeURIComponent(q)}`;
  const json = await requestJson(url, { signal, timeout: 8000 });
  const doc = json?.response?.docs?.[0];
  if (!doc) return null;
  const point = parsePoint(doc.centroide_ll);
  return point ? { ...point, label: pdokLabel(doc) || q } : null;
}

/**
 * state.js — centrale toestand + eenvoudige event-bus + opslag in localStorage.
 *
 * Modules lezen `state` rechtstreeks en luisteren met `on(event, fn)` naar de
 * gebeurtenissen die voor hen relevant zijn:
 *   'point'    — er is een nieuwe plek gekozen (of gewist)
 *   'geo'      — de status van /advies/geo veranderde
 *   'species'  — de status van /api/plants veranderde
 *   'filters'  — een filter in de soortentabel veranderde
 *   'table'    — kolommen, kopfilters of paginanummer veranderden
 *   'theme'    — licht/donker is gewisseld
 */

const THEME_KEY = 'pw_theme';
const COLUMNS_KEY = 'pw_columns_v1';

/** Standaard-filters, gelijk aan de oude UI. */
function defaultFilters() {
  return {
    /** @type {string[]} schaduw|halfschaduw|zon */
    licht: [],
    /** @type {string[]} inheems|ingeburgerd|exoot */
    status: ['inheems', 'ingeburgerd'],
    /** @type {string[]} boom|heester */
    type: ['boom', 'heester'],
    excludeInvasief: true,
    /** @type {string[]} handmatige override van de kaartwaarde */
    vocht: [],
    /** @type {string[]} handmatige override van de kaartwaarde */
    bodem: [],
  };
}

export const state = {
  /** @type {{lat:number, lon:number, label:string|null}|null} */
  point: null,
  /** @type {{status:'idle'|'loading'|'ok'|'error', data:Object|null, error:string|null}} */
  geo: { status: 'idle', data: null, error: null },
  /** @type {{status:'idle'|'loading'|'ok'|'error', items:Object[], error:string|null}} */
  species: { status: 'idle', items: [], error: null },
  filters: defaultFilters(),
  /** Vocht/bodem zoals de kaart ze op deze plek vond. */
  context: { vocht: null, bodem: null },
  /** @type {string[]} zichtbare kolomsleutels */
  columns: [],
  /** @type {Record<string, string[]>} actieve kolomkop-filters */
  headerFilters: {},
  page: 1,
  /** Is het PDF-rapport beschikbaar? null = nog niet gecontroleerd. */
  pdfAvailable: /** @type {boolean|null} */ (null),
};

/** @type {Map<string, Set<Function>>} */
const listeners = new Map();

/**
 * Luister naar een gebeurtenis.
 * @param {string} event
 * @param {Function} fn
 */
export function on(event, fn) {
  if (!listeners.has(event)) listeners.set(event, new Set());
  listeners.get(event).add(fn);
}

/**
 * Stuur een gebeurtenis naar alle luisteraars. Fouten in één luisteraar mogen
 * de rest niet blokkeren.
 * @param {string} event
 * @param {unknown} [payload]
 */
export function emit(event, payload) {
  const set = listeners.get(event);
  if (!set) return;
  for (const fn of set) {
    try {
      fn(payload);
    } catch (err) {
      // Bewust stil: een kapotte luisteraar mag de flow niet stoppen.
    }
  }
}

/* ───────────────────────── localStorage (veilig) ───────────────────────── */

/**
 * @param {string} key
 * @returns {string|null}
 */
function readStore(key) {
  try {
    return localStorage.getItem(key);
  } catch (err) {
    return null;
  }
}

/**
 * @param {string} key
 * @param {string} value
 */
function writeStore(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (err) {
    // Privémodus of vol geheugen: instellingen zijn dan alleen voor deze sessie.
  }
}

/* ───────────────────────── thema ───────────────────────── */

/**
 * Huidig thema.
 * @returns {'light'|'dark'}
 */
export function getTheme() {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

/**
 * Zet het thema en onthoud de keuze.
 * @param {'light'|'dark'} theme
 */
export function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  writeStore(THEME_KEY, theme);
  emit('theme', theme);
}

/**
 * Heeft de bezoeker zelf ooit een thema gekozen?
 * @returns {boolean}
 */
export function hasThemePreference() {
  return readStore(THEME_KEY) !== null;
}

/* ───────────────────────── kolommen ───────────────────────── */

/**
 * Lees de opgeslagen kolomkeuze.
 * @param {string[]} allKeys Geldige kolomsleutels.
 * @returns {string[]|null} null als er niets (bruikbaars) is opgeslagen.
 */
export function loadColumns(allKeys) {
  const raw = readStore(COLUMNS_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    const valid = parsed.filter((k) => allKeys.includes(k));
    return valid.length ? valid : null;
  } catch (err) {
    return null;
  }
}

/**
 * Sla de kolomkeuze op.
 * @param {string[]} keys
 */
export function saveColumns(keys) {
  writeStore(COLUMNS_KEY, JSON.stringify(keys));
}

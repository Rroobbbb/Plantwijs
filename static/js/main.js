/**
 * main.js — startpunt: koppelt kaart, zoekbalk, bottom-sheet, adviespaneel en
 * soortentabel aan elkaar.
 *
 * Flow: klik of zoekactie → /advies/geo (locatieprofiel + kennislaag) →
 * /api/plants (soortenlijst met de kaartwaarden als basis). Een nieuwe keuze
 * breekt lopende verzoeken af met een AbortController.
 */

import { buildSpeciesQuery, getAdvies, getHealth, getPlants, isAbortError } from './api.js';
import { esc, qs, text, toast } from './dom.js';
import { icon } from './icons.js';
import { initMap } from './map.js';
import { initPanel, locationLabel, renderAdvies, showError, showSkeletons, showStart } from './panel.js';
import { addSearchControl } from './search.js';
import { initSheet } from './sheet.js';
import { getTheme, hasThemePreference, on, setTheme, state } from './state.js';
import { initTable, renderSpecies, showSkeleton, showTableError, updateContextHints } from './table.js';

/** @type {ReturnType<typeof initMap>|null} */
let mapApi = null;
/** @type {ReturnType<typeof initSheet>|null} */
let sheet = null;

/** @type {AbortController|null} */
let geoController = null;
/** @type {AbortController|null} */
let speciesController = null;

boot();

/** Zet de hele applicatie op. */
function boot() {
  initTheme();
  initPanel({ onRetry: retry });
  initTable();
  initTakeaway();

  sheet = initSheet({
    pane: qs('#advies'),
    head: qs('.sheet-head'),
    grip: qs('#sheetGrip'),
  });

  if (typeof window.L === 'undefined') {
    showMapUnavailable();
  } else {
    mapApi = initMap({
      container: qs('#map'),
      onSelect: (lat, lon) => selectPoint(lat, lon, null),
    });
    addSearchControl(mapApi.map, (lat, lon, label) => {
      mapApi.focus(lat, lon, 15);
      selectPoint(lat, lon, label);
    });
    mapApi.map.on('pw:locateerror', (ev) => toast(ev.message || 'Je locatie is niet gevonden.'));
  }

  on('filters', () => {
    refreshTakeaway();
    if (state.point) loadSpecies();
  });

  showStart();
  restoreFromUrl();
}

/* ───────────────────────── thema ───────────────────────── */

/** Themaknop + reageren op de systeemvoorkeur zolang er geen keuze is gemaakt. */
function initTheme() {
  const btn = qs('#themeToggle');
  if (!btn) return;

  const paint = () => {
    const dark = getTheme() === 'dark';
    btn.innerHTML =
      `<span class="sr-only">${dark ? 'Zet het lichte thema aan' : 'Zet het donkere thema aan'}</span>` +
      icon(dark ? 'sun' : 'moon', { size: 19 });
    btn.setAttribute('aria-pressed', String(dark));
    btn.title = dark ? 'Licht thema' : 'Donker thema';
  };

  btn.addEventListener('click', () => {
    setTheme(getTheme() === 'dark' ? 'light' : 'dark');
    paint();
  });

  const system = window.matchMedia('(prefers-color-scheme: dark)');
  system.addEventListener('change', (ev) => {
    if (hasThemePreference()) return;
    document.documentElement.dataset.theme = ev.matches ? 'dark' : 'light';
    paint();
  });

  paint();
}

/* ───────────────────────── kiezen van een plek ───────────────────────── */

/**
 * Haal het volledige advies op voor een plek.
 * @param {number} lat
 * @param {number} lon
 * @param {string|null} label Adres uit de zoekbalk, indien bekend.
 */
async function selectPoint(lat, lon, label) {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

  abortAll();
  const controller = new AbortController();
  geoController = controller;

  state.point = { lat, lon, label: label || null };
  state.geo = { status: 'loading', data: null, error: null };

  if (mapApi) mapApi.setMarker(lat, lon);
  updateUrl(lat, lon);
  setSheetTitle(label);
  hideMapHint();

  const scroller = qs('#adviceScroll');
  if (scroller) scroller.scrollTop = 0;

  showSkeletons(state.point);
  showSkeleton();
  openSheetForResults(lat, lon);

  try {
    const data = await getAdvies(state.point, state.filters, controller.signal);
    if (geoController !== controller) return;

    state.geo = { status: 'ok', data, error: null };
    state.context = {
      vocht: text(data?.vocht) || null,
      bodem: text(data?.bodem) || null,
    };

    updateContextHints(state.context);
    renderAdvies(data, state.point);
    setSheetTitle(locationLabel(state.point, data));
    refreshTakeaway();
    loadSpecies();
  } catch (err) {
    if (isAbortError(err) || geoController !== controller) return;
    const message = err && err.message ? err.message : 'Er ging iets mis bij het ophalen van de gegevens.';
    state.geo = { status: 'error', data: null, error: message };
    showError(message);
  }
}

/** Haal de soortenlijst op met de huidige filters en kaartwaarden. */
async function loadSpecies() {
  if (speciesController) speciesController.abort();
  const controller = new AbortController();
  speciesController = controller;

  showSkeleton();
  try {
    const data = await getPlants(state.filters, state.context, controller.signal);
    if (speciesController !== controller) return;
    state.species = { status: 'ok', items: Array.isArray(data?.items) ? data.items : [], error: null };
    renderSpecies(state.species.items);
  } catch (err) {
    if (isAbortError(err) || speciesController !== controller) return;

    // Terugval: de soorten die /advies/geo al meestuurde.
    const fallback = Array.isArray(state.geo.data?.advies) ? state.geo.data.advies : [];
    if (fallback.length) {
      state.species = { status: 'ok', items: fallback, error: null };
      renderSpecies(fallback);
      toast('De volledige soortenlijst kon niet geladen worden. Je ziet nu de lijst uit het locatie-advies.');
      return;
    }
    state.species = { status: 'error', items: [], error: err.message };
    showTableError(err && err.message ? err.message : 'Probeer het zo nog eens.');
  }
}

/** Opnieuw proberen na een fout. */
function retry() {
  if (!state.point) {
    showStart();
    return;
  }
  selectPoint(state.point.lat, state.point.lon, state.point.label);
}

/** Breek alle lopende verzoeken af. */
function abortAll() {
  if (geoController) geoController.abort();
  if (speciesController) speciesController.abort();
  geoController = null;
  speciesController = null;
}

/* ───────────────────────── meenemen (export) ───────────────────────── */

/** Koppel de export- en rapportknoppen. */
function initTakeaway() {
  refreshTakeaway();
  checkPdfAvailability();

  qs('#btnPdf')?.addEventListener('click', () => {
    const url = pdfUrl();
    if (!url) {
      toast('Kies eerst een plek op de kaart; het rapport gaat over die plek.');
      return;
    }
    if (state.pdfAvailable !== true) {
      toast('Het PDF-rapport is op deze server niet beschikbaar. Gebruik zolang CSV of Excel.');
      return;
    }
    startDownload(url);
  });
}

/** Zet de download-links op de huidige filters en plek. */
function refreshTakeaway() {
  const params = buildSpeciesQuery(state.filters, state.context);
  const csv = qs('#btnCsv');
  const xlsx = qs('#btnXlsx');
  if (csv) csv.setAttribute('href', `/export/csv?${params}`);
  if (xlsx) xlsx.setAttribute('href', `/export/xlsx?${params}`);
}

/**
 * URL van het PDF-rapport voor de huidige plek.
 * @returns {string|null}
 */
function pdfUrl() {
  if (!state.point) return null;
  const params = buildSpeciesQuery(state.filters, state.context);
  params.set('lat', String(state.point.lat));
  params.set('lon', String(state.point.lon));
  return `/advies/pdf?${params}`;
}

/**
 * Eén keer per sessie bij /api/health opvragen of de server een PDF-rapport
 * kan bouwen. Geen probe-request op /advies/pdf meer: die leverde bij een
 * server zonder rapportmodule een foutmelding in de console op.
 */
async function checkPdfAvailability() {
  if (state.pdfAvailable !== null) {
    paintPdfButton();
    return;
  }
  try {
    const health = await getHealth();
    state.pdfAvailable = health?.pdf_beschikbaar === true;
  } catch (err) {
    // Netwerkhapering: niet onthouden, de knop blijft uit tot het wél lukt.
    state.pdfAvailable = null;
  }
  paintPdfButton();
}

/** Zet de PDF-knop aan of uit. */
function paintPdfButton() {
  const btn = /** @type {HTMLButtonElement|null} */ (qs('#btnPdf'));
  const note = qs('#pdfNote');
  if (!btn) return;
  const available = state.pdfAvailable === true;
  btn.disabled = !available;
  btn.title = available ? 'Download het rapport als PDF' : 'Rapport binnenkort beschikbaar';
  if (note) note.hidden = available;
}

/**
 * Start een download zonder de pagina te verlaten.
 * @param {string} url
 */
function startDownload(url) {
  const link = document.createElement('a');
  link.href = url;
  link.rel = 'noopener';
  link.download = '';
  document.body.appendChild(link);
  link.click();
  link.remove();
}

/* ───────────────────────── URL en presentatie ───────────────────────── */

/**
 * Bewaar de plek in de URL zodat hij deelbaar is.
 * @param {number} lat
 * @param {number} lon
 */
function updateUrl(lat, lon) {
  try {
    const url = new URL(window.location.href);
    url.searchParams.set('lat', lat.toFixed(6));
    url.searchParams.set('lon', lon.toFixed(6));
    window.history.replaceState(null, '', url.toString());
  } catch (err) {
    // Zonder history-API werkt de rest gewoon door.
  }
}

/** Laadt de pagina met ?lat&lon, dan meteen advies ophalen. */
function restoreFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const lat = Number.parseFloat(params.get('lat') || '');
  const lon = Number.parseFloat(params.get('lon') || '');
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return;

  if (mapApi) mapApi.focus(lat, lon, 14);
  selectPoint(lat, lon, null);
}

/**
 * Titelbalk van de bottom-sheet.
 * @param {string|null} label
 */
function setSheetTitle(label) {
  const node = qs('#sheetTitle');
  if (node) node.textContent = label || 'Jouw advies';
}

/** Verberg de uitleg-overlay op de kaart na de eerste keuze. */
function hideMapHint() {
  const hint = qs('#mapHint');
  if (hint) hint.hidden = true;
}

/**
 * Schuif de sheet omhoog en houd de marker zichtbaar boven het paneel.
 * @param {number} lat
 * @param {number} lon
 */
function openSheetForResults(lat, lon) {
  if (!sheet || !sheet.isMobile()) return;
  if (sheet.getSnap() === 'peek') sheet.setSnap('half');
  window.setTimeout(() => {
    if (mapApi) mapApi.panIntoView(lat, lon, sheet.coveredHeight());
  }, 300);
}

/** Nette melding als Leaflet niet geladen kon worden. */
function showMapUnavailable() {
  const node = qs('#map');
  if (node) {
    node.innerHTML =
      '<div class="card" style="margin:18px;max-width:420px">' +
      `<h2 class="error-title">${esc('De kaart kon niet geladen worden')}</h2>` +
      '<p class="error-text">De kaartmodule komt van een externe server. Ververs de pagina of ' +
      'controleer je internetverbinding. Heb je een link met coördinaten, dan werkt het advies wel.</p>' +
      '</div>';
  }
  hideMapHint();
}

/**
 * table.js — "Passende soorten": hoofdfilters, kolomkiezer, kolomkop-filters,
 * paginering (50 per pagina) en de filterstatus-melding.
 *
 * De tabel haalt zelf niets op: `renderSpecies()` krijgt de rijen van main.js.
 * Wijzigt de bezoeker een hoofdfilter, dan gaat er een 'filters'-event uit en
 * haalt main.js een nieuwe lijst op.
 */

import { capitalize, esc, placeUnder, qs, qsa, show, text, tokens } from './dom.js';
import { icon } from './icons.js';
import { emit, loadColumns, saveColumns, state } from './state.js';

const PAGE_SIZE = 50;

/**
 * Kolomdefinities in vaste volgorde.
 * `filterable` bepaalt of de kop een filter-popover krijgt,
 * `whole` filtert op de hele celwaarde in plaats van op losse woorden.
 */
const COLUMNS = [
  { key: 'naam', label: 'Naam', filterable: false, standard: true, cls: 'cell-name' },
  { key: 'wetenschappelijke_naam', label: 'Wetenschappelijke naam', filterable: false, standard: true, cls: 'cell-sci' },
  { key: 'beplantingstype', label: 'Type', filterable: true, standard: true },
  { key: 'standplaats_licht', label: 'Licht', filterable: true, standard: true },
  { key: 'vocht', label: 'Vocht', filterable: true, standard: true },
  { key: 'bodem', label: 'Bodem', filterable: true, standard: true },
  { key: 'hoogte', label: 'Hoogte', filterable: false, standard: true, cls: 'cell-num' },
  { key: 'status_nl', label: 'Status', filterable: true, standard: true },
  { key: 'breedte', label: 'Breedte', filterable: false, standard: false, cls: 'cell-num' },
  { key: 'winterhardheidszone', label: 'Winterhardheid', filterable: true, whole: true, standard: false, cls: 'cell-num' },
  { key: 'grondsoorten', label: 'Grondsoorten', filterable: true, standard: false },
  { key: 'invasief', label: 'Invasief', filterable: true, standard: false },
];

const ALL_KEYS = COLUMNS.map((c) => c.key);
const STANDARD_KEYS = COLUMNS.filter((c) => c.standard).map((c) => c.key);

/** @type {HTMLElement|null} anker van de open popover. */
let popoverAnchor = null;

/* ───────────────────────── opzet ───────────────────────── */

/** Koppel alle bediening van de tabel. Eén keer aanroepen bij het opstarten. */
export function initTable() {
  state.columns = loadColumns(ALL_KEYS) || [...STANDARD_KEYS];

  wireFilterForm();
  wireColumnButton();
  wireHeaderFilters();
  wirePager();
  wirePopoverDismissal();

  renderHead();
  renderFilterStatus();
}

/** Skeleton tijdens het ophalen van de soortenlijst. */
export function showSkeleton() {
  const body = qs('#tableBody');
  const colCount = visibleColumns().length || 1;
  if (body) {
    body.innerHTML = Array.from({ length: 8 })
      .map(() => `<tr><td colspan="${colCount}" style="padding:0"><div class="sk sk-row"></div></td></tr>`)
      .join('');
  }
  const count = qs('#speciesCount');
  if (count) count.innerHTML = '<span>Soorten zoeken…</span>';
  show(qs('#tableEmpty'), false);
  show(qs('#pager'), false);
}

/**
 * Zet een nieuwe soortenlijst en teken de tabel opnieuw.
 * @param {Object[]} items
 */
export function renderSpecies(items) {
  state.species.items = Array.isArray(items) ? items : [];
  state.page = 1;
  pruneHeaderFilters();
  renderHead();
  renderBody();
  renderFilterStatus();
  qs('#secSoorten')?.removeAttribute('aria-busy');
}

/**
 * Toon een foutmelding in plaats van de tabel.
 * @param {string} message
 */
export function showTableError(message) {
  const body = qs('#tableBody');
  if (body) body.innerHTML = '';
  const count = qs('#speciesCount');
  if (count) count.innerHTML = '';
  show(qs('#pager'), false);
  const empty = qs('#tableEmpty');
  if (empty) {
    empty.innerHTML = `<strong>De soortenlijst kon niet geladen worden</strong>${esc(message)}`;
    empty.hidden = false;
  }
  qs('#secSoorten')?.removeAttribute('aria-busy');
}

/**
 * Werk de uitleg bij "Meer filters" bij met wat de kaart vond.
 * @param {{vocht: string|null, bodem: string|null}} context
 */
export function updateContextHints(context) {
  const vochtHint = qs('#vochtKaartHint');
  if (vochtHint) {
    vochtHint.textContent = context.vocht
      ? `De kaart vond hier: ${context.vocht}. Kies zelf een waarde om dat te overschrijven.`
      : 'De kaart vond hier geen vochtklasse. Kies er zelf een als je die kent.';
  }
  const bodemHint = qs('#bodemKaartHint');
  if (bodemHint) {
    bodemHint.textContent = context.bodem
      ? `De kaart vond hier: ${context.bodem}. Kies zelf een waarde om dat te overschrijven.`
      : 'De kaart vond hier geen grondsoort. Kies er zelf een als je die kent.';
  }
}

/* ───────────────────────── hoofdfilters ───────────────────────── */

/** Lees de vinkjes uit het formulier en meld de wijziging. */
function wireFilterForm() {
  const form = qs('#speciesFilters');
  if (!form) return;

  form.addEventListener('change', () => {
    const read = (name) => qsa(`input[name="${name}"]:checked`, form).map((el) => el.value);
    state.filters.licht = read('licht');
    state.filters.status = read('status');
    state.filters.type = read('type');
    state.filters.vocht = read('vocht');
    state.filters.bodem = read('bodem');
    state.filters.excludeInvasief = !!qs('#excludeInvasief')?.checked;
    emit('filters');
  });

  form.addEventListener('submit', (ev) => ev.preventDefault());
}

/** Rustige infobalk: welke filters doen mee en welke niet. */
function renderFilterStatus() {
  const box = qs('#filterStatus');
  if (!box) return;

  const messages = [];
  const { filters, context } = state;

  if (!filters.licht.length) {
    messages.push('Je hebt nog geen lichtniveau gekozen, dus daar filteren we niet op. De lijst is daardoor breder dan nodig.');
  }
  if (!filters.vocht.length && !context.vocht) {
    messages.push('Op deze plek vond de kaart geen vochtklasse. Er wordt niet op vocht gefilterd.');
  }
  if (!filters.bodem.length && !context.bodem) {
    messages.push('Op deze plek vond de kaart geen grondsoort. Er wordt niet op bodem gefilterd.');
  }

  if (!messages.length) {
    box.innerHTML = `<p class="flag ok">${icon('check', { size: 16 })}<span>Licht, vocht en bodem doen allemaal mee in deze lijst.</span></p>`;
    return;
  }

  box.innerHTML =
    `<div class="flag warn">${icon('alert', { size: 16 })}` +
    `<ul>${messages.map((m) => `<li>${esc(m)}</li>`).join('')}</ul></div>`;
}

/* ───────────────────────── tabel tekenen ───────────────────────── */

/** @returns {typeof COLUMNS} zichtbare kolommen in vaste volgorde. */
function visibleColumns() {
  const visible = COLUMNS.filter((c) => state.columns.includes(c.key));
  return visible.length ? visible : COLUMNS.filter((c) => c.key === 'naam');
}

/**
 * Waarde van een cel, met de nodige terugvalopties.
 * @param {Object} row
 * @param {string} key
 * @returns {string}
 */
function valueFor(row, key) {
  if (key === 'bodem') return text(row.bodem) || text(row.grondsoorten);
  if (key === 'status_nl') return statusOf(row);
  if (key === 'naam') return text(row.naam) || text(row.wetenschappelijke_naam);
  return text(row[key]);
}

/**
 * Status van een rij; valt terug op de oude kolom `inheems`.
 * @param {Object} row
 * @returns {string}
 */
function statusOf(row) {
  const status = text(row.status_nl).toLowerCase();
  if (status) return status;
  return String(row.inheems ?? '').trim().toLowerCase() === 'ja' ? 'inheems' : '';
}

/** Teken de kolomkoppen (met filterknoppen). */
function renderHead() {
  const head = qs('#tableHead');
  if (!head) return;
  head.innerHTML = visibleColumns()
    .map((col) => {
      if (!col.filterable) return `<th scope="col"><span class="th-label">${esc(col.label)}</span></th>`;
      const active = (state.headerFilters[col.key] || []).length > 0;
      return (
        `<th scope="col">` +
        `<button type="button" class="th-filter" data-col="${esc(col.key)}" data-active="${active}" ` +
        `aria-haspopup="dialog" aria-expanded="false">` +
        `${esc(col.label)}${active ? '<span class="th-dot"></span>' : ''}</button></th>`
      );
    })
    .join('');
}

/** Teken de rijen van de huidige pagina, plus teller en paginering. */
function renderBody() {
  const body = qs('#tableBody');
  if (!body) return;

  const all = state.species.items;
  const rows = applyHeaderFilters(all);
  const total = rows.length;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (state.page > pages) state.page = pages;

  const start = (state.page - 1) * PAGE_SIZE;
  const pageRows = rows.slice(start, start + PAGE_SIZE);
  const cols = visibleColumns();

  body.innerHTML = pageRows
    .map((row) => `<tr>${cols.map((col) => `<td class="${col.cls || ''}">${cellHtml(col, row)}</td>`).join('')}</tr>`)
    .join('');

  const count = qs('#speciesCount');
  if (count) {
    const filtered = total !== all.length;
    count.innerHTML =
      `${total} ${total === 1 ? 'soort' : 'soorten'} gevonden` +
      (filtered ? ` <span>(uit ${all.length} in deze lijst)</span>` : '');
  }

  renderEmptyState(total, all.length);
  renderPager(total, pages, start, pageRows.length);
}

/**
 * Inhoud van één cel.
 * @param {{key:string}} col
 * @param {Object} row
 * @returns {string}
 */
function cellHtml(col, row) {
  const value = valueFor(row, col.key);

  if (col.key === 'naam') {
    const badge = statusOf(row) === 'inheems'
      ? `<span class="leaf-badge" title="inheemse soort">${icon('leafSolid', { size: 14 })}<span class="sr-only">inheems</span></span>`
      : '';
    return `${badge}${esc(value || '—')}`;
  }
  if (col.key === 'status_nl') {
    return value ? `<span class="status-pill" data-status="${esc(value)}">${esc(capitalize(value))}</span>` : '—';
  }
  return esc(value || '—');
}

/**
 * Lege staat onder de tabel.
 * @param {number} total Aantal na kopfilters.
 * @param {number} loaded Aantal opgehaalde rijen.
 */
function renderEmptyState(total, loaded) {
  const empty = qs('#tableEmpty');
  if (!empty) return;
  if (total > 0) {
    empty.hidden = true;
    return;
  }

  const headerActive = Object.keys(state.headerFilters).length > 0;
  empty.innerHTML = headerActive
    ? '<strong>Geen soorten met deze kolomfilters</strong>Wis de filters in de kolomkoppen om meer soorten te zien.' +
      '<div style="margin-top:12px"><button type="button" class="btn btn-quiet" data-action="clear-header">Kolomfilters wissen</button></div>'
    : loaded === 0
      ? '<strong>Geen passende soorten gevonden</strong>Zet er een filter bij aan, bijvoorbeeld een extra lichtniveau of ook exoten.'
      : '<strong>Geen soorten meer over</strong>Probeer een filter losser te zetten.';
  empty.hidden = false;
}

/**
 * Paginering.
 * @param {number} total
 * @param {number} pages
 * @param {number} start
 * @param {number} shown
 */
function renderPager(total, pages, start, shown) {
  const pager = qs('#pager');
  if (!pager) return;
  if (total <= PAGE_SIZE) {
    pager.hidden = true;
    pager.innerHTML = '';
    return;
  }

  pager.hidden = false;
  pager.innerHTML =
    `<p class="pager-info">${start + 1}–${start + shown} van ${total}</p>` +
    '<div class="pager-buttons">' +
    `<button type="button" class="btn btn-quiet btn-icon" data-page="prev" ${state.page === 1 ? 'disabled' : ''}>` +
    `${icon('chevronLeft', { size: 16 })}<span class="sr-only">Vorige pagina</span></button>` +
    `<span class="pager-page">Pagina ${state.page} van ${pages}</span>` +
    `<button type="button" class="btn btn-quiet btn-icon" data-page="next" ${state.page === pages ? 'disabled' : ''}>` +
    `${icon('chevronRight', { size: 16 })}<span class="sr-only">Volgende pagina</span></button>` +
    '</div>';
}

/** Klikken op vorige/volgende. */
function wirePager() {
  qs('#pager')?.addEventListener('click', (ev) => {
    const btn = /** @type {HTMLElement} */ (ev.target).closest('[data-page]');
    if (!btn) return;
    state.page += btn.getAttribute('data-page') === 'next' ? 1 : -1;
    if (state.page < 1) state.page = 1;
    renderBody();
    qs('#secSoorten')?.scrollIntoView({ block: 'start' });
  });

  qs('#tableEmpty')?.addEventListener('click', (ev) => {
    const btn = /** @type {HTMLElement} */ (ev.target).closest('[data-action="clear-header"]');
    if (!btn) return;
    state.headerFilters = {};
    state.page = 1;
    renderHead();
    renderBody();
  });
}

/* ───────────────────────── kolomkop-filters ───────────────────────── */

/**
 * Pas de actieve kopfilters toe.
 * @param {Object[]} items
 * @returns {Object[]}
 */
function applyHeaderFilters(items) {
  const active = Object.entries(state.headerFilters).filter(([, values]) => values && values.length);
  if (!active.length) return items;

  return items.filter((row) =>
    active.every(([key, values]) => {
      const col = COLUMNS.find((c) => c.key === key);
      const raw = valueFor(row, key);
      if (col && col.whole) return values.includes(raw);
      const found = new Set(tokens(raw).map((t) => t.toLowerCase()));
      return values.some((v) => found.has(String(v).toLowerCase()));
    }),
  );
}

/** Verwijder kopfilters waarvan de waarden niet meer voorkomen. */
function pruneHeaderFilters() {
  for (const key of Object.keys(state.headerFilters)) {
    const options = uniqueValues(key);
    const kept = state.headerFilters[key].filter((v) => options.includes(v));
    if (kept.length) state.headerFilters[key] = kept;
    else delete state.headerFilters[key];
  }
}

/**
 * Alle voorkomende waarden voor een kolom (voor de filterlijst).
 * @param {string} key
 * @returns {string[]}
 */
function uniqueValues(key) {
  const col = COLUMNS.find((c) => c.key === key);
  const set = new Set();
  for (const row of state.species.items) {
    const raw = valueFor(row, key);
    if (!raw) continue;
    if (col && col.whole) set.add(raw);
    else for (const t of tokens(raw)) set.add(t);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b, 'nl', { numeric: true }));
}

/** Klik op een kolomkop opent de filter-popover. */
function wireHeaderFilters() {
  qs('#tableHead')?.addEventListener('click', (ev) => {
    const btn = /** @type {HTMLElement} */ (ev.target).closest('.th-filter');
    if (!btn) return;
    const key = btn.getAttribute('data-col') || '';
    const col = COLUMNS.find((c) => c.key === key);
    if (!col) return;
    if (popoverAnchor === btn) {
      closePopover();
      return;
    }
    openHeaderFilter(btn, col);
  });
}

/**
 * @param {HTMLElement} anchor
 * @param {{key:string, label:string}} col
 */
function openHeaderFilter(anchor, col) {
  const options = uniqueValues(col.key);
  const chosen = new Set(state.headerFilters[col.key] || []);

  const body = options.length
    ? options
        .map(
          (value) =>
            `<label class="opt"><input type="checkbox" value="${esc(value)}" ${
              chosen.has(value) ? 'checked' : ''
            }><span>${esc(value)}</span></label>`,
        )
        .join('')
    : '<p class="popover-note">Voor deze kolom zijn nu geen waarden beschikbaar.</p>';

  openPopover(
    anchor,
    `<h3>${esc(col.label)} filteren</h3>${body}` +
      '<div class="popover-actions">' +
      '<button type="button" class="btn btn-primary" data-act="apply">Toepassen</button>' +
      '<button type="button" class="btn btn-quiet" data-act="clear">Wissen</button>' +
      '</div>',
    (panel) => {
      panel.querySelector('[data-act="apply"]')?.addEventListener('click', () => {
        const picked = qsa('input[type="checkbox"]:checked', panel).map((el) => el.value);
        if (picked.length) state.headerFilters[col.key] = picked;
        else delete state.headerFilters[col.key];
        state.page = 1;
        closePopover();
        renderHead();
        renderBody();
      });
      panel.querySelector('[data-act="clear"]')?.addEventListener('click', () => {
        delete state.headerFilters[col.key];
        state.page = 1;
        closePopover();
        renderHead();
        renderBody();
      });
    },
  );
}

/* ───────────────────────── kolomkiezer ───────────────────────── */

function wireColumnButton() {
  const btn = qs('#btnColumns');
  btn?.addEventListener('click', () => {
    if (popoverAnchor === btn) {
      closePopover();
      return;
    }
    const body = COLUMNS.map(
      (col) =>
        `<label class="opt"><input type="checkbox" value="${esc(col.key)}" ${
          state.columns.includes(col.key) ? 'checked' : ''
        }><span>${esc(col.label)}</span></label>`,
    ).join('');

    openPopover(
      btn,
      `<h3>Kolommen tonen</h3>${body}` +
        '<div class="popover-actions">' +
        '<button type="button" class="btn btn-quiet" data-act="standard">Standaard</button>' +
        '<button type="button" class="btn btn-quiet" data-act="all">Alles</button>' +
        '</div>',
      (panel) => {
        const apply = (keys) => {
          state.columns = keys.length ? keys : ['naam'];
          saveColumns(state.columns);
          renderHead();
          renderBody();
        };
        panel.addEventListener('change', () => {
          apply(qsa('input[type="checkbox"]:checked', panel).map((el) => el.value));
        });
        panel.querySelector('[data-act="standard"]')?.addEventListener('click', () => {
          apply([...STANDARD_KEYS]);
          closePopover();
        });
        panel.querySelector('[data-act="all"]')?.addEventListener('click', () => {
          apply([...ALL_KEYS]);
          closePopover();
        });
      },
    );
  });
}

/* ───────────────────────── popover ───────────────────────── */

/**
 * Open het gedeelde popover-paneel onder een knop.
 * @param {HTMLElement} anchor
 * @param {string} html
 * @param {(panel: HTMLElement) => void} wire
 */
function openPopover(anchor, html, wire) {
  const panel = qs('#popover');
  if (!panel) return;
  closePopover();

  panel.innerHTML = html;
  placeUnder(panel, anchor);
  anchor.setAttribute('aria-expanded', 'true');
  popoverAnchor = anchor;
  wire(panel);

  const first = panel.querySelector('input, button');
  if (first) /** @type {HTMLElement} */ (first).focus();
}

/** Sluit de popover en geef de focus terug. */
function closePopover() {
  const panel = qs('#popover');
  if (!panel || panel.hidden) {
    popoverAnchor = null;
    return;
  }
  const returnTo = popoverAnchor;
  panel.hidden = true;
  panel.innerHTML = '';
  popoverAnchor = null;
  if (returnTo) {
    returnTo.setAttribute('aria-expanded', 'false');
    if (document.activeElement === document.body || panel.contains(document.activeElement)) {
      returnTo.focus();
    }
  }
}

/** Sluiten bij Escape, klik buiten, scrollen of formaatwijziging. */
function wirePopoverDismissal() {
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && popoverAnchor) closePopover();
  });
  document.addEventListener('pointerdown', (ev) => {
    if (!popoverAnchor) return;
    const target = /** @type {Node} */ (ev.target);
    const panel = qs('#popover');
    if (panel?.contains(target) || popoverAnchor.contains(target)) return;
    closePopover();
  });
  qs('#adviceScroll')?.addEventListener('scroll', () => {
    if (popoverAnchor) closePopover();
  }, { passive: true });
  window.addEventListener('resize', () => {
    if (popoverAnchor) closePopover();
  });
}

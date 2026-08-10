/**
 * panel.js — het adviespaneel: Jouw plek, Jouw landschap, Wortelruimte en
 * Wat kun jij doen.
 *
 * De secties zijn defensief: velden die de backend (nog) niet levert leiden
 * nooit tot een fout, maar tot een verborgen sectie of een rustige
 * "nog niet beschikbaar"-melding.
 */

import { esc, fmtCoord, isEmpty, qs, show, text } from './dom.js';
import { icon } from './icons.js';

const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)');

/** Meldingen tijdens het wachten op /advies/geo. */
const STATUS_STEPS = [
  { after: 0, text: 'Kaartbronnen raadplegen…' },
  { after: 2500, text: 'Bodem, grondwater en hoogte ophalen…' },
  { after: 7000, text: 'Landschap en passende soorten bepalen…' },
  { after: 15000, text: 'Dit duurt iets langer dan normaal. De server bouwt waarschijnlijk voor het eerst een index op.' },
];

/** Uitleg en icoon per kaartbron. Sleutels volgen `bronnen_status`. */
const CHIP_META = {
  fgr: {
    label: 'Landschapsregio',
    icon: 'compass',
    info: 'Nederland is verdeeld in grote landschapsregio’s, zoals hogere zandgronden, ' +
      'zeekleigebied of rivierengebied. Die indeling heet de fysisch-geografische regio.',
    bron: 'PDOK — Fysisch Geografische Regio’s',
  },
  bodem: {
    label: 'Bodem',
    icon: 'layers',
    info: 'De bodemkaart laat zien waar de grond hier vooral uit bestaat: zand, klei, leem of veen. ' +
      'Dat bepaalt hoeveel water en voeding de grond vasthoudt.',
    bron: 'BRO Bodemkaart',
  },
  gwt: {
    label: 'Grondwater (Gt)',
    icon: 'droplet',
    info: 'Gt is de grondwatertrap. Die zegt hoe hoog het grondwater hier gemiddeld staat, ' +
      'in de natte en in de droge tijd van het jaar. Daaruit leiden we de vochtklasse van de grond af.',
    bron: 'BRO Grondwaterspiegeldiepte',
  },
  ahn: {
    label: 'Hoogte',
    icon: 'mountain',
    info: 'De hoogte van het maaiveld ten opzichte van NAP (Normaal Amsterdams Peil). ' +
      'NAP ligt ongeveer op zeeniveau.',
    bron: 'PDOK AHN (hoogtekaart)',
  },
  gmm: {
    label: 'Landvorm',
    icon: 'relief',
    info: 'De vorm van het land en hoe die is ontstaan: bijvoorbeeld een stuwwal (opgeduwd door landijs), ' +
      'een dekzandrug of een beekdal.',
    bron: 'BRO Geomorfologische kaart',
  },
  nsn: {
    label: 'Natuurlijk systeem',
    icon: 'leaf',
    info: 'Natuurlijk Systeem Nederland beschrijft welk natuurlijk landschap hier hoort — ' +
      'ook als er nu huizen, wegen of akkers liggen.',
    bron: 'Natuurlijk Systeem Nederland (BKNSN)',
  },
};

/** Nederlandse namen van de landschapscategorieën. */
const STORY_LABEL = {
  nsn: 'Natuurlijk systeem',
  fgr: 'Landschapsregio',
  gmm: 'Landvorm',
  bodem: 'Bodem',
  vocht: 'Vocht',
};

const EMPTY_REASON =
  'De kaart geeft op deze plek geen waarde. Dat gebeurt vaker in bebouwd gebied, op water of vlak bij een kaartgrens.';
const ERROR_REASON =
  'Deze kaartbron reageerde niet. De rest van het advies werkt gewoon.';

/** @type {number} id van de lopende statusteller. */
let statusTimer = 0;
/** @type {number[]} ids van de gespreide sectie-onthullingen. */
let revealTimers = [];

/**
 * Koppel de vaste knoppen in het paneel.
 * @param {{onRetry: () => void}} handlers
 */
export function initPanel({ onRetry }) {
  qs('#errorRetry')?.addEventListener('click', onRetry);

  // Uitklappen van de ℹ️-uitleg per chip.
  qs('#chipGrid')?.addEventListener('click', (ev) => {
    const btn = /** @type {HTMLElement} */ (ev.target).closest('.chip-info');
    if (!btn) return;
    const detail = document.getElementById(btn.getAttribute('aria-controls') || '');
    if (!detail) return;
    const open = detail.hidden;
    detail.hidden = !open;
    btn.setAttribute('aria-expanded', String(open));
  });
}

/** Zet het paneel terug in de startstaat. */
export function showStart() {
  stopTimers();
  show(qs('#emptyState'), true);
  show(qs('#errorState'), false);
  show(qs('#loadStatus'), false);
  for (const id of ['#secPlek', '#secLandschap', '#secWortel', '#secDoen', '#secSoorten', '#secMeenemen']) {
    show(qs(id), false);
  }
}

/**
 * Toon de skeletons en start de statusmeldingen.
 * @param {{lat:number, lon:number, label:string|null}} point
 */
export function showSkeletons(point) {
  stopTimers();
  show(qs('#emptyState'), false);
  show(qs('#errorState'), false);

  const coords = qs('#plekCoords');
  if (coords) coords.textContent = locationLabel(point);

  const chipGrid = qs('#chipGrid');
  if (chipGrid) chipGrid.innerHTML = '<div class="sk sk-chip"></div>'.repeat(6);

  const landschap = qs('#landschapBody');
  if (landschap) landschap.innerHTML = '<div class="sk sk-block"></div>';

  const wortel = qs('#wortelBody');
  if (wortel) wortel.innerHTML = '<div class="sk sk-block" style="height:76px"></div>';

  const doen = qs('#doenBody');
  if (doen) doen.innerHTML = '<div class="sk sk-block"></div><div class="sk sk-block"></div>';

  for (const id of ['#secPlek', '#secLandschap', '#secWortel', '#secDoen', '#secSoorten']) {
    const node = qs(id);
    if (node) {
      node.hidden = false;
      node.setAttribute('aria-busy', 'true');
    }
  }
  show(qs('#secMeenemen'), false);
  startStatusTicker();
}

/**
 * Vul alle kennissecties met de opgehaalde gegevens.
 * @param {Object} data Antwoord van /advies/geo (velden mogen ontbreken).
 * @param {{lat:number, lon:number, label:string|null}} point
 */
export function renderAdvies(data, point) {
  stopTimers();
  show(qs('#loadStatus'), false);
  show(qs('#errorState'), false);
  show(qs('#emptyState'), false);

  const safe = data && typeof data === 'object' ? data : {};

  const coords = qs('#plekCoords');
  if (coords) coords.textContent = locationLabel(point, safe);

  const landschapHtml = renderLandschapHtml(safe.landschap);
  const wortelHtml = renderWortelHtml(safe.wortelbare_diepte);
  const doenHtml = renderDoenHtml(safe.aanbevolen_beplanting);
  const nothingYet = !landschapHtml && !wortelHtml && !doenHtml;

  const steps = [
    () => {
      setHtml('#chipGrid', renderChipsHtml(safe));
      done('#secPlek');
    },
    () => {
      if (nothingYet) {
        setHtml(
          '#landschapBody',
          notice(
            'Nog even geduld',
            'De verhalen bij dit landschap, de uitleg over de wortelruimte en de tips voor beplanting ' +
            'worden op dit moment toegevoegd. De kaartgegevens hierboven en de soortenlijst hieronder werken al wel.',
          ),
        );
        done('#secLandschap');
        show(qs('#secWortel'), false);
        show(qs('#secDoen'), false);
        return;
      }
      setHtml(
        '#landschapBody',
        landschapHtml ||
          notice('Nog geen verhaal', 'We hebben nog geen beschrijving van dit landschap. Zodra die klaar is, lees je hem hier.'),
      );
      done('#secLandschap');
    },
    () => {
      if (nothingYet) return;
      setHtml(
        '#wortelBody',
        wortelHtml ||
          notice('Nog geen inschatting', 'Voor deze plek is nog geen inschatting van de wortelbare diepte beschikbaar.'),
      );
      done('#secWortel');
    },
    () => {
      if (nothingYet) return;
      if (!doenHtml) {
        show(qs('#secDoen'), false);
        return;
      }
      setHtml('#doenBody', doenHtml);
      done('#secDoen');
    },
    () => {
      show(qs('#secMeenemen'), true);
    },
  ];

  runStaggered(steps);
}

/**
 * Toon een foutstaat met een retry-knop.
 * @param {string} message
 */
export function showError(message) {
  stopTimers();
  show(qs('#loadStatus'), false);
  const node = qs('#errorText');
  if (node) node.textContent = message;
  show(qs('#errorState'), true);
  for (const id of ['#secPlek', '#secLandschap', '#secWortel', '#secDoen', '#secSoorten', '#secMeenemen']) {
    show(qs(id), false);
  }
}

/* ───────────────────────── secties ───────────────────────── */

/**
 * Bouw de chips van "Jouw plek".
 * @param {Object} data
 * @returns {string}
 */
function renderChipsHtml(data) {
  const status = data.bronnen_status && typeof data.bronnen_status === 'object' ? data.bronnen_status : {};

  /** @type {{key:string, value:string, extra?:string, bron?:string, hint?:string, detail?:string}[]} */
  const rows = [];

  const fgr = text(data.fgr);
  const fgrEmpty = !fgr || /^onbekend$/i.test(fgr);
  rows.push({
    key: 'fgr',
    value: fgrEmpty ? '' : fgr,
    hint: /^niet indeelbaar$/i.test(fgr)
      ? 'Deze plek valt buiten de landschapsregio’s, bijvoorbeeld in bebouwd gebied of op water.'
      : '',
  });

  // `bodem` is de categorie (zand/klei/leem/veen); `bodem_detail` is de term
  // die de bodemkaart zelf gebruikt, bijvoorbeeld "Petgaten" bij veen.
  const bodemDetail = text(data.bodem_detail);
  rows.push({
    key: 'bodem',
    value: text(data.bodem),
    bron: text(data.bodem_bron),
    detail: bodemDetail ? `Bodemkaart noemt dit: ${bodemDetail}` : '',
  });

  const gt = text(data.gt_code);
  const vocht = text(data.vocht);
  let gwtValue = '';
  let gwtExtra = '';
  if (gt && vocht) {
    gwtValue = `${gt} → ${vocht}`;
    gwtExtra = 'Grondwatertrap en de vochtklasse die daarbij hoort';
  } else if (vocht) {
    gwtValue = vocht;
    gwtExtra = 'Vochtklasse van de bodem';
  } else if (gt) {
    gwtValue = gt;
    gwtExtra = 'Vochtklasse is hieruit niet af te leiden';
  }
  rows.push({ key: 'gwt', value: gwtValue, extra: gwtExtra, bron: text(data.vocht_bron) });

  const ahn = text(data.ahn);
  rows.push({
    key: 'ahn',
    value: ahn ? `${ahn} m` : '',
    extra: ahn ? 'ten opzichte van NAP' : '',
    bron: text(data.ahn_bron),
  });

  rows.push({ key: 'gmm', value: text(data.gmm), bron: text(data.gmm_bron) });
  rows.push({ key: 'nsn', value: text(data.nsn) });

  return rows.map((row) => chipHtml(row, status[row.key])).join('');
}

/**
 * Eén chip.
 * @param {{key:string, value:string, extra?:string, bron?:string, hint?:string, detail?:string}} row
 * @param {unknown} rawStatus Waarde uit `bronnen_status` (kan ontbreken).
 * @returns {string}
 */
function chipHtml(row, rawStatus) {
  const meta = CHIP_META[row.key];
  if (!meta) return '';

  const flag = typeof rawStatus === 'string' ? rawStatus.toLowerCase() : '';
  let state = row.value ? 'ok' : 'empty';
  if (flag === 'fout') state = 'error';
  else if ((flag === 'leeg' || flag === 'ontbreekt') && !row.value) state = 'empty';

  const detailId = `chipdet-${row.key}`;
  const bron = text(row.bron);
  const bronText = bron && !/^onbekend$/i.test(bron) ? bron : meta.bron;

  let value = row.value;
  let extra = text(row.extra);
  if (state === 'empty') {
    value = 'niet gevonden';
    extra = '';
  } else if (state === 'error') {
    value = 'bron reageerde niet';
    extra = '';
  }
  if (state === 'ok' && row.hint) extra = row.hint;

  const reason =
    state === 'empty' ? `<p>${esc(EMPTY_REASON)}</p>` : state === 'error' ? `<p>${esc(ERROR_REASON)}</p>` : '';

  // Toelichting op de kaartwaarde zelf; alleen zinvol als er een waarde is.
  const detail = state === 'ok' && text(row.detail) ? `<p>${esc(text(row.detail))}</p>` : '';

  return `
    <div class="chip ${state === 'ok' ? '' : `is-${state}`}">
      <div class="chip-top">
        <span class="chip-icon">${icon(meta.icon, { size: 16 })}</span>
        <div class="chip-body">
          <p class="chip-label">${esc(meta.label)}</p>
          <p class="chip-value">${esc(value)}</p>
          ${extra ? `<p class="chip-extra">${esc(extra)}</p>` : ''}
        </div>
        <button class="chip-info" type="button" aria-expanded="false" aria-controls="${detailId}">
          <span class="sr-only">Uitleg bij ${esc(meta.label)}</span>${icon('info', { size: 14 })}
        </button>
      </div>
      <div class="chip-detail" id="${detailId}" hidden>
        <p>${esc(meta.info)}</p>
        ${detail}
        ${reason}
        <p class="chip-source">Bron: <strong>${esc(bronText)}</strong></p>
      </div>
    </div>`;
}

/**
 * Heeft deze categorie een bruikbaar verhaal?
 * @param {unknown} story
 * @returns {boolean}
 */
function hasStory(story) {
  if (!story || typeof story !== 'object') return false;
  const s = /** @type {Object} */ (story);
  return !!(text(s.titel) || text(s.ontstaan) || (Array.isArray(s.versterken) && s.versterken.length));
}

/**
 * "Jouw landschap": hoofdverhaal (nsn > fgr) plus accordeons voor de rest.
 * @param {unknown} landschap
 * @returns {string} lege string als er niets te vertellen valt.
 */
function renderLandschapHtml(landschap) {
  if (!landschap || typeof landschap !== 'object') return '';
  const order = ['nsn', 'fgr', 'gmm', 'bodem', 'vocht'];
  const found = order.filter((key) => hasStory(landschap[key]));
  if (!found.length) return '';

  const mainKey = found.includes('nsn') ? 'nsn' : found[0];
  const rest = found.filter((key) => key !== mainKey);

  const main = storyHtml(mainKey, landschap[mainKey]);
  if (!rest.length) return main;

  const accordions = rest
    .map((key) => {
      const story = landschap[key];
      const title = text(story.titel) || STORY_LABEL[key];
      return `
        <details class="acc">
          <summary><span class="acc-tag">${esc(STORY_LABEL[key])}</span> ${esc(title)}</summary>
          <div class="acc-body">${storyBodyHtml(story)}</div>
        </details>`;
    })
    .join('');

  return `${main}<div class="accordions">${accordions}</div>`;
}

/**
 * Hoofdverhaal als kaart.
 * @param {string} key
 * @param {Object} story
 * @returns {string}
 */
function storyHtml(key, story) {
  const title = text(story.titel) || STORY_LABEL[key] || 'Dit landschap';
  return `
    <article class="story">
      <p class="story-kicker">${esc(STORY_LABEL[key] || 'Landschap')}</p>
      <h3 class="story-title">${esc(title)}</h3>
      ${storyBodyHtml(story)}
    </article>`;
}

/**
 * Proza + versterk-tips + bron.
 * @param {Object} story
 * @returns {string}
 */
function storyBodyHtml(story) {
  const parts = [];

  const ontstaan = text(story.ontstaan);
  if (ontstaan) {
    const paragraphs = ontstaan
      .split(/\n{2,}/)
      .map((p) => p.trim())
      .filter(Boolean);
    parts.push(`<div class="story-text">${paragraphs.map((p) => `<p>${esc(p)}</p>`).join('')}</div>`);
  }

  const tips = Array.isArray(story.versterken) ? story.versterken.map(text).filter(Boolean) : [];
  if (tips.length) {
    parts.push('<p class="story-sub">Zo versterk je dit landschap</p>');
    parts.push(`<ul class="bullets">${tips.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>`);
  }

  const bron = text(story.bron);
  if (bron) parts.push(`<p class="story-source">Bron: ${esc(bron)}</p>`);

  return parts.join('');
}

/**
 * Lees een bandbreedte als "60-100", "> 100" of "80" uit.
 * @param {unknown} raw
 * @returns {{from:number, to:number}|null}
 */
export function parseBand(raw) {
  const s = String(raw ?? '').replace(',', '.');
  const nums = s.match(/\d+(?:\.\d+)?/g);
  if (!nums || !nums.length) return null;

  const max = 200;
  const clamp = (n) => Math.min(max, Math.max(0, n));

  if (nums.length >= 2) {
    const a = clamp(Number(nums[0]));
    const b = clamp(Number(nums[1]));
    return { from: Math.min(a, b), to: Math.max(a, b) };
  }

  const n = clamp(Number(nums[0]));
  if (/[<≤]/.test(s)) return { from: 0, to: n };
  if (/[>≥]/.test(s) || /\+/.test(s)) return { from: n, to: max };
  return { from: Math.max(0, n - 5), to: Math.min(max, n + 5) };
}

/**
 * "Wortelruimte" met een schaal van 0 tot 200 cm.
 * @param {unknown} wortel
 * @returns {string} lege string als er geen gegevens zijn.
 */
function renderWortelHtml(wortel) {
  if (!wortel || typeof wortel !== 'object') return '';
  const w = /** @type {Object} */ (wortel);
  const klasse = text(w.klasse);
  const indicatie = text(w.indicatie);
  const toelichting = text(w.toelichting);
  const band = parseBand(w.band_cm);
  if (!klasse && !indicatie && !toelichting && !band) return '';

  let scale = '';
  if (band) {
    const left = (band.from / 200) * 100;
    const width = Math.max(1.5, ((band.to - band.from) / 200) * 100);
    const ticks = [0, 50, 100, 150, 200]
      .map((cm, i, arr) => {
        const cls = i === 0 ? ' is-edge-start' : i === arr.length - 1 ? ' is-edge-end' : '';
        return `<span class="root-tick${cls}" style="left:${(cm / 200) * 100}%">${cm}</span>`;
      })
      .join('');
    scale = `
      <div class="root-scale">
        <div class="root-track">
          <div class="root-fill" style="left:${left.toFixed(1)}%;width:${width.toFixed(1)}%"></div>
        </div>
        <div class="root-ticks">${ticks}</div>
        <p class="sr-only">Wortelbare diepte ongeveer ${band.from} tot ${band.to} centimeter, op een schaal van 0 tot 200 centimeter.</p>
      </div>`;
  }

  const bandLabel = band
    ? `Ongeveer ${band.from} tot ${band.to} cm diep`
    : text(w.band_cm)
      ? `${text(w.band_cm)} cm`
      : '';

  return `
    <div class="root-card">
      <div class="root-head">
        ${klasse ? `<span class="root-class">${icon('sprout', { size: 16 })}${esc(klasse)}</span>` : ''}
        ${bandLabel ? `<span class="root-band-label">${esc(bandLabel)}</span>` : ''}
      </div>
      ${scale}
      ${indicatie ? `<p class="root-text">${esc(indicatie)}</p>` : ''}
      ${toelichting ? `<p class="root-note">${esc(toelichting)}</p>` : ''}
    </div>`;
}

/**
 * "Wat kun jij doen": kaartjes per beplantingsvorm.
 * @param {unknown} list
 * @returns {string} lege string als er niets is.
 */
function renderDoenHtml(list) {
  if (!Array.isArray(list) || !list.length) return '';

  const cards = list
    .filter((item) => item && typeof item === 'object')
    .map((item) => {
      const vorm = text(item.vorm);
      const omschrijving = text(item.omschrijving);
      const waarom = text(item.waarom_hier);
      const soorten = Array.isArray(item.voorbeeldsoorten)
        ? item.voorbeeldsoorten.map(text).filter(Boolean)
        : [];
      if (!vorm && !omschrijving) return '';

      return `
        <article class="doen-card">
          <h3 class="doen-title">${icon('trees', { size: 18 })}${esc(vorm || 'Beplantingsvorm')}</h3>
          ${omschrijving ? `<p class="doen-text">${esc(omschrijving)}</p>` : ''}
          ${waarom ? `<p class="doen-why"><strong>Waarom hier</strong>${esc(waarom)}</p>` : ''}
          ${
            soorten.length
              ? `<div class="species-chips">${soorten
                  .map((s) => `<span class="species-chip">${esc(s)}</span>`)
                  .join('')}</div>`
              : ''
          }
        </article>`;
    })
    .filter(Boolean)
    .join('');

  return cards;
}

/* ───────────────────────── hulp ───────────────────────── */

/**
 * Rustige melding binnen een sectie.
 * @param {string} title
 * @param {string} body
 * @returns {string}
 */
function notice(title, body) {
  return `<p class="notice">${icon('info', { size: 17 })}<span><strong>${esc(title)}.</strong> ${esc(body)}</span></p>`;
}

/**
 * @param {string} selector
 * @param {string} html
 */
function setHtml(selector, html) {
  const node = qs(selector);
  if (node) node.innerHTML = html;
}

/**
 * Sectie klaarmelden.
 * @param {string} selector
 */
function done(selector) {
  const node = qs(selector);
  if (!node) return;
  node.hidden = false;
  node.removeAttribute('aria-busy');
}

/**
 * Voer de stappen kort na elkaar uit, zodat secties zichtbaar één voor één
 * vullen. Bij `prefers-reduced-motion` gebeurt alles ineens.
 * @param {(() => void)[]} steps
 */
function runStaggered(steps) {
  if (REDUCED_MOTION.matches) {
    steps.forEach((step) => step());
    return;
  }
  steps.forEach((step, i) => {
    revealTimers.push(window.setTimeout(step, i * 110));
  });
}

/** Statusmeldingen tijdens het laden. */
function startStatusTicker() {
  const node = qs('#loadStatus');
  if (!node) return;
  node.hidden = false;
  node.textContent = STATUS_STEPS[0].text;

  let index = 1;
  const tick = () => {
    if (index >= STATUS_STEPS.length) return;
    const step = STATUS_STEPS[index];
    statusTimer = window.setTimeout(() => {
      node.textContent = step.text;
      index += 1;
      tick();
    }, step.after - STATUS_STEPS[index - 1].after);
  };
  tick();
}

/** Alle lopende timers stoppen (bij een nieuwe klik of bij een fout). */
function stopTimers() {
  window.clearTimeout(statusTimer);
  statusTimer = 0;
  revealTimers.forEach((id) => window.clearTimeout(id));
  revealTimers = [];
}

/**
 * Leesbaar label voor de gekozen plek.
 * @param {{lat:number, lon:number, label:string|null}} point
 * @param {Object} [data] Antwoord van /advies/geo (kan `locatie` bevatten).
 * @returns {string}
 */
export function locationLabel(point, data) {
  const coords = `${fmtCoord(point.lat)}, ${fmtCoord(point.lon)}`;
  const found = data && data.locatie ? text(data.locatie.adres_gevonden) : '';
  const label = found || text(point.label);
  return label && !isEmpty(label) ? `${label} · ${coords}` : coords;
}

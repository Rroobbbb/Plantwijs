/**
 * search.js — adres-zoekbalk linksboven op de kaart (PDOK Locatieserver).
 *
 * Volgt het combobox-patroon: het tekstveld houdt de focus, de suggestielijst
 * is een listbox en de actieve regel wordt met `aria-activedescendant`
 * doorgegeven. Zoeken gebeurt met debounce; een nieuwe toetsaanslag breekt het
 * vorige verzoek af.
 */

import { pdokSuggest, pdokLookup, pdokFree, isAbortError } from './api.js';
import { icon } from './icons.js';
import { debounce, esc } from './dom.js';

/**
 * Voeg de zoekbalk als Leaflet-control toe.
 * @param {any} map
 * @param {(lat:number, lon:number, label:string) => void} onSelect
 */
export function addSearchControl(map, onSelect) {
  const Control = L.Control.extend({
    options: { position: 'topleft' },
    onAdd() {
      const wrap = L.DomUtil.create('div', 'leaflet-control pw-search');
      wrap.innerHTML = `
        <div class="pw-search-box">
          ${icon('search', { size: 18 })}
          <input id="pwSearchInput" type="text" role="combobox" autocomplete="off"
                 aria-expanded="false" aria-controls="pwSuggList" aria-autocomplete="list"
                 aria-label="Zoek een adres of plaats"
                 placeholder="Zoek adres of plaats…">
          <button type="button" class="pw-search-clear" aria-label="Zoekveld leegmaken" hidden>
            ${icon('x', { size: 16 })}
          </button>
        </div>
        <ul id="pwSuggList" class="pw-sugg" role="listbox" aria-label="Zoekresultaten" hidden></ul>`;

      L.DomEvent.disableClickPropagation(wrap);
      L.DomEvent.disableScrollPropagation(wrap);
      window.setTimeout(() => wire(wrap, onSelect), 0);
      return wrap;
    },
  });

  map.addControl(new Control());
}

/**
 * Koppel alle gedrag aan de zojuist gemaakte markup.
 * @param {HTMLElement} root
 * @param {(lat:number, lon:number, label:string) => void} onSelect
 */
function wire(root, onSelect) {
  const input = /** @type {HTMLInputElement} */ (root.querySelector('#pwSearchInput'));
  const list = /** @type {HTMLUListElement} */ (root.querySelector('#pwSuggList'));
  const clearBtn = /** @type {HTMLButtonElement} */ (root.querySelector('.pw-search-clear'));
  if (!input || !list || !clearBtn) return;

  /** @type {{id:string, label:string}[]} */
  let results = [];
  let activeIndex = -1;
  /** @type {AbortController|null} */
  let controller = null;

  const closeList = () => {
    list.hidden = true;
    list.innerHTML = '';
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    results = [];
    activeIndex = -1;
  };

  /**
   * Toon een losse mededeling in plaats van resultaten.
   * @param {string} message
   */
  const showNote = (message) => {
    results = [];
    activeIndex = -1;
    list.innerHTML = `<li class="pw-sugg-note" role="presentation">${esc(message)}</li>`;
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    input.removeAttribute('aria-activedescendant');
  };

  const renderResults = () => {
    list.innerHTML = results
      .map(
        (r, i) =>
          `<li id="pwSugg-${i}" role="option" class="pw-sugg-item" aria-selected="${i === activeIndex}">` +
          `<span>${esc(r.label)}</span></li>`,
      )
      .join('');
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  };

  /**
   * Verplaats de markering in de lijst.
   * @param {number} delta
   */
  const move = (delta) => {
    if (!results.length) return;
    activeIndex = (activeIndex + delta + results.length) % results.length;
    renderResults();
    input.setAttribute('aria-activedescendant', `pwSugg-${activeIndex}`);
    list.children[activeIndex]?.scrollIntoView({ block: 'nearest' });
  };

  /** @param {number} index */
  const choose = async (index) => {
    const item = results[index];
    if (!item) return;
    input.value = item.label;
    clearBtn.hidden = false;
    closeList();
    try {
      const hit = await pdokLookup(item.id);
      if (hit) onSelect(hit.lat, hit.lon, hit.label || item.label);
      else showNote('Deze plek heeft geen coördinaten. Kies een andere.');
    } catch (err) {
      if (!isAbortError(err)) showNote('Zoeken lukt nu niet. Klik op de kaart om verder te gaan.');
    }
  };

  const runFreeSearch = async () => {
    const q = input.value.trim();
    if (!q) return;
    closeList();
    try {
      const hit = await pdokFree(q);
      if (hit) {
        input.value = hit.label;
        onSelect(hit.lat, hit.lon, hit.label);
      } else {
        showNote('Geen plek gevonden met deze zoekterm.');
      }
    } catch (err) {
      if (!isAbortError(err)) showNote('Zoeken lukt nu niet. Klik op de kaart om verder te gaan.');
    }
  };

  const suggest = debounce(async () => {
    const q = input.value.trim();
    if (q.length < 3) {
      closeList();
      return;
    }
    if (controller) controller.abort();
    controller = new AbortController();
    try {
      const docs = await pdokSuggest(q, controller.signal);
      if (!docs.length) {
        showNote('Geen resultaten. Probeer een postcode of plaatsnaam.');
        return;
      }
      results = docs;
      activeIndex = -1;
      renderResults();
    } catch (err) {
      if (!isAbortError(err)) showNote('Zoeken lukt nu niet. Klik op de kaart om verder te gaan.');
    }
  }, 250);

  input.addEventListener('input', () => {
    clearBtn.hidden = input.value.trim() === '';
    suggest();
  });

  input.addEventListener('keydown', (ev) => {
    switch (ev.key) {
      case 'ArrowDown':
        ev.preventDefault();
        move(1);
        break;
      case 'ArrowUp':
        ev.preventDefault();
        move(-1);
        break;
      case 'Enter':
        ev.preventDefault();
        if (activeIndex >= 0) choose(activeIndex);
        else if (results.length) choose(0);
        else runFreeSearch();
        break;
      case 'Escape':
        if (!list.hidden) {
          ev.preventDefault();
          closeList();
        }
        break;
      default:
        break;
    }
  });

  // Muis/aanraking: focus bij het invoerveld houden zodat de lijst niet sluit.
  list.addEventListener('mousedown', (ev) => ev.preventDefault());
  list.addEventListener('click', (ev) => {
    const li = /** @type {HTMLElement} */ (ev.target).closest('.pw-sugg-item');
    if (!li) return;
    choose(Array.from(list.children).indexOf(li));
  });

  clearBtn.addEventListener('click', () => {
    input.value = '';
    clearBtn.hidden = true;
    closeList();
    input.focus();
  });

  document.addEventListener('click', (ev) => {
    if (!root.contains(/** @type {Node} */ (ev.target))) closeList();
  });
}

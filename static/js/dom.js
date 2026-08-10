/**
 * dom.js — kleine DOM- en tekst-helpers.
 *
 * Alle waarden uit de API gaan via `esc()` voordat ze in innerHTML belanden.
 */

/**
 * Maak tekst veilig voor innerHTML.
 * @param {unknown} value
 * @returns {string}
 */
export function esc(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

/**
 * document.querySelector met kortere naam.
 * @param {string} sel
 * @param {ParentNode} [root]
 * @returns {HTMLElement|null}
 */
export const qs = (sel, root = document) => root.querySelector(sel);

/**
 * document.querySelectorAll als echte array.
 * @param {string} sel
 * @param {ParentNode} [root]
 * @returns {HTMLElement[]}
 */
export const qsa = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/**
 * Toon of verberg een element via het hidden-attribuut.
 * @param {HTMLElement|null} node
 * @param {boolean} visible
 */
export function show(node, visible) {
  if (node) node.hidden = !visible;
}

/**
 * Is de waarde leeg (null, undefined, lege of enkel witruimte-string)?
 * @param {unknown} value
 * @returns {boolean}
 */
export function isEmpty(value) {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  return false;
}

/**
 * Geef een getrimde string terug, of '' bij een lege/ongeldige waarde.
 * Objecten en arrays leveren bewust '' op: die horen niet als tekst in de UI.
 * @param {unknown} value
 * @returns {string}
 */
export function text(value) {
  if (isEmpty(value)) return '';
  if (typeof value === 'object') return '';
  return String(value).trim();
}

/**
 * Wacht met uitvoeren tot er `ms` niets meer gebeurd is.
 * @template {(...args: any[]) => void} F
 * @param {F} fn
 * @param {number} ms
 * @returns {(...args: Parameters<F>) => void}
 */
export function debounce(fn, ms) {
  let timer = 0;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), ms);
  };
}

/**
 * Coördinaat netjes tonen (4 decimalen ≈ 10 meter).
 * @param {number} value
 * @returns {string}
 */
export function fmtCoord(value) {
  return Number(value).toFixed(4);
}

/**
 * Splits een samengestelde celwaarde ("zon / halfschaduw") in losse tokens.
 * @param {unknown} value
 * @returns {string[]}
 */
export function tokens(value) {
  return String(value ?? '')
    .split(/[/|;,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Eerste letter als hoofdletter (voor labels uit de dataset).
 * @param {string} value
 * @returns {string}
 */
export function capitalize(value) {
  const s = text(value);
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

/**
 * Positioneer een zwevend paneel onder een ankerelement, binnen het scherm.
 * @param {HTMLElement} panel Element met position:fixed.
 * @param {HTMLElement} anchor Knop of cel waar het paneel bij hoort.
 */
export function placeUnder(panel, anchor) {
  const margin = 8;
  panel.style.visibility = 'hidden';
  panel.hidden = false;
  const a = anchor.getBoundingClientRect();
  const p = panel.getBoundingClientRect();

  let left = a.left;
  if (left + p.width > window.innerWidth - margin) left = window.innerWidth - p.width - margin;
  if (left < margin) left = margin;

  let top = a.bottom + 6;
  if (top + p.height > window.innerHeight - margin) {
    const above = a.top - p.height - 6;
    top = above > margin ? above : Math.max(margin, window.innerHeight - p.height - margin);
  }

  panel.style.left = `${Math.round(left)}px`;
  panel.style.top = `${Math.round(top)}px`;
  panel.style.visibility = '';
}

let toastTimer = 0;

/**
 * Korte melding onderin beeld (bijv. "Rapport is nog niet beschikbaar").
 * @param {string} message
 * @param {number} [ms]
 */
export function toast(message, ms = 4000) {
  const node = qs('#toast');
  if (!node) return;
  node.textContent = message;
  node.hidden = false;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { node.hidden = true; }, ms);
}

/**
 * icons.js — inline SVG-iconen (Lucide-stijl, zelf ge-embed).
 *
 * Geen icon-CDN: elk icoon is hier als pad-data opgenomen. `icon()` geeft een
 * SVG-string terug die veilig in innerHTML gebruikt kan worden; de iconen zijn
 * decoratief en dus `aria-hidden`.
 */

/** @type {Record<string, string>} innerHTML per icoon (24×24 viewBox). */
const PATHS = {
  leaf:
    '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>' +
    '<path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
  leafSolid:
    '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" ' +
    'fill="currentColor" stroke="none"/>',
  compass:
    '<circle cx="12" cy="12" r="10"/>' +
    '<path d="m16.24 7.76-2.12 6.36-6.36 2.12 2.12-6.36 6.36-2.12z"/>',
  layers:
    '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/>' +
    '<path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>' +
    '<path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/>',
  droplet:
    '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',
  mountain:
    '<path d="m8 3 4 8 5-5 5 15H2L8 3z"/>',
  relief:
    '<path d="M2 20h20"/><path d="m3 20 5-10 3.5 6L15 11l6 9"/>',
  sprout:
    '<path d="M7 20h10"/>' +
    '<path d="M10 20c5.5-2.5.8-6.4 3-10"/>' +
    '<path d="M9.5 9.4c1.1.8 1.8 2.2 2.3 3.7-2 .4-3.5.4-4.8-.3-1.2-.6-2.3-1.9-3-4.2 2.8-.5 4.4 0 5.5.8z"/>' +
    '<path d="M14.1 6a7 7 0 0 0-1.1 4c1.9-.1 3.3-.6 4.3-1.4 1-1 1.6-2.3 1.7-4.6-2.7.1-4 1-4.9 2z"/>',
  info:
    '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  search:
    '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  x:
    '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  mapPin:
    '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
  crosshair:
    '<circle cx="12" cy="12" r="9"/><path d="M12 2v4"/><path d="M12 18v4"/>' +
    '<path d="M2 12h4"/><path d="M18 12h4"/>',
  sun:
    '<circle cx="12" cy="12" r="4"/>' +
    '<path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/>' +
    '<path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/>' +
    '<path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
  moon:
    '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  download:
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  fileText:
    '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>' +
    '<path d="M14 2v5h5"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
  columns:
    '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 3v18"/>',
  alert:
    '<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/>' +
    '<path d="M12 9v4"/><path d="M12 17h.01"/>',
  check:
    '<path d="M20 6 9 17l-5-5"/>',
  refresh:
    '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/>' +
    '<path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>',
  trees:
    '<path d="M10 10v.2A3 3 0 0 1 8.9 16H5a3 3 0 0 1-1-5.8V10a3 3 0 0 1 6 0Z"/>' +
    '<path d="M7 16v6"/><path d="M13 19v3"/>' +
    '<path d="M12 19h8.3a1 1 0 0 0 .7-1.7L18 14h.3a1 1 0 0 0 .7-1.7L16 9h.2a1 1 0 0 0 .8-1.7L13 3l-1.4 1.5"/>',
  chevronLeft:
    '<path d="m15 18-6-6 6-6"/>',
  chevronRight:
    '<path d="m9 18 6-6-6-6"/>',
};

/**
 * Bouw een SVG-string voor een icoon.
 * @param {keyof typeof PATHS} name Icoonnaam.
 * @param {{size?: number, className?: string}} [opts]
 * @returns {string} SVG-markup (leeg als de naam onbekend is).
 */
export function icon(name, opts = {}) {
  const body = PATHS[name];
  if (!body) return '';
  const size = opts.size || 24;
  const cls = opts.className ? ` class="${opts.className}"` : '';
  return (
    `<svg${cls} width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" ` +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
    `aria-hidden="true" focusable="false">${body}</svg>`
  );
}

/**
 * Marker-icoon voor de kaart (gevulde druppel met witte kern).
 * @returns {string} SVG-markup.
 */
export function markerSvg() {
  return (
    '<svg width="30" height="40" viewBox="0 0 30 40" fill="none" aria-hidden="true">' +
    '<path d="M15 39s13-13.4 13-24A13 13 0 1 0 2 15c0 10.6 13 24 13 24Z" ' +
    'fill="#1d5c3f" stroke="#ffffff" stroke-width="2.5"/>' +
    '<circle cx="15" cy="14.5" r="4.6" fill="#ffffff"/>' +
    '</svg>'
  );
}

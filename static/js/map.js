/**
 * map.js — Leaflet-kaart met OSM-basiskaart, WMS-overlays uit /api/wms_meta,
 * locatieknop, schaalbalk en de klik-marker.
 *
 * De kaart kent de rest van de app niet: hij roept alleen `onSelect(lat, lon)`
 * aan zodra de bezoeker een plek kiest.
 */

import { getWmsMeta } from './api.js';
import { icon, markerSvg } from './icons.js';
import { esc } from './dom.js';

/** Volgorde en NL-namen van de overlays; `key` verwijst naar /api/wms_meta. */
const LAYER_DEFS = [
  { key: 'fgr', name: "Landschapsregio's (FGR)", on: true, opacity: 0.35 },
  { key: 'bodem', name: 'Bodemkaart', on: false, opacity: 0.6 },
  { key: 'gt', name: 'Grondwatertrappen (Gt)', on: false, opacity: 0.6 },
  { key: 'gmm', name: 'Landvormen (geomorfologie)', on: false, opacity: 0.6 },
  { key: 'ahn', name: 'Hoogtekaart (AHN)', on: false, opacity: 0.6 },
];

const NL_CENTER = [52.15, 5.4];
const NL_BOUNDS = [[50.6, 3.1], [53.7, 7.4]];

/**
 * Bouw de kaart op.
 * @param {{container: HTMLElement, onSelect: (lat:number, lon:number) => void}} opts
 * @returns {{
 *   map: any,
 *   setMarker: (lat:number, lon:number) => void,
 *   clearMarker: () => void,
 *   focus: (lat:number, lon:number, zoom?:number) => void,
 *   panIntoView: (lat:number, lon:number, coveredPx:number) => void,
 *   invalidate: () => void
 * }}
 */
export function initMap({ container, onSelect }) {
  const map = L.map(container, {
    center: NL_CENTER,
    zoom: 8,
    minZoom: 6,
    maxZoom: 19,
    zoomControl: false,
    maxBounds: L.latLngBounds(NL_BOUNDS).pad(0.6),
    attributionControl: true,
  });

  map.attributionControl.setPrefix('');
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>-bijdragers',
  }).addTo(map);

  L.control.zoom({ position: 'bottomright', zoomInTitle: 'Inzoomen', zoomOutTitle: 'Uitzoomen' }).addTo(map);
  L.control.scale({ position: 'bottomleft', imperial: false, maxWidth: 120 }).addTo(map);

  addLocateControl(map);
  const layersControl = addLayersControl(map);
  loadOverlays(map, layersControl);

  /** @type {any} */
  let marker = null;

  map.on('click', (ev) => {
    if (!ev || !ev.latlng) return;
    onSelect(ev.latlng.lat, ev.latlng.lng);
  });

  // Toetsenbord: Enter op de kaart kiest het midden, zodat de kaart ook zonder
  // muis bruikbaar is (Leaflet ondersteunt pannen/zoomen al met pijltjes).
  container.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Enter' || ev.target !== container) return;
    ev.preventDefault();
    const c = map.getCenter();
    onSelect(c.lat, c.lng);
  });

  const resize = () => window.setTimeout(() => map.invalidateSize({ animate: false }), 80);
  window.addEventListener('resize', resize);
  window.addEventListener('orientationchange', resize);

  return {
    map,

    setMarker(lat, lon) {
      if (marker) marker.remove();
      marker = L.marker([lat, lon], {
        keyboard: false,
        icon: L.divIcon({
          className: 'pw-marker',
          html: `<span class="pw-marker-ring"></span><span class="pw-marker-drop">${markerSvg()}</span>`,
          iconSize: [30, 40],
          iconAnchor: [15, 40],
        }),
        alt: 'Gekozen plek',
      }).addTo(map);
    },

    clearMarker() {
      if (marker) marker.remove();
      marker = null;
    },

    focus(lat, lon, zoom) {
      map.setView([lat, lon], zoom || Math.max(map.getZoom(), 14), { animate: true });
    },

    panIntoView(lat, lon, coveredPx) {
      if (!coveredPx || coveredPx <= 0) return;
      const size = map.getSize();
      const point = map.latLngToContainerPoint([lat, lon]);
      const visibleBottom = size.y - coveredPx;
      if (point.y <= visibleBottom - 30) return;
      const shift = point.y - visibleBottom / 2;
      map.panBy([0, Math.round(shift)], { animate: true });
    },

    invalidate: resize,
  };
}

/**
 * Knop "Mijn locatie" (geolocatie van de browser).
 * @param {any} map
 */
function addLocateControl(map) {
  const Control = L.Control.extend({
    options: { position: 'bottomright' },
    onAdd() {
      const wrap = L.DomUtil.create('div', 'leaflet-control');
      const btn = L.DomUtil.create('button', 'pw-ctl-btn', wrap);
      btn.type = 'button';
      btn.title = 'Ga naar mijn locatie';
      btn.setAttribute('aria-label', 'Ga naar mijn locatie');
      btn.innerHTML = icon('crosshair');

      L.DomEvent.on(btn, 'click', (ev) => {
        L.DomEvent.stop(ev);
        if (!navigator.geolocation) {
          map.fire('pw:locateerror', { message: 'Deze browser kan je locatie niet doorgeven.' });
          return;
        }
        btn.setAttribute('aria-busy', 'true');
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            btn.removeAttribute('aria-busy');
            map.fire('click', { latlng: L.latLng(pos.coords.latitude, pos.coords.longitude) });
            map.setView([pos.coords.latitude, pos.coords.longitude], 15);
          },
          () => {
            btn.removeAttribute('aria-busy');
            map.fire('pw:locateerror', {
              message: 'We kregen je locatie niet. Zoek je adres of klik op de kaart.',
            });
          },
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
        );
      });
      L.DomEvent.disableClickPropagation(wrap);
      return wrap;
    },
  });
  map.addControl(new Control());
}

/**
 * Lagenpicker: knop rechtsboven met een uitklappaneel vol checkboxen en
 * doorzichtigheid-schuiven.
 * @param {any} map
 * @returns {{setLayers: (rows: {def:Object, layer:any}[]) => void, setError: () => void}}
 */
function addLayersControl(map) {
  let listEl = null;
  let panelEl = null;
  let buttonEl = null;

  const Control = L.Control.extend({
    options: { position: 'topright' },
    onAdd() {
      const wrap = L.DomUtil.create('div', 'leaflet-control pw-layers-ctl');

      const btn = L.DomUtil.create('button', 'pw-ctl-btn', wrap);
      btn.type = 'button';
      btn.title = 'Kaartlagen';
      btn.setAttribute('aria-label', 'Kaartlagen tonen of verbergen');
      btn.setAttribute('aria-expanded', 'false');
      btn.innerHTML = icon('layers');
      buttonEl = btn;

      const panel = L.DomUtil.create('div', 'pw-ctl pw-layers-panel', wrap);
      panel.hidden = true;
      panel.innerHTML =
        '<h2 class="pw-layers-title">Kaartlagen</h2>' +
        '<p class="pw-layers-sub">Leg een landelijke kaart over de basiskaart. ' +
        'Met de schuif regel je hoe sterk hij doorkomt.</p>' +
        '<div class="pw-layers-list"></div>';
      panelEl = panel;
      listEl = panel.querySelector('.pw-layers-list');

      L.DomEvent.on(btn, 'click', (ev) => {
        L.DomEvent.stop(ev);
        const open = panel.hidden;
        panel.hidden = !open;
        btn.setAttribute('aria-expanded', String(open));
      });
      L.DomEvent.on(panel, 'keydown', (ev) => {
        if (ev.key === 'Escape') {
          panel.hidden = true;
          btn.setAttribute('aria-expanded', 'false');
          btn.focus();
        }
      });

      L.DomEvent.disableClickPropagation(wrap);
      L.DomEvent.disableScrollPropagation(wrap);
      return wrap;
    },
  });

  map.addControl(new Control());
  map.on('click', () => {
    if (panelEl && !panelEl.hidden) {
      panelEl.hidden = true;
      if (buttonEl) buttonEl.setAttribute('aria-expanded', 'false');
    }
  });

  return {
    setLayers(rows) {
      if (!listEl) return;
      listEl.innerHTML = rows
        .map(({ def }, i) => {
          const id = `layer-${def.key}`;
          const pct = Math.round(def.opacity * 100);
          return (
            `<div class="pw-layer">
               <label class="pw-layer-row">
                 <input type="checkbox" id="${id}" data-index="${i}" ${def.on ? 'checked' : ''}>
                 <span>${esc(def.name)}</span>
               </label>
               <div class="pw-layer-opacity">
                 <input type="range" min="0" max="100" step="5" value="${pct}" data-opacity="${i}"
                        aria-label="Doorzichtigheid van ${esc(def.name)}">
                 <output>${pct}%</output>
               </div>
             </div>`
          );
        })
        .join('');

      listEl.addEventListener('change', (ev) => {
        const target = /** @type {HTMLInputElement} */ (ev.target);
        if (target.type !== 'checkbox') return;
        const row = rows[Number(target.dataset.index)];
        if (!row) return;
        if (target.checked) row.layer.addTo(map);
        else map.removeLayer(row.layer);
      });

      listEl.addEventListener('input', (ev) => {
        const target = /** @type {HTMLInputElement} */ (ev.target);
        if (target.type !== 'range') return;
        const row = rows[Number(target.dataset.opacity)];
        if (!row) return;
        const value = Number(target.value) / 100;
        row.layer.setOpacity(value);
        const out = target.parentElement?.querySelector('output');
        if (out) out.textContent = `${Math.round(value * 100)}%`;
      });
    },

    setError() {
      if (!listEl) return;
      listEl.innerHTML =
        '<p class="pw-layers-sub">De kaartlagen zijn nu niet beschikbaar. ' +
        'De basiskaart en het advies werken gewoon.</p>';
    },
  };
}

/**
 * Haal /api/wms_meta op en zet de overlays klaar.
 * @param {any} map
 * @param {{setLayers: Function, setError: Function}} control
 */
async function loadOverlays(map, control) {
  let meta;
  try {
    meta = await getWmsMeta();
  } catch (err) {
    control.setError();
    return;
  }

  const rows = [];
  for (const def of LAYER_DEFS) {
    const entry = meta && meta[def.key];
    if (!entry || !entry.url || !entry.layer) continue;
    const layer = L.tileLayer.wms(entry.url, {
      layers: entry.layer,
      transparent: true,
      format: 'image/png',
      version: '1.3.0',
      crs: L.CRS.EPSG3857,
      opacity: def.opacity,
    });
    if (def.on) layer.addTo(map);
    rows.push({ def, layer });
  }

  if (!rows.length) control.setError();
  else control.setLayers(rows);
}

/**
 * sheet.js — bottom-sheet voor het adviespaneel op mobiel.
 *
 * Drie standen: `peek` (alleen de greep en de titel), `half` (ongeveer de halve
 * hoogte) en `full`. Slepen kan aan de greep; met het toetsenbord wisselt de
 * greepknop tussen de standen. Op desktop (≥900px) doet deze module niets.
 */

const SNAPS = /** @type {const} */ (['peek', 'half', 'full']);
const MOBILE_QUERY = '(max-width: 899px)';

/**
 * @param {{pane: HTMLElement, head: HTMLElement, grip: HTMLElement}} refs
 * @returns {{
 *   isMobile: () => boolean,
 *   getSnap: () => 'peek'|'half'|'full',
 *   setSnap: (snap: 'peek'|'half'|'full') => void,
 *   coveredHeight: () => number
 * }}
 */
export function initSheet({ pane, head, grip }) {
  const mq = window.matchMedia(MOBILE_QUERY);
  /** @type {'peek'|'half'|'full'} */
  let snap = 'half';

  const isMobile = () => mq.matches;

  /** Hoogte van de greep+titel, ofwel wat er in de `peek`-stand zichtbaar is. */
  function peekHeight() {
    const raw = getComputedStyle(document.documentElement).getPropertyValue('--peek-h');
    const px = Number.parseFloat(raw);
    return Number.isFinite(px) && px > 0 ? px : 104;
  }

  /**
   * Verschuiving (translateY in px) per stand.
   * @returns {{peek:number, half:number, full:number}}
   */
  function offsets() {
    const height = pane.offsetHeight || window.innerHeight;
    return {
      full: 0,
      half: Math.max(0, height - Math.round(window.innerHeight * 0.46)),
      peek: Math.max(0, height - peekHeight()),
    };
  }

  /** Huidige verschuiving in px. */
  function currentOffset() {
    return offsets()[snap];
  }

  /** @param {'peek'|'half'|'full'} next */
  function setSnap(next) {
    snap = SNAPS.includes(next) ? next : 'half';
    pane.style.transform = '';
    pane.classList.remove('is-peek', 'is-half', 'is-full');
    pane.classList.add(`is-${snap}`);
    grip.setAttribute('aria-expanded', String(snap === 'full'));
  }

  /* ── slepen ── */
  let dragging = false;
  let startY = 0;
  let startOffset = 0;
  let lastY = 0;
  let lastTime = 0;
  let velocity = 0;
  let moved = 0;

  head.addEventListener('pointerdown', (ev) => {
    if (!isMobile() || ev.button !== 0) return;
    dragging = true;
    moved = 0;
    startY = ev.clientY;
    lastY = ev.clientY;
    lastTime = ev.timeStamp;
    velocity = 0;
    startOffset = currentOffset();
    pane.classList.add('is-dragging');
    head.setPointerCapture(ev.pointerId);
  });

  head.addEventListener('pointermove', (ev) => {
    if (!dragging) return;
    const bounds = offsets();
    const delta = ev.clientY - startY;
    moved = Math.max(moved, Math.abs(delta));
    const next = Math.min(bounds.peek, Math.max(0, startOffset + delta));
    pane.style.transform = `translateY(${next}px)`;

    const dt = ev.timeStamp - lastTime;
    if (dt > 0) velocity = (ev.clientY - lastY) / dt;
    lastY = ev.clientY;
    lastTime = ev.timeStamp;
  });

  const endDrag = (ev) => {
    if (!dragging) return;
    dragging = false;
    pane.classList.remove('is-dragging');
    if (ev.pointerId !== undefined && head.hasPointerCapture?.(ev.pointerId)) {
      head.releasePointerCapture(ev.pointerId);
    }
    if (moved < 6) {
      pane.style.transform = '';
      return; // Geen sleep maar een klik: de knop handelt dat af.
    }

    const bounds = offsets();
    const currentPx = startOffset + (lastY - startY);

    // Duidelijke veegbeweging: één stand op- of afschalen.
    if (Math.abs(velocity) > 0.6) {
      const index = SNAPS.indexOf(snap);
      const next = velocity < 0 ? Math.min(index + 1, SNAPS.length - 1) : Math.max(index - 1, 0);
      setSnap(SNAPS[next]);
      return;
    }

    // Anders: naar de dichtstbijzijnde stand.
    let best = 'half';
    let bestDist = Infinity;
    for (const name of SNAPS) {
      const dist = Math.abs(bounds[name] - currentPx);
      if (dist < bestDist) {
        bestDist = dist;
        best = name;
      }
    }
    setSnap(/** @type {'peek'|'half'|'full'} */ (best));
  };

  head.addEventListener('pointerup', endDrag);
  head.addEventListener('pointercancel', endDrag);

  grip.addEventListener('click', () => {
    if (!isMobile()) return;
    const index = SNAPS.indexOf(snap);
    setSnap(SNAPS[(index + 1) % SNAPS.length]);
  });

  grip.addEventListener('keydown', (ev) => {
    if (!isMobile()) return;
    const index = SNAPS.indexOf(snap);
    if (ev.key === 'ArrowUp') {
      ev.preventDefault();
      setSnap(SNAPS[Math.min(index + 1, SNAPS.length - 1)]);
    } else if (ev.key === 'ArrowDown') {
      ev.preventDefault();
      setSnap(SNAPS[Math.max(index - 1, 0)]);
    }
  });

  // Bij wisselen naar desktop de inline stijl opruimen.
  mq.addEventListener('change', () => {
    pane.style.transform = '';
    if (mq.matches) setSnap(snap);
  });

  setSnap('half');

  return {
    isMobile,
    getSnap: () => snap,
    setSnap,
    coveredHeight() {
      if (!isMobile()) return 0;
      const height = pane.offsetHeight || 0;
      return Math.max(0, height - currentOffset());
    },
  };
}

"""The showcase's gallery (showcase.ps1): /out/index.html, one page that works offline from the showcase folder.

Pick a version on the timeline, a page and laptop / phone; Compare puts another version beside it. Left / right arrow
keys step through the versions. Reads /out/versions.json (what each version had, from git).
"""
import json

versions = json.load(open("/out/versions.json", encoding="utf-8-sig"))
PAGE_NAMES = {"home": "Home", "supplies": "Supplies", "models": "Models", "boardgames": "Board games", "volleyball": "Volleyball",
              "videogames": "Video games", "chess": "Chess", "reading": "Reading", "hiking": "Hiking", "gardening": "Gardening",
              "shooting": "Precision shooting", "travel": "Travel", "goals": "Goals", "journal": "Journal", "calendar": "Calendar"}

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Off the Clock - how it's grown</title>
<style>
  :root { --bg: #f3eee3; --card: #fbf8f1; --ink: #1f2a22; --muted: #5d6656; --line: #d9d1bf; --pine: #24382c; --moss: #6b7f4a;
          --amber: #b8742a; --serif: Georgia, "Times New Roman", serif; --sans: system-ui, -apple-system, "Segoe UI", sans-serif; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #141a16; --card: #1d251f; --ink: #ece6d8; --muted: #a9b09c; --line: #334036; --pine: #cfe0c6; --moss: #9fb57a; --amber: #e0a35a; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.5 var(--sans); }
  header { padding: 40px 24px 8px; max-width: 1500px; margin: 0 auto; }
  h1 { font: 600 clamp(28px, 4vw, 44px)/1.1 var(--serif); margin: 0 0 6px; color: var(--pine); }
  .sub { color: var(--muted); margin: 0; }
  main { max-width: 1500px; margin: 0 auto; padding: 16px 24px 64px; }
  .timeline { display: flex; gap: 10px; overflow-x: auto; padding: 14px 2px 18px; scroll-snap-type: x proximity; }
  .ver { flex: 0 0 auto; scroll-snap-align: start; text-align: left; min-width: 150px; padding: 12px 14px; border-radius: 14px;
         border: 1px solid var(--line); background: var(--card); color: var(--ink); cursor: pointer; font: inherit; position: relative; }
  .ver small { display: block; color: var(--muted); font-size: 12px; letter-spacing: .02em; }
  .ver b { font: 600 17px/1.25 var(--serif); }
  .ver[aria-pressed="true"] { border-color: var(--moss); box-shadow: 0 0 0 2px var(--moss) inset; }
  .ver.b-pick { box-shadow: 0 0 0 2px var(--amber) inset; border-color: var(--amber); }
  .ver .tag { position: absolute; top: 8px; right: 10px; font-size: 11px; font-weight: 700; color: var(--amber); }
  .note { margin: 0 0 14px; color: var(--muted); max-width: 70ch; }
  .controls { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; margin-bottom: 18px; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip, .seg button { font: inherit; font-size: 14px; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--line);
         background: var(--card); color: var(--ink); cursor: pointer; }
  .chip[aria-pressed="true"], .seg button[aria-pressed="true"] { background: var(--pine); color: var(--bg); border-color: var(--pine); }
  .chip:disabled { opacity: .4; cursor: default; }
  .seg { display: inline-flex; gap: 4px; }
  .compare-hint { color: var(--muted); font-size: 14px; }
  .view { display: grid; gap: 22px; grid-template-columns: repeat(var(--cols), minmax(0, 1fr)); align-items: start; }
  figure { margin: 0; background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 12px; }
  figcaption { font-size: 14px; color: var(--muted); margin: 0 4px 10px; }
  figcaption b { color: var(--ink); font-family: var(--serif); font-size: 16px; }
  figure img { display: block; width: 100%; height: auto; border-radius: 10px; border: 1px solid var(--line); }
  .phone figure img { max-width: 390px; margin: 0 auto; border-radius: 22px; }
  .missing { padding: 60px 20px; text-align: center; color: var(--muted); border: 1px dashed var(--line); border-radius: 10px; }
  a.full { color: inherit; }
  footer { color: var(--muted); font-size: 13px; text-align: center; padding: 0 24px 40px; }
  @media (max-width: 760px) { .view { grid-template-columns: 1fr; } header { padding-top: 24px; } main, header { padding-left: 16px; padding-right: 16px; } }
</style>
</head>
<body>
<header>
  <h1>Off the Clock - how it's grown</h1>
  <p class="sub">The same pages from each big step in the look, with made-up sample data. Pick a version, a page, laptop or phone - or compare two.</p>
</header>
<main>
  <div class="timeline" id="timeline" role="group" aria-label="Versions"></div>
  <p class="note" id="note"></p>
  <div class="controls">
    <div class="chips" id="pages" role="group" aria-label="Page"></div>
    <div class="seg" role="group" aria-label="Size">
      <button type="button" data-size="pc" aria-pressed="true">Laptop</button>
      <button type="button" data-size="phone" aria-pressed="false">Phone</button>
    </div>
    <div class="seg" role="group" aria-label="Compare">
      <button type="button" id="compare" aria-pressed="false">Compare</button>
    </div>
    <span class="compare-hint" id="hint" hidden>Now pick a second version on the timeline.</span>
  </div>
  <div class="view" id="view"></div>
</main>
<footer>Made with showcase.ps1. Old versions are shown against today's sample data, so the odd number may be missing.</footer>
<script>
const VERSIONS = __VERSIONS__;
const NAMES = __NAMES__;
const taken = VERSIONS.filter((v) => v.taken);
const state = { a: taken.length - 1, b: null, page: 'home', size: 'pc', comparing: false };

function el(tag, props = {}, ...kids) { const e = Object.assign(document.createElement(tag), props); e.append(...kids); return e; }

function render() {
  const A = taken[state.a], B = state.b != null ? taken[state.b] : null;
  const tl = document.getElementById('timeline'); tl.replaceChildren();
  taken.forEach((v, i) => {
    const b = el('button', { type: 'button', className: 'ver' + (state.comparing && i === state.b ? ' b-pick' : '') },
      el('small', {}, v.date), el('b', {}, v.title));
    b.setAttribute('aria-pressed', String(i === state.a));
    if (state.comparing && i === state.b) b.append(el('span', { className: 'tag' }, 'B'));
    if (state.comparing && i === state.a) b.append(el('span', { className: 'tag' }, 'A'));
    b.onclick = () => { if (state.comparing) { if (i !== state.a) state.b = i; } else state.a = i; render(); };
    tl.append(b);
  });
  document.getElementById('note').textContent = A.note;
  document.getElementById('hint').hidden = !(state.comparing && state.b == null);
  const pages = document.getElementById('pages'); pages.replaceChildren();
  const has = new Set([...A.pages, ...(B ? B.pages : [])]);
  if (!has.has(state.page)) state.page = 'home';
  Object.keys(NAMES).forEach((k) => {
    const c = el('button', { type: 'button', className: 'chip', disabled: !has.has(k), title: has.has(k) ? '' : 'Not built yet' }, NAMES[k]);
    c.setAttribute('aria-pressed', String(k === state.page));
    c.onclick = () => { state.page = k; render(); };
    pages.append(c);
  });
  document.querySelectorAll('[data-size]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.size === state.size)));
  document.getElementById('compare').setAttribute('aria-pressed', String(state.comparing));
  const view = document.getElementById('view');
  const shown = [A, ...(state.comparing && B ? [B] : [])].sort((x, y) => taken.indexOf(x) - taken.indexOf(y));
  view.style.setProperty('--cols', state.size === 'phone' ? Math.max(shown.length, 1) : shown.length);
  view.className = 'view' + (state.size === 'phone' ? ' phone' : '');
  view.replaceChildren(...shown.map((v) => {
    const src = `${v.key}/${state.page}_${state.size}.jpg`;
    const body = v.pages.includes(state.page)
      ? el('a', { href: src, target: '_blank', className: 'full', title: 'Open full size' }, el('img', { src, alt: `${NAMES[state.page]} in ${v.title}`, loading: 'lazy' }))
      : el('div', { className: 'missing' }, `${NAMES[state.page]} wasn't built yet in ${v.title}.`);
    return el('figure', {}, el('figcaption', {}, el('b', {}, v.title), ` - ${v.date}`), body);
  }));
}
document.querySelectorAll('[data-size]').forEach((b) => { b.onclick = () => { state.size = b.dataset.size; render(); }; });
document.getElementById('compare').onclick = () => {
  state.comparing = !state.comparing;
  state.b = state.comparing ? (state.a > 0 ? 0 : null) : null;
  render();
};
document.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowLeft' && state.a > 0) { state.a--; if (state.b === state.a) state.b = null; render(); }
  if (e.key === 'ArrowRight' && state.a < taken.length - 1) { state.a++; if (state.b === state.a) state.b = null; render(); }
});
render();
</script>
</body>
</html>
"""

page = HTML.replace("__VERSIONS__", json.dumps(versions)).replace("__NAMES__", json.dumps(PAGE_NAMES))
open("/out/index.html", "w", encoding="utf-8").write(page)
print(f"gallery: {sum(v['taken'] for v in versions)} versions")

# UI Foundation Redesign (Quiet Confidence tokens + top nav) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ApexOS's color/type tokens and sidebar+topbar chrome with the "Quiet Confidence"
palette and a single top nav bar, so every existing page inherits the new look with zero template
rewrites.

**Architecture:** Two files change: `apps/api/app/web/static/app.css` (CSS custom-property values, base
type, and the sidebar/topbar→topnav selectors) and `apps/api/app/web/templates/base.html` (markup: one
`<header class="topnav">` replaces the old `<aside class="sidebar">` + `<header class="topbar">` pair).
Every other template is untouched — they reference `.card`, `.grid-N`, `.stat-tile`, etc., which keep
their names and just render with new token values.

**Tech Stack:** Jinja2 templates, plain CSS custom properties (no preprocessor, no build step).

## Global Constraints

- Source of truth for the design: `docs/superpowers/specs/2026-07-31-ui-redesign-design.md`.
- **Foundation-only scope**: no template other than `base.html` is modified. No `.block`/board-grid span
  classes are introduced — those are explicitly deferred to a future spec.
- No data model, route, or business-logic changes.
- Verify loop (per `CLAUDE.md`/`docs/STANDING-RULES.md`), run from `apps/api` with the venv active:
  `python -m pytest -q` (expect **819 passed**, matching `PROGRESS.md`'s current baseline) and
  `python -m ruff check app/ tests/` (expect **exactly 35** findings — this change must add zero new
  ones).
- This work is out-of-band from the Part 11 roadmap in flight — it does not touch `PROGRESS.md`'s
  `▶ CURRENT WORK` block, which stays owned by the roadmap session.
- Nothing in `--text` below 11px anywhere in the stylesheet (the spec's stated floor).

---

## File Structure

- **Modify:** `apps/api/app/web/static/app.css` — token values (light + dark), base body type, the one
  sub-11px text rule, serif display type on `h1`/`.stat-value`, and the sidebar+topbar→topnav selector
  block (including the print media query and the 640px mobile breakpoint).
- **Modify:** `apps/api/app/web/templates/base.html` — replace the `<aside class="sidebar">` +
  `<header class="topbar">` structure with one `<header class="topnav">`, iterating `NAV_ITEMS` as a flat
  list (no `SECTION_LABELS` grouping — decided in the spec).
- **No files created.** No test files created — the existing page-walk smoke test
  (`apps/api/tests/test_web_smoke.py`) is the regression gate for this change, since it already renders
  every registered page and every masters slug and asserts `200` + `text/html`.

---

### Task 1: Design tokens — light and dark palettes

**Files:**
- Modify: `apps/api/app/web/static/app.css:1-32`

**Interfaces:**
- Produces: CSS custom properties consumed by every other rule in the file — `--bg`, `--panel`,
  `--panel-2`, `--border`, `--border-strong`, `--text`, `--muted`, `--faint`, `--accent`,
  `--accent-weak`, `--accent-ink` (new), `--ok-bg`/`--ok-fg`, `--warn-bg`/`--warn-fg`,
  `--bad-bg`/`--bad-fg`, `--muted-bg`/`--muted-fg`, `--radius`, `--font-display` (new), `--font`.
  `--sidebar-w` is removed (its only consumers, `.sidebar`/`.shell`, are removed in Task 5).

- [ ] **Step 1: Confirm the current baseline passes before touching anything**

Run (from `apps/api`, venv active):
```
python -m pytest -q
python -m ruff check app/ tests/
```
Expected: `819 passed`, ruff reports exactly `35`. If these don't match, stop and reconcile with
`PROGRESS.md` before proceeding — this plan assumes that starting point.

- [ ] **Step 2: Replace the root token block**

Replace the full block from the top of the file through the end of the dark-mode media query
(`apps/api/app/web/static/app.css:1-32`, i.e. from the header comment through the closing `}` of
`@media (prefers-color-scheme: dark) { ... }`) with:

```css
/* ApexOS server-rendered UI — Quiet Confidence: warm, considered, keyboard-first. */
:root {
  --bg: #faf8f4;
  --panel: #ffffff;
  --panel-2: #f4f0e8;
  --border: #e8e2d6;
  --border-strong: #d8d0bf;
  --text: #22201b;
  --muted: #736b5c;
  --faint: #a39a87;
  --accent: #a8582f;
  --accent-weak: #f7ece3;
  --accent-ink: #7a3f1f;
  --ok-bg: #eaf3e9; --ok-fg: #3a6b3d;
  --warn-bg: #fbf0dc; --warn-fg: #8a5a12;
  --bad-bg: #faeae6; --bad-fg: #a13f26;
  --muted-bg: #f4f0e8; --muted-fg: #736b5c;
  --radius: 12px;
  --font-display: "Iowan Old Style", Georgia, serif;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1b1815; --panel: #242019; --panel-2: #2b261e;
    --border: #3a342a; --border-strong: #4a4335;
    --text: #f1ece2; --muted: #b3a892; --faint: #8a7d64;
    --accent: #e08a5b; --accent-weak: #3a2a1c; --accent-ink: #f3b58c;
    --ok-bg: #1c2b1d; --ok-fg: #8fce93;
    --warn-bg: #332812; --warn-fg: #e8b862;
    --bad-bg: #331f19; --bad-fg: #e88a6b;
    --muted-bg: #2b261e; --muted-fg: #b3a892;
  }
}
```

- [ ] **Step 3: Sanity-check no other rule references the removed `--sidebar-w` with a fallback that would break**

Run: `grep -n "sidebar-w" apps/api/app/web/static/app.css`
Expected: two hits, both inside the `.sidebar`/`.shell` rules that Task 5 removes. If Task 5 hasn't run
yet, this is expected and harmless (an undefined custom property just resolves to its property's initial
value — it does not error).

- [ ] **Step 4: Commit**

```bash
cd "apps/api"
git add app/web/static/app.css
git commit -m "style: replace UI color/font tokens with the Quiet Confidence palette"
```

---

### Task 2: Base type size and the one sub-11px text rule

**Files:**
- Modify: `apps/api/app/web/static/app.css` (the `body` rule, originally lines 36-43; the `.tag` rule,
  originally lines 294-298 — line numbers will have shifted slightly after Task 1's edit, search by
  selector instead of line number)

**Interfaces:**
- Consumes: `--font`, `--bg`, `--text` from Task 1.
- Produces: no new selectors — same `body` and `.tag` rules, new values only.

- [ ] **Step 1: Bump the base body font size**

Find the `body` rule (originally):
```css
body {
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
```
Change `font-size: 14px;` to `font-size: 15px;` and `line-height: 1.5;` to `line-height: 1.55;`. Leave
everything else in the rule unchanged.

- [ ] **Step 2: Fix the one text rule under the 11px floor**

Find the `.tag` rule (originally):
```css
.tag {
  display: inline-block; margin-left: 6px; padding: 1px 7px; border-radius: 999px;
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
  background: var(--ok-bg); color: var(--ok-fg); vertical-align: middle;
}
```
Change `font-size: 10px;` to `font-size: 11px;`. Leave everything else unchanged.

- [ ] **Step 3: Confirm no other rule in the file sets a font-size below 11px**

Run: `grep -noE "font-size:\s*[0-9]+px" apps/api/app/web/static/app.css | sort -t: -k3 -n | head -5`
Expected: the smallest value listed is `11px` (from `thead th`, `.explain-weight`, `.sort-arrow`, or the
now-fixed `.tag` — several rules legitimately sit at exactly 11px, which is the floor, not a violation).
If anything below `11px` shows up, fix it the same way as Step 2.

- [ ] **Step 4: Visually confirm via the existing page-walk smoke test that nothing broke**

Run (from `apps/api`, venv active): `python -m pytest -q tests/test_web_smoke.py`
Expected: all cases pass (this test only checks status code + content-type, not visual appearance, but a
malformed CSS edit that broke Jinja rendering — it wouldn't, since this is a separate static file — would
still be caught here as a sanity net).

- [ ] **Step 5: Commit**

```bash
cd "apps/api"
git add app/web/static/app.css
git commit -m "style: raise base body type size and fix the one sub-11px text rule"
```

---

### Task 3: Serif display type on headings and stat values

**Files:**
- Modify: `apps/api/app/web/static/app.css` (the `.page-header h1` rule, originally line 87; the
  `.stat-value` rule, originally line 114)

**Interfaces:**
- Consumes: `--font-display` from Task 1.

- [ ] **Step 1: Apply the display face to page titles**

Find:
```css
.page-header h1 { font-size: 22px; font-weight: 650; margin: 0; }
```
Replace with:
```css
.page-header h1 { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin: 0; letter-spacing: -.01em; }
```

- [ ] **Step 2: Apply the display face to stat values**

Find:
```css
.stat-value { font-size: 24px; font-weight: 680; margin-top: 6px; letter-spacing: -.01em; }
```
Replace with:
```css
.stat-value { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin-top: 6px; letter-spacing: -.01em; }
```

- [ ] **Step 3: Commit**

```bash
cd "apps/api"
git add app/web/static/app.css
git commit -m "style: use the serif display face for page titles and stat values"
```

---

### Task 4: Replace the sidebar + topbar markup with a single top nav

**Files:**
- Modify: `apps/api/app/web/templates/base.html` (the whole file — it is 45 lines)

**Interfaces:**
- Consumes: `NAV_ITEMS` (`list[dict[str, str]]`, each `{"label": str, "href": str, "section": str}`) and
  `APP_NAME` (`str`), both already registered as Jinja globals in `apps/api/app/web/core.py:224-231`.
  `SECTION_LABELS` is **not** consumed by the new markup — the spec decided the top nav is a flat row,
  no grouping.
- Produces: `<header class="topnav">` containing `.topnav-brand`, `.topnav-links` (with one
  `.topnav-link` per `NAV_ITEMS` entry, `.active` class on the current page's link), and
  `.topnav-actor`. `<main class="content">` is unchanged in role (still holds `{% block flash %}` and
  `{% block content %}`).

- [ ] **Step 1: Replace the file contents**

The current file is:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{% block title %}{{ APP_NAME }}{% endblock %} · {{ APP_NAME }}</title>
  <link rel="stylesheet" href="/static/app.css" />
</head>
<body>
  <aside class="sidebar">
    <div class="brand"><span class="brand-mark">◆</span> {{ APP_NAME }}</div>
    <nav>
      {% set current = request.url.path %}
      {% for section in ["main", "work", "system"] %}
        {% if SECTION_LABELS[section] %}
          <div class="nav-section">{{ SECTION_LABELS[section] }}</div>
        {% endif %}
        {% for item in NAV_ITEMS if item.section == section %}
          {% set active = (current == item.href) if item.href == "/" else current.startswith(item.href) %}
          <a class="nav-item {{ 'active' if active else '' }}" href="{{ item.href }}">{{ item.label }}</a>
        {% endfor %}
      {% endfor %}
    </nav>
  </aside>

  <div class="shell">
    <header class="topbar">
      <div class="topbar-title">{% block topbar %}{{ self.title() }}{% endblock %}</div>
      <div class="topbar-actor">Apex Founder · founder@apexsupply.example</div>
    </header>
    <main class="content">
      {% block flash %}
        {% if request.query_params.get("ok") %}
          <div class="flash flash-ok">{{ request.query_params.get("ok") }}</div>
        {% endif %}
        {% if request.query_params.get("err") %}
          <div class="flash flash-bad">{{ request.query_params.get("err") }}</div>
        {% endif %}
      {% endblock %}
      {% block content %}{% endblock %}
    </main>
  </div>
</body>
</html>
```

Replace it with:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{% block title %}{{ APP_NAME }}{% endblock %} · {{ APP_NAME }}</title>
  <link rel="stylesheet" href="/static/app.css" />
</head>
<body>
  <header class="topnav">
    <div class="topnav-brand"><span class="brand-mark">◆</span> {{ APP_NAME }}</div>
    <nav class="topnav-links">
      {% set current = request.url.path %}
      {% for item in NAV_ITEMS %}
        {% set active = (current == item.href) if item.href == "/" else current.startswith(item.href) %}
        <a class="topnav-link {{ 'active' if active else '' }}" href="{{ item.href }}">{{ item.label }}</a>
      {% endfor %}
    </nav>
    <div class="topnav-actor">Apex Founder · founder@apexsupply.example</div>
  </header>
  <main class="content">
    {% block flash %}
      {% if request.query_params.get("ok") %}
        <div class="flash flash-ok">{{ request.query_params.get("ok") }}</div>
      {% endif %}
      {% if request.query_params.get("err") %}
        <div class="flash flash-bad">{{ request.query_params.get("err") }}</div>
      {% endif %}
    {% endblock %}
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

Note the `{% block topbar %}` is dropped entirely — `grep -rn "block topbar" apps/api/app/web/templates/`
confirms no other template overrides it, and the page's own `<h1>` (rendered by the `page_header` macro
in `_macros.html:3-11`, used on every content page) already shows the page title, so no information is
lost.

- [ ] **Step 2: Run the page-walk smoke test**

Run (from `apps/api`, venv active): `python -m pytest -q tests/test_web_smoke.py`
Expected: all cases pass — this walks every registered page (`> 20` of them) plus all 9 master slugs and
asserts `200` + `text/html`. This is the structural regression gate for a `base.html` change: if a Jinja
syntax error were introduced, every one of these would fail with a 500.

- [ ] **Step 3: Commit**

```bash
cd "apps/api"
git add app/web/templates/base.html
git commit -m "feat: replace sidebar + topbar with a single flat top nav"
```

---

### Task 5: Top nav CSS (replacing the sidebar/shell/topbar rules)

**Files:**
- Modify: `apps/api/app/web/static/app.css` (the `/* --- Sidebar --- */` through `/* --- Shell --- */`
  block, originally lines 46-80; the 640px mobile breakpoint, originally lines 103-106)

**Interfaces:**
- Consumes: `--accent`, `--accent-weak`, `--accent-ink`, `--panel-2`, `--muted`, `--text`, `--bg`,
  `--border`, `--font-display` from Task 1/3.
- Produces: `.topnav`, `.topnav-brand`, `.brand-mark` (kept, same name), `.topnav-links`,
  `.topnav-link`, `.topnav-link.active`, `.topnav-actor`, `.content` (kept, same name/role — no more
  `margin-left` offset since there's no sidebar to clear).

- [ ] **Step 1: Replace the sidebar/shell/topbar CSS block**

Find (the whole block from the `/* --- Sidebar --- */` comment through the end of `.content`'s rule):
```css
/* --- Sidebar --- */
.sidebar {
  position: fixed; top: 0; left: 0; bottom: 0; width: var(--sidebar-w);
  background: var(--panel); border-right: 1px solid var(--border);
  padding: 16px 12px; overflow-y: auto;
}
.brand {
  font-weight: 650; font-size: 15px; padding: 6px 10px 16px;
  display: flex; align-items: center; gap: 8px;
}
.brand-mark { color: var(--accent); }
.nav-section {
  font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--faint); padding: 14px 10px 6px;
}
.nav-item {
  display: block; padding: 7px 10px; border-radius: 8px;
  color: var(--muted); font-weight: 500; margin-bottom: 1px;
}
.nav-item:hover { background: var(--panel-2); color: var(--text); }
.nav-item.active { background: var(--accent-weak); color: var(--accent); font-weight: 600; }

/* --- Shell --- */
.shell { margin-left: var(--sidebar-w); }
.topbar {
  position: sticky; top: 0; z-index: 5;
  display: flex; align-items: center; justify-content: space-between;
  height: 56px; padding: 0 28px;
  background: color-mix(in srgb, var(--bg) 85%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border);
}
.topbar-title { font-weight: 600; }
.topbar-actor { color: var(--muted); font-size: 13px; }
.content { max-width: 1200px; margin: 0 auto; padding: 28px; }
```

Replace with:
```css
/* --- Top nav (replaces the former left sidebar + topbar pair) --- */
.topnav {
  position: sticky; top: 0; z-index: 5;
  display: flex; align-items: center; gap: 28px;
  height: 60px; padding: 0 28px;
  background: color-mix(in srgb, var(--bg) 85%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border);
}
.topnav-brand {
  font-family: var(--font-display); font-weight: 700; font-size: 16px;
  display: flex; align-items: center; gap: 8px; flex: 0 0 auto;
}
.brand-mark { color: var(--accent); }
.topnav-links { display: flex; align-items: center; gap: 4px; flex: 1 1 auto; overflow-x: auto; }
.topnav-link {
  padding: 7px 12px; border-radius: 8px; font-size: 14px; font-weight: 600;
  color: var(--muted); white-space: nowrap;
}
.topnav-link:hover { background: var(--panel-2); color: var(--text); }
.topnav-link.active { background: var(--accent-weak); color: var(--accent-ink); }
.topnav-actor { color: var(--muted); font-size: 13px; flex: 0 0 auto; }
.content { max-width: 1200px; margin: 0 auto; padding: 28px; }
```

- [ ] **Step 2: Fix the 640px mobile breakpoint**

Find (originally lines 103-106):
```css
@media (max-width: 640px) {
  .sidebar { display: none; } .shell { margin-left: 0; }
  .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; }
}
```
Replace with:
```css
@media (max-width: 640px) {
  .topnav-links { display: none; }
  .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; }
}
```
This is a deliberate, documented gap: below 640px the nav links disappear with no replacement (no
hamburger menu) since building mobile nav is out of scope for this pass — the brand and actor stay
visible, and every page remains reachable by URL. Flag this to the user in the final report; it is not a
silent regression, it is a scoped-out gap.

- [ ] **Step 3: Fix the print media query**

Find (originally line 146, inside the `@media print { ... }` block):
```css
  .sidebar, .topbar, .list-toolbar, .form-actions, .btn, .flash { display: none !important; }
```
Replace with:
```css
  .topnav, .list-toolbar, .form-actions, .btn, .flash { display: none !important; }
```

- [ ] **Step 4: Grep for any leftover reference to the removed classes**

Run: `grep -rn "\.sidebar\|\.shell\|\.topbar\|\.nav-section\|\.nav-item" apps/api/app/web/static/app.css apps/api/app/web/templates/`
Expected: no matches. (`.topnav`, `.topnav-*` matches are fine — the grep pattern only targets the old
class names.)

- [ ] **Step 5: Run the page-walk smoke test again**

Run (from `apps/api`, venv active): `python -m pytest -q tests/test_web_smoke.py`
Expected: all cases pass.

- [ ] **Step 6: Commit**

```bash
cd "apps/api"
git add app/web/static/app.css
git commit -m "style: add top nav CSS, drop sidebar/shell/topbar rules, fix print + mobile breakpoints"
```

---

### Task 6: Full verify loop and manual visual check

**Files:** none (verification only)

- [ ] **Step 1: Full automated verify loop**

Run (from `apps/api`, venv active):
```
python -m pytest -q
python -m ruff check app/ tests/
```
Expected: `819 passed` (same count as the Task 1 baseline — this change adds no new tests and removes
none), ruff reports exactly `35` (zero new findings, per `CLAUDE.md`'s bar).

- [ ] **Step 2: Manual visual check with the dev server**

Use the project's `run` skill (or start the server manually per `apps/api`'s existing run instructions) and
open, in a browser:
- `/` (Command Center)
- `/products`
- `/purchase-orders` and one PO detail page

Confirm for each: the top nav renders with all `NAV_ITEMS` as a flat row, the current page's link is
highlighted, no page shows a broken layout or missing chrome, and text is legible (nothing looks smaller
than the old UI — it should look larger, given the 14px→15px base bump).

- [ ] **Step 3: Toggle OS/browser dark mode and repeat the check on the same three pages**

Confirm the warm-paper light palette and the dark-mode palette both render with readable contrast and no
leftover indigo/gray from the old palette (a leftover would mean a rule was missed in Tasks 1-5 — grep for
the old hex values `#4f46e5` and `#7c74ff` across `app.css` to confirm zero matches).

- [ ] **Step 4: Print preview check**

In the browser's print preview for a page with a table (e.g. a warehouse count sheet or PO detail), confirm
the top nav is hidden and the table still renders with visible borders — this exercises the print media
query fixed in Task 5, Step 3.

- [ ] **Step 5: Final commit (if Step 2-4 surfaced no changes) or fix-and-recommit (if they did)**

If everything in Steps 2-4 looked right, there's nothing left to commit — Task 5's commit is the final
state. If any visual issue was found, fix it in `app.css`/`base.html`, re-run Step 1's verify loop, and
commit with a message describing the specific fix (e.g. `git commit -m "fix: <specific issue found in
manual check>"`).

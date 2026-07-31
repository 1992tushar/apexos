# ApexOS UI redesign — design spec

**Status:** approved — foundation-only scope
**Scope:** visual identity + top-nav layout for this pass (see "Rollout scope" below). No data model,
route, or business-logic changes. The board-grid span system described below is documented for context
but its template-by-template rollout is explicitly deferred, not part of this pass.
**Reference mockup:** the "★ Final" tabs in the shared Artifact (Command Center, Products list, PO detail) — this doc formalizes what's in those three screens into tokens and rules other pages will reuse.

## Why

The current server-rendered UI (`app.css`, `base.html`, Jinja templates under `app/web/templates/`) was
built minimal-first: a fixed left sidebar, a topbar, and everything else stacked as full-width cards in a
uniform grid. Feedback: it reads as small, dull, and "generic SaaS dashboard" — not the layout paradigm,
not just the palette. Three rounds of mockups narrowed this down to two decisions:

1. **Layout**: replace the sidebar + uniform-grid-of-cards structure with a **flexible workspace board** —
   a top nav (no permanent sidebar) and a grid of blocks that can span different widths/heights instead of
   all being identical full-width or third-width tiles.
2. **Visual treatment**: "Quiet Confidence" — warm paper tones, a serif display face for headings and
   numerals, terracotta accent, generous spacing. Calmer and more considered than the current flat
   gray-and-indigo minimalism, without becoming loud.

## Color

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#faf8f4` | `#1b1815` | page background |
| `--panel` | `#ffffff` | `#242019` | blocks, cards |
| `--panel-2` | `#f4f0e8` | `#2b261e` | subtle fill (table head, hover) |
| `--border` | `#e8e2d6` | `#3a342a` | hairlines |
| `--border-strong` | `#d8d0bf` | `#4a4335` | inputs, emphasis borders |
| `--text` | `#22201b` | `#f1ece2` | body text |
| `--muted` | `#736b5c` | `#b3a892` | secondary text |
| `--faint` | `#a39a87` | `#8a7d64` | hints, captions |
| `--accent` | `#a8582f` | `#e08a5b` | primary actions, links (terracotta) |
| `--accent-weak` | `#f7ece3` | `#3a2a1c` | accent fill (chips, hover backgrounds) |
| `--accent-ink` | `#7a3f1f` | `#f3b58c` | accent text on light fill |
| `--ok-bg` / `--ok-fg` | `#eaf3e9` / `#3a6b3d` | `#1c2b1d` / `#8fce93` | positive badges/deltas |
| `--warn-bg` / `--warn-fg` | `#fbf0dc` / `#8a5a12` | `#332812` / `#e8b862` | attention badges |
| `--bad-bg` / `--bad-fg` | `#faeae6` / `#a13f26` | `#331f19` / `#e88a6b` | overdue/negative |

Semantic (ok/warn/bad) stays separate from the accent — the accent marks interactivity and brand, not status.
Dark mode is a full token redefinition, not an inversion — same warmth, adjusted for a dark ground.

## Type

- **Display** (headings, stat/block values, page titles): `"Iowan Old Style", Georgia, serif` — the one
  place personality shows. Used at restraint: h1, `.block-value`, nothing smaller than ~18px.
- **Body / UI** (nav, labels, table cells, buttons, forms): `"Segoe UI", -apple-system, sans-serif` — same
  system-font pragmatism as today, for legibility at small sizes and native OS rendering.
- **Base body size moves from 14px to 14.5–15px.** Secondary text (labels, hints, table headers) moves from
  today's 11–12px floor up to a 12–13px floor. This directly answers the original "everything is too small"
  complaint — nothing in the new system should render text below 11px.
- Numerals use `font-variant-numeric: tabular-nums` wherever they line up in columns (tables, stat blocks).

## Layout: the board

Replaces the sidebar + `.content` + `.grid.grid-N` pattern.

- **Top nav, no sidebar.** A single horizontal bar (~56–64px) holding brand, primary nav links, and the
  actor name. Frees the left edge on every page — the single biggest source of "generic dashboard" feeling
  in the sidebar options.
- **Board grid**: `display:grid; grid-template-columns:repeat(4,1fr); gap:16px` at desktop width, inside a
  centered `max-width:1240px` wrapper. Blocks (`.block`, replacing `.card`) get one of four span modifiers:
  - default: 1 column
  - `.block-wide` / `.block-half`: 2 columns (naming follows context — "wide" for a hero metric with a
    chart, "half" for two side-by-side detail panels)
  - `.block-tall`: spans 2 rows (used for list-shaped content like an alerts panel sitting next to shorter
    stat blocks)
  - `.block-full`: all 4 columns (tables, action lists, anything that wants full width)
- **Responsive collapse**: below 900px, the grid drops to 2 columns and every `wide`/`half`/`full` block
  becomes full-width within that; below 640px, 1 column, matching the existing breakpoint philosophy in
  `app.css`.
- This is not a free-form/draggable canvas — spans are still fixed per block in the template, chosen at
  design time per page. "Flexible" describes the visual variety (not every block is the same size), not
  runtime rearrangement.

## Component mapping (old → new)

| Old | New | Notes |
|---|---|---|
| `.sidebar`, `.nav-item` | removed → `.topnav`, `.topnav-link` | horizontal, same `NAV_ITEMS`/`SECTION_LABELS` data from `base.html`, rendered as a flat link row instead of grouped sections. Section grouping (`nav-section`) is dropped since there's no vertical space to hang labels off of — a state worth confirming since it does lose one piece of the current information architecture. |
| `.card`, `.card-title` | `.block`, `.block-label` | same purpose, new tokens, `.block-label` is a caption (uppercase, small) rather than a heading — headings now live in the serif display face at the top of significant blocks only (e.g. `.block-value`) |
| `.grid.grid-2/3/4` | board grid + span modifiers | fixed 2/3/4-column grids are replaced by the 4-column board; a page that had `grid-3` picks 3 default (1-col) blocks, a page that had `grid-2` picks 2 `.block-wide` or similar depending on content weight |
| `.stat-tile`, `.stat-value` | folded into `.block` + `.block-value` | stat tiles are no longer a visually distinct component — they're just a block whose content is a number |
| `.detail-grid` (2fr/1fr) | `.block-half` pairs in the board | e.g. PO detail's "goods receipts" / "bill" panels become two `.block-half`s instead of a fixed 2:1 grid |
| `.table-wrap`, `table`, `thead/tbody` | unchanged structurally | same table markup, restyled tokens/spacing (12→13.5px body, tabular nums) |
| `.badge`, `.tag`, `.chip` | unchanged structurally | restyled tokens only |
| `.list-toolbar`, `.pagination`, `.form-grid`, `.field`, inputs | unchanged structurally | restyled tokens/spacing only; these are content-level components independent of the board/sidebar decision |
| `.explain-*`, `.rev`, `.calendar-*`, `.compare` (domain-specific blocks from Parts 3–10) | unchanged structurally | restyled tokens only; these are already narrow, well-scoped components per `app.css`'s existing comments and don't need new abstractions |
| `@media print` rules | selectors updated | `.sidebar` reference removed/replaced with `.topnav`; the print bar hides `.topnav` instead |

**No new abstraction beyond the board grid + block spans.** Every other existing class keeps its name and
structural role — only tokens (color, type, spacing) and the four span modifiers are new. This matches the
project's standing rule against unearned abstractions.

## Rollout scope — DECIDED: foundation only

This pass covers **foundation only**: rewrite `app.css` tokens/type/board system, update `base.html` (top
nav, drop sidebar), fix the print block's selectors. No individual template gets rewritten to use the
`.block-wide`/`.block-tall`/`.block-full` span modifiers in this pass — every existing template keeps its
current markup (`.card`, `.grid.grid-2/3/4`, `.detail-grid`, etc.) and simply inherits the new tokens,
type, and top nav automatically, since those classes keep their structural role (see the mapping table
above). That alone resolves the "small and dull, generic dashboard" complaint everywhere, with zero
template files touched and zero risk of breaking a page's markup.

The curated board-grid layout (screens choosing which content is wide/tall/full, as shown in the ★ Final
mockups) is **out of scope for this pass** and would be a separate, later effort per screen.

**Nav grouping — decided:** the sidebar's section labels (Overview / Operate / System) are dropped. The
top nav is a flat row of links, matching the mockup.

## Out of scope

- No new JS framework, no client-side interactivity beyond what exists (this stays server-rendered Jinja).
- No change to any route, service, or data shape — this is CSS/template presentation only.
- No new component abstractions beyond the board grid + 4 span modifiers.
- Per `CLAUDE.md`: this is not one of the named roadmap parts. It should land as its own explicit, scoped
  effort — not folded into whatever `PROGRESS.md` part is in flight — and should not block or get blocked
  by roadmap work.

## Open questions

None outstanding — rollout scope and nav grouping are decided above. The board-grid span system and its
per-screen rollout to the remaining ~40 templates is deferred to a future spec, not this one.

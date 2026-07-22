# ApexOS — Design System

> **Status:** Approved · **Owner:** UX / Design · **Version:** 1.0 · **Date:** 2026-07-19
>
> Conforms to `00-canonical-foundation.md` (§8 Design Principles) and `05-navigation.md`.
> Where this document and the foundation disagree, the foundation wins. This is the single source
> of truth for **how ApexOS looks and feels**: tokens, components, and interaction specs.
> Design north star (Foundation §1): **Linear / Stripe / Notion / Vercel** — minimal, fast,
> keyboard-first, large whitespace, subtle motion, blue primary, dark-mode first.

Every screen must still answer the three questions (Foundation §8): **What happened? · What needs
attention? · What should I do?**

---

## 1. Foundations

- **Base:** Tailwind + **shadcn/ui** (Radix primitives). shadcn primitives live unmodified in
  `components/ui`; ApexOS styling is applied through the tokens below, never by forking primitives.
- **Tokens are CSS variables** on `:root` (light) and `.dark` (dark), consumed by Tailwind via
  `hsl(var(--token))`. Components reference **semantic** tokens (`--primary`, `--destructive`),
  never raw hex. Dark mode is the default; both themes are first-class.
- **Icons:** Lucide, `16px`/`20px`, `1.5px` stroke, `currentColor`.
- **Grid:** 8px base spacing; content max-width 1200px for reading views, full-bleed for tables
  (per `05-navigation.md` §1).

---

## 2. Color Tokens

HSL channel triplets so Tailwind can apply opacity (`hsl(var(--primary) / 0.1)`). Blue primary;
green/amber/red/grey status (Foundation §8).

### 2.1 Semantic tokens — light & dark

| Token | Light `H S% L%` | Dark `H S% L%` | Use |
|-------|-----------------|----------------|-----|
| `--background` | `0 0% 100%` | `222 47% 6%` | App canvas |
| `--foreground` | `222 47% 11%` | `210 20% 96%` | Primary text |
| `--card` | `0 0% 100%` | `222 40% 9%` | Card / surface |
| `--card-foreground` | `222 47% 11%` | `210 20% 96%` | Text on card |
| `--popover` | `0 0% 100%` | `222 44% 8%` | Popover / dropdown / command palette |
| `--muted` | `210 40% 96%` | `222 30% 14%` | Subtle fill (table header, chips) |
| `--muted-foreground` | `215 16% 47%` | `215 18% 62%` | Secondary text, captions |
| `--accent` | `210 40% 94%` | `222 30% 16%` | Hover fill, active nav bg |
| `--accent-foreground` | `222 47% 11%` | `210 20% 96%` | Text on accent |
| `--border` | `214 20% 90%` | `222 24% 18%` | Borders, dividers |
| `--input` | `214 20% 88%` | `222 24% 20%` | Input border |
| `--ring` | `221 83% 53%` | `217 91% 60%` | Focus ring (blue) |
| `--primary` | `221 83% 53%` | `217 91% 60%` | Brand blue — primary actions, active nav |
| `--primary-foreground` | `210 40% 98%` | `222 47% 8%` | Text on primary |
| `--secondary` | `210 40% 96%` | `222 30% 15%` | Secondary button fill |
| `--secondary-foreground` | `222 47% 11%` | `210 20% 96%` | Text on secondary |
| `--destructive` | `0 72% 51%` | `0 72% 58%` | Destructive action / error |
| `--destructive-foreground` | `0 0% 100%` | `0 0% 100%` | Text on destructive |

### 2.2 Status palette (green/amber/red/grey + blue)

Each status has a `-fg` (text/icon), `-bg` (subtle badge fill), and `-solid` (dot/bar). Tuned for
AA contrast on `--card` in both themes.

| Status | Meaning (domain) | Light fg / bg / solid | Dark fg / bg / solid |
|--------|------------------|-----------------------|----------------------|
| **Success** (green) | Paid, fulfilled, active, in-stock | `142 71% 29%` / `142 60% 94%` / `142 71% 40%` | `142 62% 55%` / `142 40% 14%` / `142 62% 45%` |
| **Warning** (amber) | Pending, low-stock, credit near limit, due soon | `35 92% 33%` / `40 90% 92%` / `35 92% 48%` | `38 92% 58%` / `35 45% 15%` / `38 92% 50%` |
| **Danger** (red) | Overdue, credit hold, out-of-stock, failed | `0 72% 45%` / `0 80% 95%` / `0 72% 51%` | `0 78% 63%` / `0 45% 16%` / `0 78% 55%` |
| **Neutral** (grey) | Draft, closed, archived, inactive | `215 16% 40%` / `210 30% 94%` / `215 12% 55%` | `215 16% 62%` / `220 18% 16%` / `215 12% 55%` |
| **Info** (blue) | New, processing, informational | `221 83% 45%` / `214 95% 94%` / `221 83% 53%` | `217 91% 66%` / `217 50% 16%` / `217 91% 60%` |

Domain status → color mapping (canonical; use everywhere a status is shown):

| Entity | green | amber | red | grey | blue |
|--------|-------|-------|-----|------|------|
| Sales Order | Fulfilled | Fulfilling / Pending | Cancelled | Draft | New / Confirmed |
| Invoice | Paid | Due soon | Overdue | Void | Issued |
| Inventory | In stock | Low stock | Out of stock | — | — |
| Credit Policy | Within limit | Near limit | On hold | Inactive | — |

### 2.3 Data-viz palette (Recharts)

Categorical series, colorblind-aware, in order: `221 83% 53%` (blue), `142 71% 40%` (green),
`35 92% 48%` (amber), `262 70% 58%` (violet), `190 80% 42%` (teal), `340 75% 55%` (pink). See the
`dataviz` skill before building charts; do not color-code by the status palette in charts.

---

## 3. Typography

- **Font:** **Inter** (UI), `-apple-system` fallback; **`ui-monospace`** (JetBrains Mono) for codes
  (SKU, `SO-202607-00042`), money, and IDs. `font-feature-settings: "cv11","ss01"; "tnum"` — enable
  **tabular figures** wherever numbers align in tables.
- **Scale** (Major-third-ish, `rem`):

| Token | Size / line-height | Weight | Use |
|-------|--------------------|--------|-----|
| `text-display` | 30 / 36 | 600 | Dashboard hero number |
| `text-h1` | 24 / 32 | 600 | PageHeader title |
| `text-h2` | 20 / 28 | 600 | Section heading |
| `text-h3` | 16 / 24 | 600 | Card title, table caption |
| `text-body` | 14 / 20 | 400 | Default body / table cell |
| `text-sm` | 13 / 18 | 400 | Secondary, help text |
| `text-caption` | 12 / 16 | 500 | Labels, badges, meta |
| `text-overline` | 11 / 16 | 600 | Section labels (uppercase, `+0.04em`, `--muted-foreground`) — matches sidebar "WORK/SYSTEM" |

Body default is **14px** (Linear/Stripe density). Weights used: 400 / 500 / 600 only. Never center
long text; numbers right-align in tables.

---

## 4. Spacing, Radius, Shadow, Motion Tokens

### 4.1 Spacing (8px base)

`space-1` 4 · `space-2` 8 · `space-3` 12 · `space-4` 16 · `space-5` 20 · `space-6` 24 ·
`space-8` 32 · `space-10` 40 · `space-12` 48 · `space-16` 64. Card padding `space-6` (24);
compact table cell `space-2`/`space-3`; page gutter `space-6`→`space-8`.

### 4.2 Radius

`--radius: 0.5rem` (8px, base). `radius-sm` 6 (inputs, badges) · `radius-md` 8 (buttons, cards) ·
`radius-lg` 12 (dialogs, sheets, stat tiles) · `radius-full` 9999 (pills, avatars, status dots).

### 4.3 Shadow (soft, low; heavier in dark)

| Token | Light | Use |
|-------|-------|-----|
| `shadow-xs` | `0 1px 2px 0 hsl(222 47% 11% / 0.05)` | Resting card, input |
| `shadow-sm` | `0 1px 3px hsl(222 47% 11% / 0.08), 0 1px 2px -1px hsl(222 47% 11% / 0.08)` | Hovered card, dropdown |
| `shadow-md` | `0 4px 12px hsl(222 47% 11% / 0.10)` | Popover, menu |
| `shadow-lg` | `0 12px 32px hsl(222 47% 11% / 0.16)` | Dialog, Sheet |

In dark mode shadows deepen (`… / 0.4–0.6`) and pair with a 1px `--border` for edge definition.
Elevation is expressed with **border + subtle shadow**, not heavy drop shadows.

### 4.4 Motion

`duration-fast` 120ms · `duration-base` 180ms · `duration-slow` 240ms.
Easing: `ease-out` (`cubic-bezier(0.16,1,0.3,1)`) for enter; `ease-in-out` for move. See §11.

---

## 5. Core Component Inventory (on shadcn/ui)

All built on shadcn/ui primitives; specs below are the ApexOS contract.

| Component | Built on | Key spec |
|-----------|----------|----------|
| **Button** | `button` | Variants: `primary` (blue solid), `secondary` (muted), `outline`, `ghost`, `destructive`, `link`. Sizes `sm`/`md`/`icon`. Radius-md, height 32/36. Loading = spinner + disabled, label retained. One primary per view. |
| **Card** | `card` | `--card` bg, 1px `--border`, `radius-lg`, `shadow-xs`, padding `space-6`. Header (title `text-h3` + optional action) / content / footer slots. |
| **Table** | `table` + TanStack | See §6. Full-bleed, sticky header, zebra off (border rows), row hover `--accent`. |
| **Badge / Status** | `badge` | Uses §2.2 status tokens: `-bg` fill + `-fg` text, optional leading `-solid` dot (`radius-full` 6px). `text-caption`, `radius-full`, `px-2 py-0.5`. |
| **Input** | `input` | Height 36, 1px `--input`, `radius-sm`, focus = 2px `--ring`. Numeric inputs tabular, right-aligned. Money inputs show `₹` prefix, store minor units. |
| **Select** | `select` | Radix; searchable variant (Command) when >8 options. Master-data selects (customer type, UOM, category) pull from `*_type` tables (D2). |
| **Dialog** | `dialog` | Centered modal for focused confirm/short forms. `radius-lg`, `shadow-lg`, backdrop `--background / 0.6` + blur. Max-width 480–640. `Esc`/`⌘Enter` wired. |
| **Sheet** | `sheet` | Right-side panel for **quick-create** (`05-navigation.md` §4.2) and detail peeks. Width 420–520; slides in `duration-base`. |
| **Toast** | `sonner` | Bottom-right; success/info/warning/error variants map to §2.2. Auto-dismiss 4s (errors sticky w/ action). Live domain events (D10) surface here; message from the error envelope (`12-coding-standards.md` §4). |
| **EmptyState** | composite (`components/shared`) | Icon (Lucide, muted) + `text-h3` title + one-line `--muted-foreground` help + primary CTA. Used for zero-data lists and cleared filters. |
| **StatTile** | composite | Dashboard KPI tile — see §9. |
| **PageHeader** | composite | Breadcrumb (`05-navigation.md` §4) + title (`text-h1`) + status badge + primary/secondary actions + optional meta line. Sticky under topbar. |

Composite components live in `components/shared`; feature UI in `features/*/components`
(`10-folder-structure.md` §3).

---

## 6. TanStack Table Spec

Tables are a signature surface (Foundation §8: "beautiful tables"). One `DataTable` wrapper over
TanStack Table + shadcn `table`.

- **Density:** two modes — `comfortable` (row 44px, cell `py-3`) default, `compact` (row 36px,
  `py-2`) toggle, persisted per user per table. `text-body` (14px), tabular numerals.
- **Sticky header:** header row sticky (`--muted` bg, `text-caption` uppercase `--muted-foreground`,
  1px bottom `--border`). Horizontal scroll keeps the first (identity) column pinned optionally.
- **Rows:** border-separated (no zebra), hover `--accent`, keyboard row focus ring; `Enter` opens
  the record, `↑/↓` move selection (`05-navigation.md` §5.4). Money right-aligned, monospace codes.
- **Row actions:** trailing `⋯` menu (`dropdown-menu`) with entity verbs (Fulfill, Invoice, Cancel);
  primary inline action may show on hover. Never more than one destructive item, always confirmed.
- **Bulk select:** leading checkbox column; header checkbox = select-page. A selection appears as a
  **floating action bar** (count + bulk verbs + clear), not per-row. `x` toggles a row (§5.4).
- **Column features:** sortable headers (click / `Sort` menu), show/hide columns, resize; server-side
  sort/filter/pagination via query params. Sticky footer row for column totals (sum of `_minor`).
- **States:** loading = skeleton rows (not spinner); empty = **EmptyState**; filtered-empty =
  "No results — clear filters". Error = inline retry row using the error envelope.
- **Responsive:** below 768px rows collapse to stacked **Card** rows (`05-navigation.md` §6).

---

## 7. Form Spec (RHF + Zod)

- **React Hook Form** + **Zod resolver**; the Zod schema mirrors the backend Pydantic contract
  (`12-coding-standards.md` §5, §11). shadcn `form` (`FormField`/`FormItem`/`FormLabel`/`FormMessage`).
- **Layout:** single column, label above field, `space-4` between fields, `space-6` between groups.
  Related fields group in a `Card` or `fieldset`. Long forms → sections with `text-overline` labels.
- **Labels & help:** every field labeled (`text-caption`, `--foreground`); optional help `text-sm`
  `--muted-foreground` below; required marked, not optional. Placeholders are examples, never labels.
- **Validation:** validate on blur, then on change once touched; submit re-validates all. Field errors
  from `FormMessage` (`--destructive`, `text-sm`); server/business errors (typed `AppError`, §4) map to
  the field via `details[].field`, or to a form-level alert + **Toast**.
- **Money fields:** `₹` prefix, tabular, store/emit **minor units** (`unitPriceMinor`), never floats.
- **Submit:** primary Button, `disabled` while `isPending` with spinner; `⌘Enter` submits, `Esc`
  cancels (`05-navigation.md` §5.4). Optimistic UI only where safely reversible.
- **Quick-create** forms render in a **Sheet**; complex records (Sales Order, PO) use the full `/new`
  page (`05-navigation.md` §4.2).

---

## 8. Accessibility

- **Contrast:** body text ≥ AA (4.5:1); large text/UI ≥ 3:1. Status is never color-only — pair with
  an icon, dot, or label. Token pairs in §2 are tuned to meet this in both themes.
- **Keyboard:** everything operable without a mouse (north-star mandate). Visible focus ring
  (`--ring`, 2px) on all interactives; logical tab order; no focus traps except modal Dialog/Sheet
  (focus returns to trigger on close). Chords per `05-navigation.md` §5, disabled while typing.
- **Semantics:** Radix gives roles/ARIA; preserve them. Real `<button>`/`<a>`, labeled inputs
  (`htmlFor`), `aria-live="polite"` for Toasts and async status, `aria-busy` on loading regions.
- **Motion:** honor `prefers-reduced-motion` — disable non-essential transitions (§11).
- **Targets:** ≥ 32px hit area (≥ 40px on mobile). Icon-only buttons carry `aria-label`.

---

## 9. Dashboard Tile Spec (StatTile)

The dashboard answers "What happened? / needs attention? / to do?" (Foundation §8) through a grid of
tiles.

- **StatTile:** `Card` (`radius-lg`, `space-6`) containing: `text-overline` label (e.g. "Receivables
  Overdue") · `text-display` value (tabular, money via `lib/format` minor→`₹`) · a **delta** chip
  (`▲/▼` + % vs. prior period, green up / red down — inverted for cost/overdue metrics) · optional
  sparkline (Recharts, single §2.3 series) · optional footnote `text-sm --muted-foreground`.
- **Attention coloring:** a tile crossing a threshold (overdue > 0, stock-out present) adopts the
  matching status `-solid` accent (left 2px bar or icon), never a full-color fill.
- **Grid:** responsive 12-col; tiles span 3 (KPI) / 6 (chart) / 12 (feed). `space-4` gap.
  Loading = skeleton tile; empty = "No data yet" muted.
- **Companion panels:** "What happened" = activity feed from `activity_log` (D10); "What to do" =
  open `task` list (`05-navigation.md` §7). Every tile/row is a deep-link to its filtered module view,
  scoped by the active **BU** (D1).

---

## 10. Theme Implementation Notes

- Tokens declared once in `styles/` on `:root` and `.dark`; Tailwind `theme.extend.colors` maps each
  to `hsl(var(--token) / <alpha-value>)`. Theme toggle (`⌘\`, `05-navigation.md` §5.1) sets `.dark`
  on `<html>`; default follows system, choice persisted per user (D8 profile).
- Never hardcode a hex in a component — reference a semantic token. New surfaces earn a token here
  first. Charts read tokens via CSS variables so they retheme automatically.

---

## 11. Motion Guidelines (subtle only)

Motion clarifies state change; it never decorates (Foundation §8: "subtle animation only").

| Interaction | Motion |
|-------------|--------|
| Hover / focus (button, row, nav) | color/opacity `duration-fast` (120ms), no movement |
| Dropdown / Popover / Select | fade + 4px rise, `duration-fast`, `ease-out` |
| Dialog | fade backdrop + scale `0.98→1`, `duration-base` (180ms) |
| Sheet | slide from edge, `duration-base`, `ease-out` |
| Toast | slide-in + fade, `duration-base`; fade-out on dismiss |
| Skeleton | slow shimmer, 1.5s loop |
| Page/tab change | content fade `duration-fast`; no large layout animation |

Rules: no bounce, no spin (except a loading spinner), no parallax, nothing over `duration-slow`
(240ms). Animate `transform`/`opacity` only. All of the above are **disabled** under
`prefers-reduced-motion: reduce` (§8).

---

## 12. Design Acceptance Checklist

- [ ] Colors reference semantic/status tokens (§2) — no hardcoded hex; works in light **and** dark.
- [ ] Status shown with color **and** icon/label; domain→color mapping matches §2.2.
- [ ] Type uses the scale (§3); numbers/money tabular, right-aligned, minor→`₹` via `lib/format`.
- [ ] Spacing/radius/shadow from tokens (§4); 8px grid respected.
- [ ] Components are the §5 inventory on unmodified shadcn primitives; composites in the right folder.
- [ ] Tables follow §6 (sticky header, density toggle, row actions, bulk bar, all states).
- [ ] Forms follow §7 (RHF+Zod, labels, money minor units, `⌘Enter`/`Esc`, server-error mapping).
- [ ] Loading / empty / error states designed, not afterthoughts.
- [ ] Accessible: AA contrast, keyboard-operable, visible focus, `prefers-reduced-motion` honored (§8).
- [ ] Motion is subtle, token-timed, transform/opacity only (§11).
- [ ] Dashboard tiles deep-link and respect BU scope (§9, D1).
```

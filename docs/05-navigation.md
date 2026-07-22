# ApexOS — Navigation System

> **Status:** Draft for build · **Owner:** UX / IA · **Version:** 1.0 · **Date:** 2026-07-19
> **Conforms to:** `00-canonical-foundation.md` and `02-information-architecture.md`.
> Sidebar order is the Module Map (Foundation §7), verbatim. Keyboard-first per the north star.

---

## 1. App Shell

Three-region shell: fixed left **Sidebar**, top **Topbar** (BU switcher, global search, quick-create,
notifications, tasks, profile), and the **Content** area (PageHeader + body). Desktop ≥ 1024px.

```
┌──────────────┬──────────────────────────────────────────────────────────────┐
│  APEXOS   ⌄  │  ⌕ Search or run a command…  ⌘K     [BU: All Units ▾] + ◔ ☰ ⦿ │  ← Topbar
├──────────────┼──────────────────────────────────────────────────────────────┤
│ ⌂ Dashboard  │  ← Sales Orders / SO-202607-00512     [Fulfilling ●]     ⋯    │  ← PageHeader
│              │  Blue Café · ₹42,180 · Margin 29%        [Fulfill] [Invoice]   │
│ ─ WORK ───── │ ────────────────────────────────────────────────────────────  │
│ ◇ Sales      │                                                                │
│ ◍ Customers  │                                                                │
│ ▤ Products   │                   CONTENT AREA                                 │
│ ▦ Inventory  │              (list / detail / form)                            │
│ ⇄ Procurement│                                                                │
│ ₹ Finance    │                                                                │
│ ▧ Reports    │                                                                │
│ ─ SYSTEM ─── │                                                                │
│ ✓ Tasks   3  │                                                                │
│ ⎘ Documents  │                                                                │
│ ⚙ Settings   │                                                                │
│              │                                                                │
│ ⦿ Tushar T.  │                                                                │
└──────────────┴──────────────────────────────────────────────────────────────┘
   240px                                    fluid
```

- Sidebar width **240px** expanded, **56px** collapsed (icons only).
- Topbar height **56px**, sticky. Content max-width for reading views **1200px**; tables go full-bleed.

---

## 2. Sidebar

### 2.1 Order & grouping (Foundation §7, exact order)

The nine module-map rows become sidebar items, split into two sections. The final map row
("Tasks / Documents / Settings") expands into its three real destinations.

| Order | Item | Route | Section | Icon (Lucide) |
|---|---|---|---|---|
| 1 | Dashboard | `/` | — (top, ungrouped) | `layout-dashboard` |
| 2 | Sales | `/sales-orders` | **Work** | `shopping-cart` |
| 3 | Customers | `/customers` | Work | `users` |
| 4 | Products | `/products` | Work | `package` |
| 5 | Inventory / Warehouse | `/inventory` | Work | `warehouse` |
| 6 | Procurement | `/purchase-orders` | Work | `truck` |
| 7 | Finance | `/invoices` | Work | `indian-rupee` |
| 8 | Reports / Analytics | `/reports` | Work | `bar-chart-3` |
| 9 | Tasks | `/tasks` | **System** | `check-square` |
| 10 | Documents | `/documents` | System | `folder` |
| 11 | Settings | `/settings` | System | `settings` |

- **Dashboard** sits alone at the top (it is the home / command center).
- **Work** = day-to-day operational modules (items 2–8).
- **System** = platform/admin (items 9–11).
- Section labels ("WORK", "SYSTEM") are muted 11px uppercase; hidden when collapsed.

### 2.2 Sub-navigation

Modules with multiple views expose sub-items on hover-expand or on the module's own landing
page (secondary tab strip), keeping the sidebar shallow. Examples:

| Module | Sub-views (secondary nav) |
|---|---|
| Sales | Sales Orders · Pipeline |
| Customers | Customers · Leads · Competitors |
| Inventory | Balances · Movements |
| Procurement | Purchase Orders · Goods Receipts · Suppliers · Vendor Evaluations |
| Finance | Invoices · Bills · Payments · Receivables · Payables |
| Settings | Organization · Partners · Finance · Team & Access · Sales · Governance · Preferences |

Rule: **max one level in the sidebar**; anything deeper is a tab strip inside the module
(secondary nav), never a third sidebar tier.

### 2.3 States

| State | Behavior |
|---|---|
| **Active** | Blue left indicator bar (2px) + `--primary` text + subtle `--accent` background. |
| **Hover** | `--accent` background, no indicator. |
| **Collapsed** (56px) | Icons only; label + sub-nav appear in a hover flyout. Toggle with `[` or the chevron by the logo. Persisted per user. |
| **Badge** | Count pill on Tasks (open tasks) and any module with an attention count. |
| **Focus** | Visible focus ring (keyboard nav with ↑/↓, Enter to open). |

---

## 3. Topbar

Left → right: BU switcher · global search · quick-create · notifications · tasks · profile.

```
[ ApexOS ⌄ ]   ⌕ Search or run a command…  ⌘K        [ BU: All Units ▾ ]  ( + )  ( ◔ )  ( ⦿ )
                                                          BU scope       quick   notif   profile
                                                                        create
```

- **BU switcher** — sets global Business Unit scope (D1). Options: each `business_unit` + "All
  Units". Persisted; reflected as `?bu=` on shareable links. `⌘B` opens it.
- **Global search / ⌘K** — opens the command palette (see §5). The topbar field is a visual
  affordance; focus always routes to the palette.
- **Quick-create `+`** — opens the create menu (see §4.2).
- **Notifications `◔`** — dropdown of `notification`; unread dot. Entry point in §7.
- **Tasks** — reachable via sidebar item (with badge) and `g t`; my open `task` count.
- **Profile `⦿`** — user menu: profile, theme (light/dark/system), sign out (Clerk, D8).

---

## 4. Breadcrumbs & Page Context

### 4.1 Breadcrumb rules

Breadcrumbs live in the **PageHeader**, not the topbar, and follow the route hierarchy.

| Rule | Example |
|---|---|
| Root module link is always first; back-arrow chevron precedes it. | `← Sales Orders` |
| Detail = module → record code (human code, not UUID). | `Sales Orders / SO-202607-00512` |
| Create/Edit appends a leaf. | `Sales Orders / SO-202607-00512 / Edit` |
| Settings sections nest one level. | `Settings / Organization / Categories` |
| Max depth **3**. Deeper context uses in-page tabs, not more crumbs. | — |
| Each crumb is a link except the current (last) node. | — |
| BU scope is **not** a breadcrumb (it is global state, shown in topbar). | — |

### 4.2 Quick-create menu (`+` / `c`)

```
┌── Create ( c ) ───────────────┐
│  Sales Order        c then s  │
│  Customer           c then u  │
│  Product            c then p  │
│  Purchase Order     c then o  │
│  Payment            c then y  │
│  Task               c then t  │
│  ── Upload ──                 │
│  Document                     │
└───────────────────────────────┘
```

Quick-create opens the entity's **Sheet** form (fast path) rather than navigating away, so the
user keeps context. Complex records (Sales Order, Purchase Order) open their full `/new` page.

---

## 5. Keyboard Shortcuts

Keyboard-first is a north-star mandate. Two systems: the **⌘K palette** and **direct chords**
(Linear-style `g`-then-key jumps and `c`-then-key creates).

### 5.1 Global

| Keys | Action |
|---|---|
| `⌘K` / `Ctrl K` | Open command palette (navigate / find / act) |
| `⌘B` / `Ctrl B` | Open Business Unit switcher |
| `[` | Toggle sidebar collapsed/expanded |
| `?` | Open keyboard-shortcuts cheat sheet |
| `Esc` | Close dialog / sheet / palette; clear focus |
| `⌘\` | Toggle theme (light/dark) |

### 5.2 Go-to (press `g`, then key) — jump navigation

| Chord | Destination | Route |
|---|---|---|
| `g d` | Dashboard | `/` |
| `g s` | Sales orders | `/sales-orders` |
| `g p` | Products | `/products` |
| `g u` | Customers | `/customers` |
| `g i` | Inventory | `/inventory` |
| `g o` | Purchase orders | `/purchase-orders` |
| `g f` | Finance (invoices) | `/invoices` |
| `g r` | Reports | `/reports` |
| `g t` | Tasks | `/tasks` |
| `g m` | Documents | `/documents` |
| `g ,` | Settings | `/settings` |

### 5.3 Quick-create (press `c`, then key)

| Chord | Creates |
|---|---|
| `c s` | Sales Order |
| `c u` | Customer |
| `c p` | Product |
| `c o` | Purchase Order |
| `c y` | Payment |
| `c t` | Task |

### 5.4 Context (within a list or detail)

| Keys | Action |
|---|---|
| `↑ / ↓` | Move row selection |
| `Enter` | Open selected row |
| `x` | Toggle row select (bulk) |
| `e` | Edit current record |
| `/` | Focus list filter/search |
| `⌘ Enter` | Submit form / confirm dialog |

> Chords are disabled while typing in an input; `Esc` first, then the chord. Cheat sheet (`?`)
> lists everything and is generated from this table.

---

## 6. Mobile / Responsive Navigation

| Breakpoint | Shell behavior |
|---|---|
| **≥ 1024px** (desktop) | Full shell: sidebar (expandable/collapsible) + topbar. |
| **768–1023px** (tablet) | Sidebar auto-collapses to 56px icon rail; flyout labels on tap. |
| **< 768px** (mobile) | Sidebar becomes an off-canvas **Sheet** (hamburger `☰` in topbar). Bottom tab bar for the 4 highest-traffic modules. |

Mobile bottom tab bar (thumb-reach primary nav):

```
┌──────────────────────────────────────────────┐
│                CONTENT                         │
│                                                │
├────────┬────────┬────────┬────────┬───────────┤
│  ⌂     │  ◇     │  ▤     │  ✓     │   ⌕        │
│  Home  │ Sales  │Products│ Tasks  │  Search    │
└────────┴────────┴────────┴────────┴───────────┘
```

- `⌕` on mobile opens the same ⌘K palette (full-screen sheet) — search stays the primary nav.
- Quick-create `+` becomes a floating action button on list screens.
- Everything else lives behind the hamburger Sheet; tables switch to stacked **Card** rows.

---

## 7. Notifications & Tasks Entry Points

Two related but distinct surfaces:

| Surface | Source | Entry points | Purpose |
|---|---|---|---|
| **Notifications** | `notification` | Topbar bell `◔` (unread dot), `g` then bell, in-app **Toast** for live events | Passive awareness — "what happened that concerns me" |
| **Tasks** | `task` | Sidebar **Tasks** (badge = open count), `g t`, Dashboard "What to do" panel, `c t` to create | Active work — "what I must do" |

```
┌── Notifications  ◔ ─────────────────────────┐
│  ● PO-202607-0031 awaiting your approval     │  → deep-links to /purchase-orders/…
│  ● INV-202607-00142 marked paid              │
│    Vendor eval due: PaperWings               │
│  ────────────────────────────────────────    │
│  Mark all read        View all → /tasks      │
└──────────────────────────────────────────────┘
```

Relationship: a **notification** may spawn or reference a **task**; both link back to their
entity via the same deep-link rules as breadcrumbs (§4). Live domain events (D10) surface as
transient **Toasts**; their durable record is the notification/activity feed.

---

## 8. Navigation Acceptance Checklist

- [ ] Sidebar order matches Foundation §7 exactly (§2.1).
- [ ] No sidebar tier deeper than one level; deeper context = in-page tabs (§2.2).
- [ ] BU switcher scopes every operational screen and is never a breadcrumb (§3, §4.1).
- [ ] `⌘K`, all `g`-jumps, and all `c`-creates are wired and appear in the `?` cheat sheet (§5).
- [ ] Breadcrumbs cap at depth 3 and use human codes, not UUIDs (§4.1).
- [ ] Mobile: off-canvas sheet + bottom tab bar + ⌘K search (§6).
- [ ] Notifications (`notification`) and Tasks (`task`) have distinct, labeled entry points (§7).

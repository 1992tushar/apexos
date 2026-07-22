# ApexOS — Design & Architecture Docs

The versioned design system-of-record for **ApexOS**, the internal operating system of
**Apex Supply Solutions Pvt. Ltd.** Read `00` first — it governs everything else.

| # | Document | Purpose |
|---|----------|---------|
| 00 | [Canonical Foundation](./00-canonical-foundation.md) | **Source of truth** — locked decisions, domain glossary, entity list, naming, module map. If anything conflicts, this wins. |
| 01 | [Product Requirements (PRD)](./01-prd.md) | Vision, personas, scope by phase, functional & non-functional requirements, success metrics. |
| 02 | [Information Architecture](./02-information-architecture.md) | Content model, screen inventory, route map, command palette. |
| 03 | [User Roles & Permissions](./03-user-roles-and-permissions.md) | RBAC model, permission catalog, role × permission matrix. |
| 04 | [User Journeys](./04-user-journeys.md) | End-to-end core flows with diagrams. |
| 05 | [Navigation](./05-navigation.md) | Sidebar, app shell, keyboard shortcuts. |
| 06 | [Feature List](./06-feature-list.md) | Exhaustive features by module, prioritized & phased. |
| 07 | [Database ER Diagram](./07-database-er-diagram.md) | Full schema, ER diagrams, indexing, ledgers. |
| 08 | [Module Breakdown](./08-module-breakdown.md) | Modules, services, dependency graph, domain events. |
| 09 | [API Architecture](./09-api-architecture.md) | REST conventions, endpoint catalog, auth, QuickBooks bridge. |
| 10 | [Folder Structure](./10-folder-structure.md) | Monorepo layout, worked sales-order slice. |
| 11 | [Naming Standards](./11-naming-standards.md) | DB / Python / TS / API / git naming with examples. |
| 12 | [Coding Standards](./12-coding-standards.md) | Layering, type safety, testing, error handling, docs. |
| 13 | [Security Design](./13-security-design.md) | Auth, authz, data protection, threat model. |
| 14 | [Backup Strategy](./14-backup-strategy.md) | Postgres/R2 backup, DR, restore runbook. |
| 15 | [Deployment Strategy](./15-deployment-strategy.md) | Envs, CI/CD, migrations, observability. |
| 16 | [Future Roadmap](./16-future-roadmap.md) | Phased roadmap to new verticals. |
| 17 | [Design System](./17-design-system.md) | Tokens, components, tables, forms, motion, a11y. |

## The Spine (Phase 1)

The first vertical slice built end-to-end to production quality:

```
Customer → Product → Sales Order → Fulfillment (stock move) → Invoice → Receivable → Dashboard tile
```

Everything else is a variation on this proven pattern.

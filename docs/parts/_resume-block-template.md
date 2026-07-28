# Resume-block template

> Copy this into PROGRESS.md's CURRENT WORK section when opening a part.

## Resume-block template

Copy this at the start of a new part; update it at every checkpoint. Keep only the current part's
block in the `CURRENT WORK` section — move finished parts down into the chronological log below.

```
## Part <n> — <title> · on `main` · checkpoint <i> of <k> · tag when done: `part-0<n>-done`

- [x] **C1** <what it delivered> → commit `<sha>`
- [ ] **C2** <next chunk>

**Requirements passed:**      <IDs verified, e.g. R6.1–R6.6, R6.16>
**Requirements outstanding:** <IDs left>
**Gotchas for the next session:** <signature changes, migrations, half-finished refactors>
**Decisions made mid-part:**     <choices a later session must not silently reverse>

**Changed since last checkpoint:** <paths — paste from `git diff <last-tag>..HEAD --stat`>
**Read for the next checkpoint:**  <the 4–6 files it will actually modify. Be specific.>
**Call, don't read:**              <verified signatures of anything the next checkpoint calls but does
                                    not edit — copy them from the source so they're exact. Four lines
                                    here replaces a 250-line orientation read.>
**Do NOT read:**                   <what CODEBASE-MAP.md already covers; files listed above that
                                    the next checkpoint won't touch; docs already resolved>

**NEXT SESSION:** start at C<i+1>. Read this block + `docs/CODEBASE-MAP.md` + `docs/REQUIREMENTS.md` §<n>,
              then `git diff <last-tag>..HEAD --stat` for the delta. Nothing else.
```

Rules that make the block worth writing:

1. **Commit at every checkpoint**, not at part end. Uncommitted work dies with the session.
2. **Requirement IDs, not prose.** "Did the inventory stuff" is not resumable; "R6.1–R6.6 pass,
   R6.10 outstanding" is.
3. **Record decisions, not just progress.** A later session that silently reverses a mid-part
   decision is the expensive failure mode.
4. **Say what NOT to read.** Resuming sessions burn most of their budget re-establishing context they
   do not need.
5. **Name the files.** `Read for the next checkpoint` is the single highest-value line in the block.
   A session that has to *discover* which four files it needs will read twenty-five finding out.
6. **Keep `docs/CODEBASE-MAP.md` true.** If a checkpoint changes the *shape* of things — a new piece
   of shared machinery, a new pattern, a module that moved — amend the map in the same session. It is
   what lets the next session skip orientation entirely, and it is only worth reading if it's right.

---


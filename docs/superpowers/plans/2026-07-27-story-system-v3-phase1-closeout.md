# Story System v3 Phase 1 Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the already implemented Story System v3 Phase 1 with an auditable handoff, a detailed Phase 2 authoritative-runtime plan, independent review, fresh verification, and an explicit integration decision.

**Architecture:** Closeout changes documentation and, only when review identifies a concrete defect, the existing Phase 1 implementation. Runtime gameplay remains on v2. The feature branch stays isolated until the user chooses merge, pull request, preservation, or discard.

**Tech Stack:** Markdown, Git, Python 3.12, pytest, FastAPI/Pydantic/SQLAlchemy, Vue 3, TypeScript, Vite, Node test runner.

---

## File Structure

- Create `plan/reports/2026-07-27-story-system-v3-phase1-handoff.md`: authoritative Phase 1 implementation and verification handoff.
- Modify `docs/superpowers/plans/2026-07-26-story-system-v3-phase1-foundation.md`: add completion status and handoff link without rewriting historical TDD checkboxes.
- Create `docs/superpowers/plans/2026-07-27-story-system-v3-phase2-authoritative-runtime.md`: task-by-task TDD plan for the next subsystem.
- Modify Phase 1 source or tests only if independent review identifies a critical or important defect.

### Task 1: Record Phase 1 implementation handoff

**Files:**
- Create: `plan/reports/2026-07-27-story-system-v3-phase1-handoff.md`
- Modify: `docs/superpowers/plans/2026-07-26-story-system-v3-phase1-foundation.md:1-12`

- [ ] **Step 1: Capture immutable branch evidence**

Run:

```powershell
git rev-parse main
git rev-parse HEAD
git log --reverse --format="%h %s" main..HEAD
git status --short --branch
```

Expected: a clean `codex/story-v3-foundation` branch and a complete ordered commit list beginning with path traversal protection.

- [ ] **Step 2: Write the handoff report**

Create the report with these concrete sections:

```markdown
# Story System v3 Phase 1 Implementation Handoff

## Status
## Branch and commit range
## Task-to-commit traceability
## Delivered interfaces
## Completion-review evidence
## Verification commands and results
## Known warnings and environment limitations
## Deferred Phase 2 work
## Resume instructions
```

Record the exact base/head SHAs, 30-node/143-choice/846-block compilation summary, backend and frontend test counts, the Windows symlink privilege skip, and the fact that gameplay still imports `StoryV2Loader` and `TurnStore`.

- [ ] **Step 3: Mark the original plan implemented**

Add this banner immediately after the Phase 1 plan title:

```markdown
> **Implementation status:** Completed on branch `codex/story-v3-foundation`.
> **Handoff:** `plan/reports/2026-07-27-story-system-v3-phase1-handoff.md`
> The original checkboxes are preserved as the execution recipe; current completion evidence lives in the handoff report.
```

- [ ] **Step 4: Check documentation consistency**

Run:

```powershell
rg -n "Implementation status|Handoff|Runtime v2|499 passed|30 nodes|143 choices|846" docs/superpowers/plans/2026-07-26-story-system-v3-phase1-foundation.md plan/reports/2026-07-27-story-system-v3-phase1-handoff.md
git diff --check
```

Expected: the status and evidence are discoverable and no whitespace errors are reported.

- [ ] **Step 5: Commit the handoff**

```powershell
git add plan/reports/2026-07-27-story-system-v3-phase1-handoff.md docs/superpowers/plans/2026-07-26-story-system-v3-phase1-foundation.md
git commit -m "docs: add story v3 phase1 handoff"
```

### Task 2: Write the Phase 2 authoritative-runtime plan

**Files:**
- Create: `docs/superpowers/plans/2026-07-27-story-system-v3-phase2-authoritative-runtime.md`
- Reference: `docs/superpowers/specs/2026-07-26-story-system-v3-design.md:326-635`
- Reference: `plan/reports/2026-07-26-全面架构与剧情系统审查报告.md:240-548`

- [ ] **Step 1: Map the Phase 2 runtime boundaries**

Inspect and list the exact replacement points:

```powershell
rg -n "StoryV2Loader|TurnStore|GameState|resume|save|process_choice|locked_visibility|next.mode" backend/app frontend/src backend/tests
```

Expected: the plan identifies current v2 loader, in-memory turn store, client-submitted state, save/resume paths, and frontend store consumers.

- [ ] **Step 2: Define the target file structure**

The Phase 2 plan must assign one responsibility per module:

```text
backend/app/game/state.py
backend/app/game/reducer.py
backend/app/game/frame_builder.py
backend/app/game/session_repository.py
backend/app/game/turn_service.py
backend/app/routers/sessions.py
backend/app/models/game_session.py
backend/app/schemas/session.py
frontend/src/api/sessions.ts
frontend/src/stores/sessionStore.ts
```

Existing v2 runtime files remain until the new session API passes its full quality gate, then are removed in a dedicated final task.

- [ ] **Step 3: Write the task-by-task TDD plan**

Create tasks in this order, each with exact files, failing tests, commands, minimal implementation sketches, passing commands, and a commit step:

1. authoritative typed game state and invariants;
2. persistent sessions and optimistic `turn_revision`;
3. compiled v3 condition and availability evaluation;
4. typed effect execution with copy-on-write rollback;
5. navigation policies and cycle completion;
6. server-side frame building and explicit run status;
7. session create/get/choose API;
8. story-revision-bound save and resume;
9. known gameplay corrections for K, E, H, S20, and cycle semantics;
10. frontend migration to read-only turn views;
11. isolated API and core Playwright journeys;
12. removal of v2 runtime dependencies and the final quality gate.

- [ ] **Step 4: Self-review the Phase 2 plan**

Run:

```powershell
rg -n "T[B]D|T[O]DO|implement[ ]later|appropriat[e]|as[ ]needed|类似|同上" docs/superpowers/plans/2026-07-27-story-system-v3-phase2-authoritative-runtime.md
rg -n "StoryV2Loader|TurnStore|turn_revision|story_revision|locked_visibility|warp|shortcut|S20|H_choice_01" docs/superpowers/plans/2026-07-27-story-system-v3-phase2-authoritative-runtime.md
git diff --check
```

Expected: the placeholder scan returns no plan placeholders, and every mandatory runtime concept is present.

- [ ] **Step 5: Commit the Phase 2 plan**

```powershell
git add docs/superpowers/plans/2026-07-27-story-system-v3-phase2-authoritative-runtime.md
git commit -m "docs: plan story v3 authoritative runtime"
```

### Task 3: Independently review the complete Phase 1 branch

**Files:**
- Review: all files changed by `git diff --name-only main..HEAD`
- Modify: only files required to resolve critical or important findings
- Update: `plan/reports/2026-07-27-story-system-v3-phase1-handoff.md`

- [ ] **Step 1: Capture the review range**

Run:

```powershell
git rev-parse main
git rev-parse HEAD
git diff --stat main..HEAD
```

Expected: a fixed base/head pair for the reviewer.

- [ ] **Step 2: Request focused code review**

Ask the reviewer to evaluate:

```text
Requirements: docs/superpowers/plans/2026-07-26-story-system-v3-phase1-foundation.md
Design: docs/superpowers/specs/2026-07-26-story-system-v3-design.md
Focus: identifier/path safety, strict schema boundaries, deterministic migration,
compiler semantic validation, immutable publication, clean-database saves,
canonical data integrity, test isolation, and runtime-v2 scope preservation.
Report Critical, Important, and Minor findings with file and line evidence.
```

- [ ] **Step 3: Resolve critical and important findings**

For every accepted finding:

1. add or identify a failing regression test;
2. run it and confirm failure;
3. make the smallest correction;
4. run the focused test and full backend suite;
5. commit one coherent fix.

If the reviewer reports no critical or important findings, record that result in the handoff without modifying source.

- [ ] **Step 4: Record review disposition**

Add a `## Independent review` section to the handoff containing the reviewed SHA range, findings, accepted fixes, rejected findings with technical reasoning, and remaining minor notes.

- [ ] **Step 5: Commit the review record**

```powershell
git add plan/reports/2026-07-27-story-system-v3-phase1-handoff.md
git commit -m "docs: record story v3 phase1 review"
```

### Task 4: Run and record the final quality gate

**Files:**
- Modify: `plan/reports/2026-07-27-story-system-v3-phase1-handoff.md`

- [ ] **Step 1: Run the backend suite**

```powershell
python -m pytest backend/tests -q -rs
```

Expected: all tests pass; on this Windows host the resolved-directory-symlink test may be skipped with WinError 1314.

- [ ] **Step 2: Run strict canonical compilation in a temporary build root**

```powershell
$buildRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("cycle-master-phase1-closeout-" + [guid]::NewGuid().ToString("N"))
python -m backend.scripts.compile_story_v3 --strict --build-root $buildRoot
```

Expected JSON summary:

```json
{"choice_count":143,"content_block_count":846,"node_count":30,"revision":"90ff3b90b08ed94e82daeafd6af35b54c3da5aab40e36318dde2e8e4b3eef016"}
```

- [ ] **Step 3: Run frontend unit tests and production build**

```powershell
Set-Location frontend
npm.cmd run test:unit
npm.cmd run build
Set-Location ..
```

Expected: 3 unit tests pass and Vite production build exits zero. Record the existing Sass legacy API and large-chunk warnings as non-blocking.

- [ ] **Step 4: Record exact final evidence**

Update the handoff verification section with commands, counts, skip reason, strict compilation summary, build result, warning summary, final head SHA, and date.

- [ ] **Step 5: Commit and verify repository cleanliness**

```powershell
git add plan/reports/2026-07-27-story-system-v3-phase1-handoff.md
git commit -m "docs: finalize story v3 phase1 verification"
git diff --check main..HEAD
git status --short --branch
```

Expected: no whitespace errors and a clean feature branch.

### Task 5: Present the integration decision

**Files:** none

- [ ] **Step 1: Detect worktree and base branch**

```powershell
git rev-parse --git-dir
git rev-parse --git-common-dir
git merge-base HEAD main
```

Expected: a named branch in `.worktrees/story-v3-foundation`, based on `main`.

- [ ] **Step 2: Present exactly four choices**

```text
Implementation complete. What would you like to do?

1. Merge back to main locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

- [ ] **Step 3: Execute only the selected integration workflow**

Do not push, merge, delete the branch, or remove the worktree until the user selects the corresponding option. Require the exact word `discard` before option 4.

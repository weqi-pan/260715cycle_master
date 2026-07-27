# Story System v3 Phase 1 Closeout Design

> Status: approved for written-spec review
> Date: 2026-07-27
> Related implementation plan: `docs/superpowers/plans/2026-07-26-story-system-v3-phase1-foundation.md`
> Related architecture design: `docs/superpowers/specs/2026-07-26-story-system-v3-design.md`

## 1. Objective

Close the completed Story System v3 Phase 1 foundation work without extending its runtime scope. The closeout must leave an auditable handoff, a concrete Phase 2 authoritative-runtime implementation plan, a reviewed and verified feature branch, and an explicit integration decision.

## 2. Current State

The isolated worktree `.worktrees/story-v3-foundation` contains branch `codex/story-v3-foundation`. Its commits implement the eight Phase 1 tasks:

1. Story identifier validation and path traversal protection.
2. Strict v3 authoring models.
3. Deterministic v2-to-v3 migration.
4. Whole-project compilation and diagnostics.
5. Immutable revision publication.
6. Save persistence decoupled from legacy story content tables.
7. Canonical v3 story migration.
8. Schema export and strict quality gates.

The branch is clean and not merged into `main`. Runtime gameplay intentionally remains on v2, as required by the Phase 1 boundary.

## 3. Closeout Deliverables

### 3.1 Phase 1 implementation handoff

Create `plan/reports/2026-07-27-story-system-v3-phase1-handoff.md` containing:

- base and head commits;
- task-to-commit traceability;
- changed architecture and public interfaces;
- the Phase 1 completion-review checklist with evidence;
- exact fresh verification commands and results;
- the one Windows-only skipped symlink test and its reason;
- known non-blocking frontend build warnings;
- remaining risks and the explicit v2/v3 runtime boundary;
- instructions for resuming work.

The handoff must distinguish verified facts from deferred Phase 2 work.

### 3.2 Phase 1 plan status update

Update `docs/superpowers/plans/2026-07-26-story-system-v3-phase1-foundation.md` with a concise completion banner and a link to the handoff report. Preserve the original step checkboxes as an execution recipe rather than rewriting historical RED/GREEN evidence that cannot be reconstructed from the final tree.

### 3.3 Phase 2 authoritative-runtime implementation plan

Create `docs/superpowers/plans/2026-07-27-story-system-v3-phase2-authoritative-runtime.md` from the approved v3 architecture design and committed Phase 1 interfaces.

The plan will cover one subsystem: the server-authoritative gameplay runtime. It will include:

- persistent game sessions and turn revisions;
- immutable copy-on-write state transitions;
- typed condition, effect, visibility, and navigation execution;
- session API replacement for client-submitted full state;
- removal of runtime dependence on `StoryV2Loader` and in-memory `TurnStore`;
- fixes for cycle semantics, K warp exits, E crossing limits, H trust reachability, S20 restoration, and explicit ending states;
- save/resume behavior bound to story revisions;
- frontend migration to read-only turn views;
- isolated unit, API, integration, and core E2E quality gates.

The plan will not implement Phase 2 code during closeout.

### 3.4 Independent review

Request a focused code review for the complete Phase 1 diff from `main` to the feature-branch head. The review must check the Phase 1 plan and completion criteria, with special attention to security boundaries, compiler determinism, publication atomicity, migration correctness, and test isolation.

Critical and important findings must be resolved before the branch is offered for integration. Minor findings may be recorded in the handoff when they do not threaten Phase 1 correctness.

### 3.5 Final verification

Run the complete Phase 1 quality gate after all review fixes and documentation changes:

```powershell
python -m pytest backend/tests -q -rs
python -m backend.scripts.compile_story_v3 --strict --build-root <temporary-directory>
Set-Location frontend
npm.cmd run test:unit
npm.cmd run build
Set-Location ..
git diff --check main..HEAD
git status --short --branch
```

The expected outcome is:

- all backend tests pass except the documented Windows symlink-privilege skip;
- strict compilation publishes 30 nodes, 143 choices, and 846 content blocks to a temporary build root;
- frontend unit tests and production build pass;
- no whitespace errors or unintended tracked changes remain.

### 3.6 Integration decision

After verification, present the standard development-branch completion choices:

1. merge locally into `main`;
2. push and create a pull request;
3. keep the feature branch and worktree;
4. discard the feature branch and worktree.

No push, merge, branch deletion, or worktree removal occurs without the user's explicit selection. Discard additionally requires explicit destructive confirmation.

## 4. Commit Strategy

Use separate commits so the closeout remains auditable:

1. `docs: define story v3 phase1 closeout`
2. `docs: add story v3 phase1 handoff`
3. `docs: plan story v3 authoritative runtime`
4. review-fix commits only if review finds code or test issues

The final branch review and verification occur after these commits.

## 5. Acceptance Criteria

Closeout is complete when:

- the handoff report exists and contains current verification evidence;
- the original Phase 1 plan points to the handoff and clearly states its implementation status;
- the Phase 2 plan is detailed enough for task-by-task TDD execution without design guessing;
- independent review has no unresolved critical or important findings;
- the complete quality gate passes;
- the branch is clean;
- the user is presented with the four explicit integration choices.

## 6. Non-Goals

- Do not implement the Phase 2 runtime.
- Do not partially switch gameplay from v2 to v3.
- Do not redesign the frontend or editor.
- Do not push, merge, or delete branches without explicit user direction.
- Do not claim the Windows symlink test passed when the host lacks the required privilege.

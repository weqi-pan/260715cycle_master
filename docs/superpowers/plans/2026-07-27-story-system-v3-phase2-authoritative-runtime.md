# Story System v3 Phase 2 Roadmap

> Status: deferred until the demo needs production-grade runtime behavior
> Date: 2026-07-27
> This document is a roadmap, not an executable implementation plan.

## Purpose

Phase 1 already provides the v3 authoring schema, deterministic migration, whole-project compilation, immutable publication, and canonical v3 data. The current game remains a local demo whose gameplay runtime still uses v2.

Phase 2 should begin only when the project needs stronger runtime correctness, persistent sessions, or a public release. Until then, avoid a partial v2/v3 runtime switch.

## Current boundary

- Authoring and validation foundation: v3.
- Active gameplay runtime: v2 `StoryV2Loader`, `GameEngine`, and `TurnStore`.
- Frontend state flow: existing `gameStore` and `/api/game` endpoints.
- Storage: SQLite saves plus committed JSON story content.
- Editor: development-only v2 JSON editor with Phase 1 identifier/path protection.

## Milestone 1: Demo correctness

Do this first if development continues on the demo:

1. Add regression tests for the first three cycles.
2. Fix the known K exit duplication and apply one uniform warp cost.
3. Enforce the E deep-interaction limit on the server.
4. Verify `H_choice_01` is reachable through a real play path.
5. Make S20 restoration once per cycle.
6. Keep failed choices from partially mutating the current state.
7. Preserve the current screen when a request fails instead of restarting the game.

Completion signal: the core demo path is stable, repeatable, and covered by focused backend/API tests.

## Milestone 2: Server-authoritative sessions

Do this only when saves must survive service restarts or the client can no longer be trusted:

1. Add persistent `GameSession` storage with `story_revision` and `turn_revision`.
2. Replace client-submitted full state with create/get/choose session commands.
3. Reject stale commands with HTTP 409 and prevent duplicate effect application.
4. Apply choices on a copy of state and commit only after the complete turn succeeds.
5. Bind saves to the story revision used by the session.
6. Return read-only turn views with explicit `active`, `ending`, `cycle_complete`, and `blocked` status.
7. Migrate the frontend store to the session API while retaining the current turn on network errors.

Completion signal: restarting the backend can recover a saved session and the client cannot forge node, item, attribute, flag, or cycle state.

## Milestone 3: v3 runtime cutover

Do this after Milestone 2 passes its tests:

1. Execute typed v3 conditions, effects, visibility, and navigation from the published snapshot.
2. Support `locked_visibility=hide/show` and structured lock reasons.
3. Implement `travel`, `warp`, and `shortcut` as explicit navigation policies.
4. Use `completed_cycles` with derived one-based `current_cycle` everywhere.
5. Switch gameplay and saves to a fixed immutable story revision.
6. Remove runtime dependencies on `StoryV2Loader` and the in-memory `TurnStore`.
7. Keep the v2-to-v3 migration tool as an offline authoring utility until old data is retired.

Completion signal: no gameplay request imports or executes the v2 runtime.

## Milestone 4: Production tooling

These are release-hardening tasks, not demo requirements:

- revisioned editor drafts and conflict handling;
- complete lossless content editing;
- isolated Playwright story/database roots;
- CI gates for backend, frontend, strict story compilation, and core journeys;
- resource manifest enforcement and missing-asset cleanup;
- frontend code splitting and Sass dependency upgrades;
- desktop packaging.

## Recommended next task

If the project remains a demo, start only with Milestone 1 and implement one verified gameplay defect at a time. Do not start persistent sessions or the v3 cutover until the demo behavior itself is stable and there is a concrete need for those capabilities.

## Quality gates for future work

Use the smallest gate appropriate to the milestone:

```powershell
python -m pytest backend/tests -q
python -m backend.scripts.compile_story_v3 --strict --build-root <temporary-directory>
Set-Location frontend
npm.cmd run test:unit
npm.cmd run build
```

Browser E2E is required only for player journeys or editor behavior that cannot be proven reliably at the model/API level.

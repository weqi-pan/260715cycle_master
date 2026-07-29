# Story System v3 Phase 2 Roadmap

> Status: superseded by the pure-v3 Demo cutover completed on 2026-07-29
>
> Original date: 2026-07-27
>
> This document is retained as historical design context, not an active implementation plan.

## Supersession note

The original roadmap assumed the Demo would continue running the legacy story runtime until production-grade persistent sessions were built. That sequencing was replaced by the approved pure-v3 Demo cutover.

The current project now uses Story System v3 for the complete local player path:

- `data/story_v3` is the only story source;
- backend startup strictly compiles, publishes, and loads a v3 snapshot;
- conditions, effects, content, choices, repeat policies, travel, shortcut, warp, cycles, saves, and the frontend player use v3 contracts;
- the legacy story runtime, migration chain, graph engine, and visual editor have been removed.

## Completed Demo milestones

### Demo correctness

Completed and covered by backend/API tests:

1. Regression coverage for core cycles and player paths.
2. Uniform K warp exit cost without duplicated exits.
3. Server-enforced E deep-interaction limit.
4. Reachable `H_choice_01` through authored gameplay state.
5. S20 restoration once per cycle.
6. Atomic failed choices with no partial state mutation.
7. Frontend frame preservation when a request fails.

### v3 runtime cutover

Completed for the Demo:

1. Typed v3 conditions and effects execute from the active snapshot.
2. `locked_visibility=hide/show` and structured locked choices are supported.
3. `travel`, `warp`, and `shortcut` use explicit routing policies.
4. Cycle, visit, interaction, and repeat scopes are represented in v3 state.
5. Gameplay and saves validate against the active v3 registries.
6. Runtime imports no legacy story implementation.
7. The old authoring migration utility and old data were retired after canonical v3 content was verified.

## Current Demo boundary

- The backend issues one-time `turn_id` values and keeps active turns in process memory.
- SQLite stores explicit local saves and node-persistent state.
- The frontend receives read-only frames and submits player commands using the current turn.
- The player can resume a validated save, but active turns do not survive a backend restart.
- Story authoring is direct JSON plus strict compilation; there is no visual editor.
- Old saves are unsupported.
- AI NPC code has not been implemented.

## Optional future milestone: production-grade sessions

This is no longer required for the local Demo. Consider it only for public, multi-user, or cross-device operation:

1. Add persistent `GameSession` storage with `story_revision` and `turn_revision`.
2. Replace in-memory active turns with create/get/choose session commands.
3. Recover sessions after backend restart and reject stale revisions with HTTP 409.
4. Bind saves and sessions to immutable story revisions.
5. Add authentication, ownership, concurrency, retention, and migration policies.
6. Return explicit `active`, `ending`, `cycle_complete`, and `blocked` session status.

Completion signal: a backend restart can recover an authorized session and clients cannot forge any gameplay state.

## Optional future milestone: production tooling

- v3-native visual authoring, only if manual JSON becomes a real bottleneck;
- revisioned drafts and conflict handling;
- CI gates for backend, frontend, strict compilation, and core journeys;
- complete asset manifest enforcement;
- frontend code splitting and Sass dependency upgrades;
- desktop packaging;
- AI NPC dialogue bounded by v3 state, NPC knowledge, clue, and unlock allowlists.

## Current quality gates

```powershell
python -m pytest backend/tests -q
python -m backend.scripts.compile_story_v3 --strict --build-root tmp/pure-v3-final

Set-Location frontend
npm.cmd run test:unit
npm.cmd run build
Set-Location ..

python -m pytest tests/e2e/test_phase2_checklist.py tests/e2e/test_phase2_final.py tests/e2e/test_phase5_immersion.py -q
```

The browser suite covers only player-facing journeys. Removed editor behavior and retired runtime paths are intentionally excluded.

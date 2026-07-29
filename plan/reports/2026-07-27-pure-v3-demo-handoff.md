# Pure v3 Demo Cutover Handoff

> Completed: 2026-07-29
>
> Task 10 baseline commit: `3482fce`
>
> Task 11 finalization commit: the commit containing this report; resolve with `git rev-parse HEAD` after checkout because a commit cannot embed its own final SHA.

## Outcome

Cycle Master is now a pure Story System v3 Demo. The active game has one story source, one runtime contract, one player API flow, and one save-state model.

- `data/story_v3` is the only authoring source.
- Backend startup strictly compiles, publishes, and loads the v3 snapshot.
- Runtime conditions, effects, content, choices, repeat policies, routing, cycles, saves, and frontend frames use v3.
- The runtime import boundary is enforced by `backend/tests/test_pure_v3_boundary.py`.
- The visual editor and old save compatibility are not supported.
- AI NPC code is not present and has not started.

## Retained inventory

- 30 v3 node JSON files plus project registries and exported v3 Schema.
- Immutable story compilation and publication under `backend/app/story`.
- v3 runtime repository, condition evaluator, effect executor, content resolver, routing engine, and turn store.
- `/api/game` and `/api/saves` player APIs.
- SQLite `saves` and `node_persistent_state` persistence tables.
- Vue player, ordered story timeline, status bar, inventory, save/load panel, and cycle map.
- Backend unit/API tests, frontend unit tests, and 27 focused player-facing E2E checks.

## Deleted inventory

- All legacy story data and its Schema.
- Legacy story loader, graph engine, special router, and migration/validation chain.
- Backend editor repository, routes, Schemas, and authoring models.
- Frontend editor route, view, and components.
- Duplicate item/NPC registries and old story database tables.
- Tests that only exercised retired runtime or editor internals.

## Verification record

| Gate | Result |
|---|---|
| Backend suite | 263 passed, 1 skipped |
| Strict v3 compile | 30 nodes, 143 choices, 846 content blocks |
| Frontend unit tests | 8 passed |
| Frontend production build | passed |
| Core player E2E | 27 passed |
| Runtime import | `Cycle Master API` imports successfully from repository root |
| Legacy audit | no active legacy story reference in backend, frontend, data, scripts, tests, README, or CHANGELOG |

The strict compile revision recorded during finalization was:

```text
cb12b416d0a9f0d2ab91f5477a4200365a0449fe9cdf37808b84207de21f69a6
```

## Player journeys covered

- explicit “踏入循环” start flow;
- visible-but-disabled locked choices and exploration unlocks;
- clue/item acquisition and repeat removal;
- authoritative `turn_id` progression and replay rejection;
- A→H main-ring traversal and cycle completion;
- E→J shortcut and H→K warp routes;
- local save create/load/update/delete and validated resume;
- ordered narration/dialogue playback, NPC display names, map, status, and refresh behavior.

## Unsupported compatibility

- Old saves are not migrated or guaranteed to load.
- The removed editor has no replacement in this Demo.
- Removed legacy data and migration tools are not retained as a fallback.

## Known Demo limitations

- Active turns are stored in backend process memory; a restart invalidates an unsaved turn.
- SQLite saves are local and have no account ownership, multi-user isolation, or cross-device synchronization.
- Content authoring is direct v3 JSON plus strict compilation.
- Frontend production build still reports Sass legacy API warnings and a large main bundle warning.
- Desktop packaging and complete asset-manifest enforcement remain future work.
- AI NPC dialogue, provider configuration, NPC knowledge boundaries, clue allowlists, and unlock allowlists remain future work.

## Recommended next step

Treat this commit as the new Demo baseline. Add new gameplay or AI NPC work only through v3 contracts, with focused backend tests and player E2E for each new behavior. Do not restore removed compatibility layers.

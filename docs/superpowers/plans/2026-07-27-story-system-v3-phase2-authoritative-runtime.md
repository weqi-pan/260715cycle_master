# Story System v3 Phase 2 Authoritative Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace client-owned game state with a persistent, story-revision-bound, optimistic-concurrency session runtime that executes the compiled Story System v3 snapshot transactionally and returns read-only turn views.

**Architecture:** The published `StorySnapshotV3` is the immutable runtime story source, while SQLite-backed `GameSession` rows are the authoritative player-state source. A pure copy-on-write reducer evaluates typed conditions, effects, availability, repeat scopes, and navigation; `TurnService` builds a complete frame before an optimistic `turn_revision` update commits state and audit data in one transaction. The existing v2 runtime stays available until Tasks 1-11 pass their full gate, and Task 12 removes it in one dedicated deletion commit.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2.10, SQLAlchemy 2.0, SQLite, pytest 9, Vue 3, Pinia, TypeScript 5.5, Axios, Vite, Node test runner, Playwright.

---

## Runtime replacement map

The initial replacement search is:

```powershell
rg -n "StoryV2Loader|TurnStore|GameState|resume|save|process_choice|locked_visibility|next\.mode" backend/app frontend/src backend/tests
```

It identifies these live authority paths:

- `backend/app/routers/game.py` constructs `StoryV2Loader` and `TurnStore`, accepts client state through `/api/game/resume`, and delegates to the in-place v2 `process_choice` pipeline.
- `backend/app/routers/saves.py` accepts and returns full client-visible `GameState` snapshots.
- `backend/app/engine/engine.py` mutates `GameState` in place while applying effects.
- `backend/app/engine/story_v2_loader.py` and `backend/app/engine/turn_store.py` are runtime dependencies that remain until Task 12.
- `frontend/src/api/game.ts`, `frontend/src/stores/gameStore.ts`, and `frontend/src/views/GamePlay.vue` create, resume, choose, save, and load through client-owned state.
- `backend/app/schemas/story_v3.py` already preserves typed `ConditionV3`, `StoryEffectV3`, `locked_visibility`, structured routing, and `next.mode`; the new runtime consumes these compiled snapshot values directly.

## File responsibilities

### New authoritative runtime modules

- `backend/app/game/state.py` — frozen typed player, world, loop, visit, crossing, history, and authoritative `GameState` values plus invariant validation.
- `backend/app/game/reducer.py` — pure condition, repeat, availability, effect, and navigation execution over `StorySnapshotV3`; returns a new state and transition data without persistence.
- `backend/app/game/frame_builder.py` — converts a snapshot plus authoritative state into the read-only `TurnView`, including structured locks and explicit run status.
- `backend/app/game/session_repository.py` — loads, inserts, conditionally updates, saves, and resumes persisted sessions without containing story rules.
- `backend/app/game/turn_service.py` — pins one story revision, validates a command version, invokes reducer and frame builder, and commits only after the complete turn succeeds.
- `backend/app/models/game_session.py` — SQLAlchemy `GameSession`, `GameSave`, and `ChoiceAudit` tables with no foreign key to story content tables.
- `backend/app/schemas/session.py` — command and read-only response schemas for create/get/choose/save/resume.
- `backend/app/routers/sessions.py` — FastAPI transport mapping for the authoritative session service and stable HTTP error codes.
- `frontend/src/api/sessions.ts` — typed session commands; no function accepts authoritative game state.
- `frontend/src/stores/sessionStore.ts` — stores only the latest `TurnView`, retains it on errors, and refreshes the same session after HTTP 409.

### Existing files changed before cutover

- `backend/app/story/publisher.py` — load and verify a specified immutable revision for long-lived sessions and saves.
- `backend/app/main.py` — register the new session router beside the v2 router until Task 12.
- `backend/app/paths.py` and `backend/app/config.py` — expose isolated database, story source, and build roots for tests and local launches.
- `backend/tests/conftest.py` — construct temporary database/story/build fixtures and publish a test snapshot.
- `frontend/src/types/index.ts` — export generated-compatible turn view and command types during migration.
- `frontend/src/views/GamePlay.vue` — render `TurnView`, use server availability/status, and remove client-state save/resume calls.

### Dedicated final removals

- `backend/app/routers/game.py`, `backend/app/routers/saves.py`, `backend/app/engine/engine.py`, `backend/app/engine/condition_eval.py`, `backend/app/engine/graph.py`, `backend/app/engine/special_router.py`, `backend/app/engine/story_v2_loader.py`, `backend/app/engine/turn_store.py`, `backend/app/schemas/game.py`, `backend/app/models/save.py`, and `backend/app/models/story.py` — delete only in Task 12 after the new-runtime gate passes.
- `frontend/src/api/game.ts`, `frontend/src/stores/gameStore.ts`, and `frontend/src/player/choiceVisibility.ts` — delete only in Task 12 after `GamePlay.vue` and Playwright use session APIs.
- `backend/app/story/v2_migration.py` — replace its `StoryV2Loader` dependency with a migration-local read-only v2 source reader before deleting the runtime loader.

## Shared signature contract

The tasks below use these names without aliases:

```python
# backend/app/game/state.py
RunStatus = Literal["active", "ending", "cycle_complete", "blocked"]

class GameState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    current_node_id: str
    player: PlayerState
    world: WorldState
    loop: LoopState
    visit: VisitState
    crossing: CrossingState | None = None
    history: ChoiceHistory = Field(default_factory=ChoiceHistory)

    @property
    def current_cycle(self) -> int:
        return self.loop.completed_cycles + 1

    validate_against(snapshot: StorySnapshotV3) -> None

# backend/app/game/reducer.py
class LockReason(BaseModel):
    code: str
    message: str

class ChoiceDecision(BaseModel):
    visible: bool
    enabled: bool
    reason: LockReason | None

class TransitionResult(BaseModel):
    state: GameState
    result_blocks: list[ContentBlockV3]
    choice_id: str
    status: RunStatus

evaluate_condition(condition: ConditionV3 | None, state: GameState) -> bool
evaluate_choice(snapshot: StorySnapshotV3, state: GameState, choice: StoryChoiceV3) -> ChoiceDecision
apply_effects(snapshot: StorySnapshotV3, state: GameState, effects: list[StoryEffectV3]) -> GameState
reduce_choice(snapshot: StorySnapshotV3, state: GameState, choice_id: str) -> TransitionResult

# backend/app/game/frame_builder.py
def build_turn_view(
    snapshot: StorySnapshotV3,
    state: GameState,
    *,
    session_id: str,
    turn_revision: int,
    result_blocks: list[ContentBlockV3],
    status: RunStatus | None = None,
) -> TurnView

# backend/app/game/session_repository.py
class SessionRepository:
    create(state: GameState, *, story_revision: str, status: RunStatus) -> SessionRecord
    get(session_id: str) -> SessionRecord
    commit_turn(session_id: str, *, expected_revision: int, state: GameState, status: RunStatus, choice_id: str) -> SessionRecord
    create_save(session_id: str, *, expected_revision: int, name: str) -> SaveRecord
    resume_save(save_id: str) -> SessionRecord

# backend/app/game/turn_service.py
class TurnService:
    create_session() -> TurnView
    get_session(session_id: str) -> TurnView
    choose(session_id: str, command: ChooseCommand) -> TurnView
    save(session_id: str, command: SaveCommand) -> SaveView
    resume(command: ResumeCommand) -> TurnView
```

These are interface declarations rather than executable Python. Later tasks must not rename these arguments, fields, or return types.

### Task 1: Authoritative typed game state and invariants

**Files:**

- Create: `backend/app/game/__init__.py`
- Create: `backend/app/game/state.py`
- Create: `backend/tests/game/test_state.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Write the failing state and invariant tests**

```python
# backend/tests/game/test_state.py
import pytest
from pydantic import ValidationError

from app.game.state import GameState, initial_game_state


def test_initial_state_uses_completed_cycles_and_one_based_current_cycle(published_story):
    state = initial_game_state(published_story.snapshot)
    assert state.current_node_id == published_story.snapshot.project.entry_node_id
    assert state.loop.completed_cycles == 0
    assert state.current_cycle == 1
    assert state.player.attributes["sanity"] == 100


def test_state_is_frozen_and_rejects_unknown_nodes(published_story):
    state = initial_game_state(published_story.snapshot)
    with pytest.raises(ValidationError, match="frozen"):
        state.current_node_id = "K"

    invalid = state.model_copy(update={"current_node_id": "missing"})
    with pytest.raises(ValueError, match="unknown current node"):
        invalid.validate_against(published_story.snapshot)
```

- [ ] **Step 2: Run RED and confirm the missing module**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_state.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'app.game'`.

- [ ] **Step 3: Add the frozen state model and explicit scopes**

```python
# backend/app/game/state.py
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.story_v3 import StorySnapshotV3

RunStatus = Literal["active", "ending", "cycle_complete", "blocked"]
Scalar = bool | int | str


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PlayerState(FrozenModel):
    attributes: dict[str, int]
    inventory: dict[str, int] = Field(default_factory=dict)


class WorldState(FrozenModel):
    flags: dict[str, Scalar]
    persistent_node_items: dict[str, frozenset[str]] = Field(default_factory=dict)


class LoopState(FrozenModel):
    completed_cycles: int = Field(default=0, ge=0)
    half_cycles: int = Field(default=0, ge=0)
    cycle_once_keys: frozenset[str] = Field(default_factory=frozenset)


class VisitState(FrozenModel):
    visit_id: int = Field(default=1, ge=1)
    node_id: str
    chosen_ids: frozenset[str] = Field(default_factory=frozenset)
    once_keys: frozenset[str] = Field(default_factory=frozenset)
    entry_attributes: dict[str, int]


class CrossingState(FrozenModel):
    crossing_id: int = Field(ge=1)
    node_id: str
    interaction_count: int = Field(default=0, ge=0)
    interacted_npcs: frozenset[str] = Field(default_factory=frozenset)


class ChoiceHistory(FrozenModel):
    cycle_choice_ids: frozenset[str] = Field(default_factory=frozenset)
    session_choice_ids: frozenset[str] = Field(default_factory=frozenset)
    session_once_keys: frozenset[str] = Field(default_factory=frozenset)


class GameState(FrozenModel):
    current_node_id: str
    player: PlayerState
    world: WorldState
    loop: LoopState
    visit: VisitState
    crossing: CrossingState | None = None
    history: ChoiceHistory = Field(default_factory=ChoiceHistory)

    @property
    def current_cycle(self) -> int:
        return self.loop.completed_cycles + 1

    def validate_against(self, snapshot: StorySnapshotV3) -> None:
        if self.current_node_id not in snapshot.nodes:
            raise ValueError(f"unknown current node: {self.current_node_id}")
        if self.visit.node_id != self.current_node_id:
            raise ValueError("visit node must equal current node")
        if self.crossing is not None and self.crossing.node_id != self.current_node_id:
            raise ValueError("crossing node must equal current node")
        for name, definition in snapshot.project.attributes.items():
            value = self.player.attributes[name]
            if not definition.minimum <= value <= definition.maximum:
                raise ValueError(f"attribute outside bounds: {name}")


def initial_game_state(snapshot: StorySnapshotV3) -> GameState:
    node_id = snapshot.project.entry_node_id
    attributes = {key: value.default for key, value in snapshot.project.attributes.items()}
    state = GameState(
        current_node_id=node_id,
        player=PlayerState(attributes=attributes),
        world=WorldState(flags={key: value.default for key, value in snapshot.project.flags.items()}),
        loop=LoopState(),
        visit=VisitState(node_id=node_id, entry_attributes=attributes),
    )
    state.validate_against(snapshot)
    return state
```

- [ ] **Step 4: Add a published snapshot fixture with temporary source and build roots**

```python
# backend/tests/conftest.py
@pytest.fixture
def published_story(tmp_path):
    story_root = tmp_path / "story_v3"
    build_root = tmp_path / "story_build"
    shutil.copytree(PROJECT_ROOT / "data" / "story_v3", story_root)
    compilation = StoryCompiler().compile(story_root)
    published = StoryPublisher(build_root).publish(compilation, base_revision=None)
    return SimpleNamespace(
        story_root=story_root,
        build_root=build_root,
        snapshot=StoryPublisher(build_root).load_active(),
        revision=published.revision,
    )
```

- [ ] **Step 5: Run GREEN**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_state.py -q`

Expected: PASS with `2 passed`; mutations are rejected and the first displayed cycle is `1`.

- [ ] **Step 6: Run focused and full verification**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_state.py backend/tests/test_story_v3_schema.py backend/tests/test_story_v3_compiler.py -q`

Expected: PASS with no writes under `data/story_v3` or `data/story_build`.

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests -q -rs`

Expected: the complete backend suite passes.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/game/__init__.py backend/app/game/state.py backend/tests/game/test_state.py backend/tests/conftest.py
git commit -m "feat: add authoritative game state"
```

### Task 2: Persistent sessions and optimistic `turn_revision`

**Files:**

- Create: `backend/app/models/game_session.py`
- Create: `backend/app/game/session_repository.py`
- Create: `backend/tests/game/test_session_repository.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/story/publisher.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Write failing persistence, restart, and stale-revision tests**

```python
# backend/tests/game/test_session_repository.py
import pytest

from app.game.session_repository import SessionRepository, StaleTurnRevision
from app.game.state import initial_game_state


def test_session_persists_story_and_turn_revision(isolated_db_session, published_story):
    repository = SessionRepository(isolated_db_session)
    created = repository.create(
        initial_game_state(published_story.snapshot),
        story_revision=published_story.revision,
        status="active",
    )
    loaded = repository.get(created.id)
    assert loaded.story_revision == published_story.revision
    assert loaded.turn_revision == 0


def test_stale_commit_cannot_double_apply_effects(isolated_db_session, published_story):
    repository = SessionRepository(isolated_db_session)
    created = repository.create(initial_game_state(published_story.snapshot), story_revision=published_story.revision, status="active")
    next_state = created.state.model_copy(update={"player": created.state.player.model_copy(update={"inventory": {"item_coin": 1}})})
    committed = repository.commit_turn(created.id, expected_revision=0, state=next_state, status="active", choice_id="A_choice_01")
    assert committed.turn_revision == 1

    with pytest.raises(StaleTurnRevision, match="expected 0, actual 1"):
        repository.commit_turn(created.id, expected_revision=0, state=next_state, status="active", choice_id="A_choice_01")
    assert repository.get(created.id).state.player.inventory == {"item_coin": 1}
```

- [ ] **Step 2: Run RED and confirm repository types are absent**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_session_repository.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'app.game.session_repository'`.

- [ ] **Step 3: Add session, save, and audit tables without story-table foreign keys**

```python
# backend/app/models/game_session.py
class GameSession(Base):
    __tablename__ = "game_sessions"
    id = Column(String, primary_key=True)
    story_revision = Column(String(64), nullable=False, index=True)
    turn_revision = Column(Integer, nullable=False, default=0)
    current_node_id = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    state_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class GameSave(Base):
    __tablename__ = "game_saves"
    id = Column(String, primary_key=True)
    name = Column(String(120), nullable=False)
    story_revision = Column(String(64), nullable=False, index=True)
    source_turn_revision = Column(Integer, nullable=False)
    current_node_id = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    state_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class ChoiceAudit(Base):
    __tablename__ = "choice_audits"
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_revision = Column(Integer, nullable=False)
    choice_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)
    __table_args__ = (UniqueConstraint("session_id", "turn_revision"),)
```

- [ ] **Step 4: Implement conditional-update persistence and revision loading**

```python
# backend/app/game/session_repository.py
@dataclass(frozen=True, slots=True)
class SessionRecord:
    id: str
    story_revision: str
    turn_revision: int
    state: GameState
    status: RunStatus

    @classmethod
    def from_row(cls, row: GameSession) -> "SessionRecord":
        return cls(id=row.id, story_revision=row.story_revision, turn_revision=row.turn_revision, state=_decode_state(row.state_json), status=row.status)


@dataclass(frozen=True, slots=True)
class SaveRecord:
    id: str
    name: str
    story_revision: str
    source_turn_revision: int

    @classmethod
    def from_row(cls, row: GameSave) -> "SaveRecord":
        return cls(id=row.id, name=row.name, story_revision=row.story_revision, source_turn_revision=row.source_turn_revision)


class SessionNotFound(RuntimeError):
    pass


class SaveNotFound(RuntimeError):
    pass


class StaleTurnRevision(RuntimeError):
    def __init__(self, expected: int, actual: int):
        super().__init__(f"expected {expected}, actual {actual}")
        self.expected = expected
        self.actual = actual


def _encode_state(state: GameState) -> str:
    return state.model_dump_json()


def _decode_state(payload: str) -> GameState:
    return GameState.model_validate_json(payload)


class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, session_id: str) -> SessionRecord:
        row = self.db.get(GameSession, session_id)
        if row is None:
            raise SessionNotFound(session_id)
        return SessionRecord.from_row(row)

    def commit_turn(self, session_id: str, *, expected_revision: int, state: GameState, status: RunStatus, choice_id: str) -> SessionRecord:
        updated = self.db.execute(
            update(GameSession)
            .where(GameSession.id == session_id, GameSession.turn_revision == expected_revision)
            .values(
                turn_revision=expected_revision + 1,
                current_node_id=state.current_node_id,
                status=status,
                state_json=_encode_state(state),
                updated_at=_utcnow(),
            )
        )
        if updated.rowcount != 1:
            actual = self.get(session_id).turn_revision
            self.db.rollback()
            raise StaleTurnRevision(expected_revision, actual)
        self.db.add(ChoiceAudit(id=uuid4().hex, session_id=session_id, turn_revision=expected_revision + 1, choice_id=choice_id, created_at=_utcnow()))
        self.db.commit()
        return self.get(session_id)
```

```python
# backend/app/story/publisher.py
def load_revision(self, revision: str) -> StorySnapshotV3:
    if not _is_revision(revision):
        raise StoryRevisionIntegrityError("Requested story revision is invalid.")
    return self._verify_revision(self.revisions_root / revision, revision)
```

- [ ] **Step 5: Run GREEN**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_session_repository.py -q`

Expected: PASS; the second commit raises `StaleTurnRevision` and only one audit/state update exists.

- [ ] **Step 6: Run focused and full verification for clean database and publisher behavior**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_session_repository.py backend/tests/test_clean_database.py backend/tests/test_story_v3_publisher.py -q`

Expected: PASS; `Base.metadata.create_all()` creates session tables in an empty temporary SQLite file and `load_revision()` verifies immutable artifacts.

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests -q -rs`

Expected: the complete backend suite passes.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/models/game_session.py backend/app/game/session_repository.py backend/app/models/__init__.py backend/app/story/publisher.py backend/tests/game/test_session_repository.py backend/tests/conftest.py
git commit -m "feat: persist versioned game sessions"
```

### Task 3: Compiled v3 condition and availability evaluation

**Files:**

- Create: `backend/app/game/reducer.py`
- Create: `backend/tests/game/test_condition_availability.py`
- Modify: `backend/app/game/__init__.py`

- [ ] **Step 1: Write failing typed-condition and locked-visibility tests**

```python
# backend/tests/game/test_condition_availability.py
from app.game.reducer import evaluate_choice
from app.game.state import initial_game_state


def test_locked_visibility_hide_omits_locked_choice(published_story):
    snapshot = published_story.snapshot
    state = initial_game_state(snapshot)
    choice = snapshot.nodes["A"].choices[2]
    choice = choice.model_copy(update={"availability": choice.availability.model_copy(update={"locked_visibility": "hide"})})
    decision = evaluate_choice(snapshot, state, choice)
    assert decision.visible is False
    assert decision.enabled is False


def test_locked_visibility_show_returns_structured_reason(published_story):
    snapshot = published_story.snapshot
    state = initial_game_state(snapshot)
    choice = snapshot.nodes["H"].choices[0]
    decision = evaluate_choice(snapshot, state, choice)
    assert decision.visible is True
    assert decision.enabled is False
    assert decision.reason.model_dump() == {
        "code": "condition_not_met",
        "message": "张天民要把记录了55天循环的笔记本交给你",
    }
```

- [ ] **Step 2: Run RED and confirm evaluator is absent**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_condition_availability.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'app.game.reducer'`.

- [ ] **Step 3: Implement exhaustive evaluation over compiled v3 unions**

```python
# backend/app/game/reducer.py
class LockReason(BaseModel):
    code: str
    message: str


class ChoiceDecision(BaseModel):
    visible: bool
    enabled: bool
    reason: LockReason | None = None


def _compare(left: int, operator: str, right: int) -> bool:
    return {
        "lt": left < right,
        "lte": left <= right,
        "eq": left == right,
        "ne": left != right,
        "gte": left >= right,
        "gt": left > right,
    }[operator]


def evaluate_condition(condition: ConditionV3 | None, state: GameState) -> bool:
    if condition is None:
        return True
    if isinstance(condition, AttributeCompareCondition):
        return _compare(state.player.attributes[condition.attribute], condition.operator, condition.value)
    if isinstance(condition, FlagEqualsCondition):
        return state.world.flags[condition.flag] == condition.value
    if isinstance(condition, ItemCondition):
        present = state.player.inventory.get(condition.item_id, 0) > 0
        return present is condition.present
    if isinstance(condition, CounterCompareCondition):
        value = state.current_cycle if condition.counter == "current_cycle" else getattr(state.loop, condition.counter)
        return _compare(value, condition.operator, condition.value)
    if isinstance(condition, AtNodeCondition):
        return state.current_node_id == condition.node_id
    if isinstance(condition, AllCondition):
        return all(evaluate_condition(item, state) for item in condition.conditions)
    if isinstance(condition, AnyCondition):
        return any(evaluate_condition(item, state) for item in condition.conditions)
    if isinstance(condition, NotCondition):
        return not evaluate_condition(condition.condition, state)
    raise TypeError(f"unsupported compiled condition: {type(condition).__name__}")


def evaluate_choice(snapshot: StorySnapshotV3, state: GameState, choice: StoryChoiceV3) -> ChoiceDecision:
    if evaluate_condition(choice.availability.condition, state) and _repeat_available(choice, state):
        return ChoiceDecision(visible=True, enabled=True)
    if choice.availability.locked_visibility == "hide":
        return ChoiceDecision(visible=False, enabled=False)
    message = choice.availability.locked_reason or choice.hint or "当前条件尚未满足"
    return ChoiceDecision(visible=True, enabled=False, reason=LockReason(code="condition_not_met", message=message))
```

- [ ] **Step 4: Cover repeat scopes with stable keys**

```python
def _repeat_available(choice: StoryChoiceV3, state: GameState) -> bool:
    if choice.repeat_policy == "always":
        return True
    if choice.repeat_policy == "once_per_visit":
        return choice.id not in state.visit.chosen_ids
    if choice.repeat_policy == "once_per_cycle":
        return choice.id not in state.history.cycle_choice_ids
    if choice.repeat_policy == "once_ever":
        return choice.id not in state.history.session_choice_ids
    raise TypeError(f"unsupported repeat policy: {choice.repeat_policy}")
```

- [ ] **Step 5: Run GREEN**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_condition_availability.py -q`

Expected: PASS; `hide` returns no visible choice, while `show` returns a disabled choice with `{code, message}`.

- [ ] **Step 6: Run focused and full verification**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_condition_availability.py backend/tests/test_story_v3_schema.py backend/tests/test_story_v3_compiler.py -q`

Expected: PASS and every evaluated value originates from a validated `StorySnapshotV3` union member.

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests -q -rs`

Expected: the complete backend suite passes.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/game/reducer.py backend/app/game/__init__.py backend/tests/game/test_condition_availability.py
git commit -m "feat: evaluate v3 choice availability"
```

### Task 4: Typed effect execution with copy-on-write rollback

**Files:**

- Modify: `backend/app/game/reducer.py`
- Create: `backend/tests/game/test_effect_reducer.py`

- [ ] **Step 1: Write a failing mid-effect rollback test**

```python
# backend/tests/game/test_effect_reducer.py
import pytest

from app.game.reducer import EffectExecutionError, apply_effects
from app.game.state import initial_game_state
from app.schemas.story_v3 import InventoryEffect, SetFlagEffect


def test_effect_failure_does_not_mutate_original_state(published_story):
    snapshot = published_story.snapshot
    original = initial_game_state(snapshot)
    effects = [
        SetFlagEffect(type="set_flag", flag="taoist_chant", value=True),
        InventoryEffect(type="inventory", item_id="item_coin", operation="remove", quantity=1),
    ]
    with pytest.raises(EffectExecutionError, match="cannot remove item_coin"):
        apply_effects(snapshot, original, effects)
    assert original.world.flags["taoist_chant"] is False
    assert original.player.inventory == {}
```

- [ ] **Step 2: Run RED and confirm effect execution is absent**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_effect_reducer.py -q`

Expected: FAIL during collection with `ImportError: cannot import name 'apply_effects'`.

- [ ] **Step 3: Implement immutable typed effect dispatch**

```python
# backend/app/game/reducer.py
class EffectExecutionError(RuntimeError):
    pass


def apply_effects(snapshot: StorySnapshotV3, state: GameState, effects: list[StoryEffectV3]) -> GameState:
    working = state.model_copy(deep=True)
    try:
        for effect in effects:
            working = _apply_effect(snapshot, working, effect)
        working.validate_against(snapshot)
        return working
    except Exception as exc:
        if isinstance(exc, EffectExecutionError):
            raise
        raise EffectExecutionError(str(exc)) from exc


def _apply_effect(snapshot: StorySnapshotV3, state: GameState, effect: StoryEffectV3) -> GameState:
    if isinstance(effect, SetFlagEffect):
        flags = dict(state.world.flags)
        flags[effect.flag] = effect.value
        return state.model_copy(update={"world": state.world.model_copy(update={"flags": flags})})
    if isinstance(effect, ModifyAttributeEffect):
        attributes = dict(state.player.attributes)
        definition = snapshot.project.attributes[effect.attribute]
        value = effect.value if effect.operation == "set" else attributes[effect.attribute] + effect.value
        attributes[effect.attribute] = min(definition.maximum, max(definition.minimum, value)) if effect.clamp else value
        return state.model_copy(update={"player": state.player.model_copy(update={"attributes": attributes})})
    if isinstance(effect, InventoryEffect):
        inventory = dict(state.player.inventory)
        current = inventory.get(effect.item_id, 0)
        if effect.operation == "remove" and current < effect.quantity:
            raise EffectExecutionError(f"cannot remove {effect.item_id}: have {current}, need {effect.quantity}")
        next_quantity = current + effect.quantity if effect.operation == "add" else current - effect.quantity
        if next_quantity == 0:
            inventory.pop(effect.item_id, None)
        else:
            inventory[effect.item_id] = next_quantity
        return state.model_copy(update={"player": state.player.model_copy(update={"inventory": inventory})})
    return _apply_scoped_effect(snapshot, state, effect)
```

- [ ] **Step 4: Implement the remaining compiled effect variants explicitly**

Add exhaustive branches in `_apply_scoped_effect()` for `PersistNodeItemEffect`, `RecordInteractionEffect`, `ModifyCounterEffect`, `MarkOnceEffect`, and `RestoreEntryAttributeEffect`. `RestoreEntryAttributeEffect` reads `state.visit.entry_attributes[effect.attribute]`; `MarkOnceEffect` stores keys in visit, cycle, or session scope; an unhandled union member raises `EffectExecutionError`.

```python
def _apply_scoped_effect(snapshot: StorySnapshotV3, state: GameState, effect: StoryEffectV3) -> GameState:
    if isinstance(effect, RestoreEntryAttributeEffect):
        restored = state.visit.entry_attributes[effect.attribute]
        attributes = {**state.player.attributes, effect.attribute: restored}
        return state.model_copy(update={"player": state.player.model_copy(update={"attributes": attributes})})
    if isinstance(effect, ModifyCounterEffect):
        current = getattr(state.loop, effect.counter)
        value = effect.value if effect.operation == "set" else current + effect.value
        if value < 0:
            raise EffectExecutionError(f"counter cannot be negative: {effect.counter}")
        updates = {effect.counter: value}
        if effect.counter == "completed_cycles" and value != current:
            updates["cycle_once_keys"] = frozenset()
        return state.model_copy(update={"loop": state.loop.model_copy(update=updates)})
    if isinstance(effect, MarkOnceEffect):
        return _mark_once(state, key=effect.key, scope=effect.scope)
    if isinstance(effect, RecordInteractionEffect):
        return _record_interaction(state, group=effect.group, subject_id=effect.subject_id)
    if isinstance(effect, PersistNodeItemEffect):
        return _persist_node_item(state, node_id=effect.node_id, item_id=effect.item_id)
    raise EffectExecutionError(f"unsupported compiled effect: {type(effect).__name__}")
```

- [ ] **Step 5: Run GREEN**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_effect_reducer.py -q`

Expected: PASS; the first effect exists only in the discarded working copy after the second effect fails.

- [ ] **Step 6: Run focused and full verification**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_effect_reducer.py backend/tests/game/test_state.py backend/tests/test_story_v3_schema.py -q`

Expected: PASS with typed dispatch for every `StoryEffectV3` member.

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests -q -rs`

Expected: the complete backend suite passes.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/game/reducer.py backend/tests/game/test_effect_reducer.py
git commit -m "feat: execute v3 effects transactionally"
```

### Task 5: Navigation policies and cycle completion

**Files:**

- Modify: `backend/app/game/reducer.py`
- Modify: `data/story_v3/nodes/H.json`
- Create: `backend/tests/game/support.py`
- Create: `backend/tests/game/test_navigation.py`

- [ ] **Step 1: Write failing travel, warp, shortcut, and cycle tests**

```python
# backend/tests/game/test_navigation.py
from app.game.reducer import reduce_choice
from app.game.state import initial_game_state
from backend.tests.game.support import state_at_node


def test_travel_starts_a_new_visit(published_story):
    state = initial_game_state(published_story.snapshot)
    result = reduce_choice(published_story.snapshot, state, "A_choice_01")
    assert result.state.current_node_id == "B"
    assert result.state.visit.visit_id == state.visit.visit_id + 1


def test_k_warp_applies_snapshot_exit_cost_once(published_story):
    state = state_at_node(published_story.snapshot, "K")
    result = reduce_choice(published_story.snapshot, state, "K_choice_02")
    assert result.state.current_node_id == "A"
    assert result.state.player.attributes["sanity_max"] == state.player.attributes["sanity_max"] - 1


def test_cycle_completion_increments_completed_cycles_before_next_cycle(published_story):
    state = state_at_node(published_story.snapshot, "H")
    result = reduce_choice(published_story.snapshot, state, "H_choice_09")
    assert result.state.loop.completed_cycles == 1
    assert result.state.current_cycle == 2
    assert result.status == "cycle_complete"
```

- [ ] **Step 2: Run RED and confirm navigation is not implemented**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_navigation.py -q`

Expected: FAIL with `ImportError: cannot import name 'reduce_choice'`.

- [ ] **Step 3: Add deterministic state constructors for reducer tests**

```python
# backend/tests/game/support.py
def state_at_node(snapshot, node_id, *, completed_cycles=0, attributes=None, flags=None, entry_attributes=None):
    state = initial_game_state(snapshot)
    player_attributes = {**state.player.attributes, **(attributes or {})}
    world_flags = {**state.world.flags, **(flags or {})}
    visit = VisitState(
        visit_id=state.visit.visit_id + 1,
        node_id=node_id,
        entry_attributes=entry_attributes or dict(player_attributes),
    )
    crossing = CrossingState(crossing_id=visit.visit_id, node_id=node_id) if isinstance(snapshot.nodes[node_id].routing, CrossingRoutingV3) else None
    return state.model_copy(update={
        "current_node_id": node_id,
        "player": state.player.model_copy(update={"attributes": player_attributes}),
        "world": state.world.model_copy(update={"flags": world_flags}),
        "loop": state.loop.model_copy(update={"completed_cycles": completed_cycles}),
        "visit": visit,
        "crossing": crossing,
    })
```

- [ ] **Step 4: Implement the pure reducer pipeline**

```python
# backend/app/game/reducer.py
class InvalidChoice(RuntimeError):
    pass


class TransitionResult(BaseModel):
    state: GameState
    result_blocks: list[ContentBlockV3]
    choice_id: str
    status: RunStatus


def reduce_choice(snapshot: StorySnapshotV3, state: GameState, choice_id: str) -> TransitionResult:
    node = snapshot.nodes[state.current_node_id]
    choice = next((item for item in node.choices if item.id == choice_id), None)
    if choice is None:
        raise InvalidChoice(f"unknown choice: {choice_id}")
    decision = evaluate_choice(snapshot, state, choice)
    if not decision.visible or not decision.enabled:
        raise InvalidChoice(f"choice is unavailable: {choice_id}")
    working = apply_effects(snapshot, state, choice.effects)
    working = _record_choice(working, choice)
    completed_before = state.loop.completed_cycles
    working = _navigate(snapshot, working, node, choice)
    working.validate_against(snapshot)
    target = snapshot.nodes[working.current_node_id]
    if target.meta.terminal is not None:
        status = target.meta.terminal.type
    elif working.loop.completed_cycles > completed_before:
        status = "cycle_complete"
    else:
        status = "active"
    return TransitionResult(state=working, result_blocks=choice.result, choice_id=choice.id, status=status)
```

- [ ] **Step 5: Define exact navigation policies**

```python
def _navigate(snapshot: StorySnapshotV3, state: GameState, node: StoryNodeV3, choice: StoryChoiceV3) -> GameState:
    if choice.next.mode == "stay":
        return state
    if choice.next.mode == "travel":
        return _enter_node(snapshot, state, choice.next.target)
    if choice.next.mode == "warp":
        if not isinstance(node.routing, WarpRoutingV3) or choice.next.target not in node.routing.allowed_targets:
            raise InvalidChoice(f"invalid warp route: {choice.id}")
        return _enter_node(snapshot, apply_effects(snapshot, state, node.routing.exit_effects), choice.next.target)
    if choice.next.mode == "shortcut":
        if not isinstance(node.routing, ShortcutRoutingV3) or choice.next.target != node.routing.exit_node_id:
            raise InvalidChoice(f"invalid shortcut route: {choice.id}")
        return _enter_node(snapshot, apply_effects(snapshot, state, node.routing.counter_effects), choice.next.target)
    raise InvalidChoice(f"unsupported navigation mode: {choice.next.mode}")


def _enter_node(snapshot: StorySnapshotV3, state: GameState, target: str) -> GameState:
    target_node = snapshot.nodes[target]
    visit = VisitState(
        visit_id=state.visit.visit_id + 1,
        node_id=target,
        entry_attributes=dict(state.player.attributes),
    )
    crossing = CrossingState(crossing_id=visit.visit_id, node_id=target) if isinstance(target_node.routing, CrossingRoutingV3) else None
    return state.model_copy(update={"current_node_id": target, "visit": visit, "crossing": crossing})
```

Add this typed effect to `H_choice_09` in `data/story_v3/nodes/H.json`; returning to A by another route, including K warp, does not complete a cycle:

```json
"effects": [
  {
    "type": "modify_counter",
    "counter": "completed_cycles",
    "operation": "add",
    "value": 1
  }
]
```

The reducer emits `cycle_complete` only when this typed effect raises `completed_cycles`. `current_cycle` remains derived and is never persisted separately.

- [ ] **Step 6: Run GREEN**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_navigation.py -q`

Expected: PASS; travel creates a visit, warp applies one configured cost, shortcut applies its configured counter effects, and the first completed loop exposes `current_cycle == 2`.

- [ ] **Step 7: Run focused and full verification**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_navigation.py backend/tests/game/test_effect_reducer.py backend/tests/game/test_condition_availability.py -q`

Expected: PASS.

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests -q -rs`

Expected: the complete backend suite passes.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/game/reducer.py backend/tests/game/support.py backend/tests/game/test_navigation.py data/story_v3/nodes/H.json
git commit -m "feat: add v3 navigation policies"
```

### Task 6: Server-side frame building and explicit run status

**Files:**

- Create: `backend/app/game/frame_builder.py`
- Create: `backend/app/schemas/session.py`
- Create: `backend/tests/game/test_frame_builder.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: Write failing read-only frame tests**

```python
# backend/tests/game/test_frame_builder.py
from app.game.frame_builder import build_turn_view
from app.game.state import initial_game_state
from app.schemas.story_v3 import AttributeCompareCondition
from backend.tests.game.support import state_at_node


def test_frame_contains_versions_cycles_and_structured_locks(published_story):
    state = state_at_node(published_story.snapshot, "H")
    view = build_turn_view(
        published_story.snapshot,
        state,
        session_id="session-1",
        turn_revision=4,
        result_blocks=[],
    )
    locked = next(choice for choice in view.choices if choice.id == "H_choice_01")
    assert view.session_id == "session-1"
    assert view.story_revision == published_story.revision
    assert view.turn_revision == 4
    assert view.completed_cycles == 0
    assert view.current_cycle == 1
    assert locked.available is False
    assert locked.lock_reason.code == "condition_not_met"


def test_nonterminal_without_enabled_exit_is_blocked(published_story):
    snapshot = published_story.snapshot
    impossible = AttributeCompareCondition(type="attribute_compare", attribute="sanity", operator="gt", value=100)
    node = snapshot.nodes["A"]
    choices = [choice.model_copy(update={"availability": choice.availability.model_copy(update={"condition": impossible, "locked_visibility": "hide"})}) for choice in node.choices]
    blocked_snapshot = snapshot.model_copy(update={"nodes": {**snapshot.nodes, "A": node.model_copy(update={"choices": choices})}})
    view = build_turn_view(blocked_snapshot, initial_game_state(blocked_snapshot), session_id="s", turn_revision=0, result_blocks=[])
    assert view.status == "blocked"
```

- [ ] **Step 2: Run RED and confirm the builder is absent**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_frame_builder.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'app.game.frame_builder'`.

- [ ] **Step 3: Define command and read-only response schemas**

```python
# backend/app/schemas/session.py
class LockReasonView(BaseModel):
    code: str
    message: str


class TurnNodeView(BaseModel):
    id: StoryId
    name: str
    scene: SceneV3


class ChooseCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn_revision: int = Field(ge=0)
    choice_id: StoryId


class SaveCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn_revision: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=120)


class ResumeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    save_id: str = Field(min_length=1, max_length=64)


class TurnChoice(BaseModel):
    id: StoryId
    text: str
    short_text: str | None
    available: bool
    lock_reason: LockReasonView | None


class TurnView(BaseModel):
    session_id: str
    story_revision: str
    turn_revision: int
    status: Literal["active", "ending", "cycle_complete", "blocked"]
    node: TurnNodeView
    content: list[ContentBlockV3]
    choices: list[TurnChoice]
    attributes: dict[str, int]
    inventory: dict[str, int]
    completed_cycles: int
    current_cycle: int


class SaveView(BaseModel):
    save_id: str
    name: str
    story_revision: str
    turn_revision: int
```

- [ ] **Step 4: Build content, choices, and status entirely on the server**

```python
# backend/app/game/frame_builder.py
def build_turn_view(snapshot: StorySnapshotV3, state: GameState, *, session_id: str, turn_revision: int, result_blocks: list[ContentBlockV3], status: RunStatus | None = None) -> TurnView:
    node = snapshot.nodes[state.current_node_id]
    entry_blocks = _select_entry_blocks(node, state)
    choices = []
    for choice in node.choices:
        decision = evaluate_choice(snapshot, state, choice)
        if not decision.visible:
            continue
        choices.append(TurnChoice(
            id=choice.id,
            text=choice.text,
            short_text=choice.short_text,
            available=decision.enabled,
            lock_reason=None if decision.reason is None else LockReasonView.model_validate(decision.reason.model_dump()),
        ))
    resolved_status = _resolve_status(node, choices, status)
    return TurnView(
        session_id=session_id,
        story_revision=snapshot.revision,
        turn_revision=turn_revision,
        status=resolved_status,
        node=TurnNodeView(id=node.id, name=node.meta.name, scene=node.scene),
        content=[*result_blocks, *entry_blocks],
        choices=choices,
        attributes=dict(state.player.attributes),
        inventory=dict(state.player.inventory),
        completed_cycles=state.loop.completed_cycles,
        current_cycle=state.current_cycle,
    )


def _resolve_status(node: StoryNodeV3, choices: list[TurnChoice], requested: RunStatus | None) -> RunStatus:
    if requested in {"ending", "cycle_complete"}:
        return requested
    if node.meta.terminal is not None:
        return node.meta.terminal.type
    if not any(choice.available for choice in choices):
        return "blocked"
    return "active"
```

- [ ] **Step 5: Run GREEN**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_frame_builder.py -q`

Expected: PASS; status is one of `active`, `ending`, `cycle_complete`, or `blocked`, and no authoritative `GameState` appears in the response schema.

- [ ] **Step 6: Run focused and full verification**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_frame_builder.py backend/tests/game/test_condition_availability.py backend/tests/game/test_navigation.py -q`

Expected: PASS.

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests -q -rs`

Expected: the complete backend suite passes.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/game/frame_builder.py backend/app/schemas/session.py backend/app/schemas/__init__.py backend/tests/game/test_frame_builder.py
git commit -m "feat: build authoritative turn views"
```

### Task 7: Session create/get/choose API

**Files:**

- Create: `backend/app/game/turn_service.py`
- Create: `backend/app/routers/sessions.py`
- Create: `backend/tests/api/test_sessions_api.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/__init__.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Write failing API contract and replay tests**

```python
# backend/tests/api/test_sessions_api.py
def test_create_get_and_choose_accept_only_command_fields(session_client):
    created = session_client.post("/api/sessions", json={})
    assert created.status_code == 201
    turn = created.json()
    assert set(turn) >= {"session_id", "story_revision", "turn_revision", "status", "node", "choices"}
    assert "state" not in turn

    forged = session_client.post(
        f"/api/sessions/{turn['session_id']}/choose",
        json={"turn_revision": 0, "choice_id": "A_choice_01", "current_node_id": "K", "inventory": {"item_coin": 99}},
    )
    assert forged.status_code == 422

    chosen = session_client.post(
        f"/api/sessions/{turn['session_id']}/choose",
        json={"turn_revision": 0, "choice_id": "A_choice_01"},
    )
    assert chosen.status_code == 200
    assert chosen.json()["turn_revision"] == 1

    replay = session_client.post(
        f"/api/sessions/{turn['session_id']}/choose",
        json={"turn_revision": 0, "choice_id": "A_choice_01"},
    )
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == "stale_turn_revision"
```

- [ ] **Step 2: Run RED and confirm routes return 404**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/api/test_sessions_api.py -q`

Expected: FAIL because `POST /api/sessions` returns `404 Not Found`.

- [ ] **Step 3: Add an API client bound to the temporary database and build root**

```python
# backend/tests/conftest.py
@pytest.fixture
def session_client(isolated_db_session, published_story):
    test_app = FastAPI()
    test_app.include_router(sessions.router)
    service = TurnService(SessionRepository(isolated_db_session), StoryPublisher(published_story.build_root))
    test_app.dependency_overrides[sessions.get_turn_service] = lambda: service
    with TestClient(test_app) as client:
        yield client
```

- [ ] **Step 4: Implement the revision-pinned service**

```python
# backend/app/game/turn_service.py
class TurnService:
    def __init__(self, repository: SessionRepository, publisher: StoryPublisher):
        self.repository = repository
        self.publisher = publisher

    def create_session(self) -> TurnView:
        snapshot = self.publisher.load_active()
        state = initial_game_state(snapshot)
        preview = build_turn_view(snapshot, state, session_id="pending", turn_revision=0, result_blocks=[], status="active")
        record = self.repository.create(state, story_revision=snapshot.revision, status=preview.status)
        return build_turn_view(snapshot, state, session_id=record.id, turn_revision=0, result_blocks=[], status=record.status)

    def get_session(self, session_id: str) -> TurnView:
        record = self.repository.get(session_id)
        snapshot = self.publisher.load_revision(record.story_revision)
        return build_turn_view(snapshot, record.state, session_id=record.id, turn_revision=record.turn_revision, result_blocks=[], status=record.status)

    def choose(self, session_id: str, command: ChooseCommand) -> TurnView:
        record = self.repository.get(session_id)
        if record.turn_revision != command.turn_revision:
            raise StaleTurnRevision(command.turn_revision, record.turn_revision)
        snapshot = self.publisher.load_revision(record.story_revision)
        transition = reduce_choice(snapshot, record.state, command.choice_id)
        preview = build_turn_view(snapshot, transition.state, session_id=record.id, turn_revision=record.turn_revision + 1, result_blocks=transition.result_blocks, status=transition.status)
        committed = self.repository.commit_turn(record.id, expected_revision=command.turn_revision, state=transition.state, status=preview.status, choice_id=command.choice_id)
        return preview.model_copy(update={"turn_revision": committed.turn_revision})
```

- [ ] **Step 5: Add transport-only routes and stable error mapping**

```python
# backend/app/routers/sessions.py
router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def get_turn_service(db: Session = Depends(get_db)) -> TurnService:
    return TurnService(SessionRepository(db), StoryPublisher(STORY_BUILD_DIR))


@router.post("", response_model=TurnView, status_code=201)
def create_session(service: TurnService = Depends(get_turn_service)):
    return service.create_session()


@router.get("/{session_id}", response_model=TurnView)
def get_session(session_id: str, service: TurnService = Depends(get_turn_service)):
    return service.get_session(session_id)


@router.post("/{session_id}/choose", response_model=TurnView)
def choose(session_id: str, command: ChooseCommand, service: TurnService = Depends(get_turn_service)):
    try:
        return service.choose(session_id, command)
    except StaleTurnRevision as exc:
        raise HTTPException(status_code=409, detail={"code": "stale_turn_revision", "expected": exc.expected, "actual": exc.actual}) from exc
```

- [ ] **Step 6: Run GREEN**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/api/test_sessions_api.py -q`

Expected: PASS; forged state fields receive 422, the first command increments revision once, and replay receives 409 without another audit or effect.

- [ ] **Step 7: Run focused and full verification**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/api/test_sessions_api.py backend/tests/game/test_session_repository.py backend/tests/game/test_effect_reducer.py -q`

Expected: PASS.

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests -q -rs`

Expected: the complete backend suite passes while the old `/api/game` routes still exist.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/game/turn_service.py backend/app/routers/sessions.py backend/app/main.py backend/app/routers/__init__.py backend/tests/api/test_sessions_api.py backend/tests/conftest.py
git commit -m "feat: add authoritative session API"
```

### Task 8: Story-revision-bound save and resume

**Files:**

- Modify: `backend/app/game/session_repository.py`
- Modify: `backend/app/game/turn_service.py`
- Modify: `backend/app/routers/sessions.py`
- Modify: `backend/app/schemas/session.py`
- Create: `backend/tests/api/test_session_saves.py`
- Create: `backend/tests/game/test_session_restart.py`

- [ ] **Step 1: Write failing save, clean-database, and restart tests**

```python
# backend/tests/api/test_session_saves.py
def test_save_and_resume_are_bound_to_story_revision(session_client):
    turn = session_client.post("/api/sessions", json={}).json()
    saved = session_client.post(
        f"/api/sessions/{turn['session_id']}/saves",
        json={"turn_revision": turn["turn_revision"], "name": "checkpoint"},
    )
    assert saved.status_code == 201
    assert saved.json()["story_revision"] == turn["story_revision"]

    resumed = session_client.post("/api/sessions/resume", json={"save_id": saved.json()["save_id"]})
    assert resumed.status_code == 201
    assert resumed.json()["session_id"] != turn["session_id"]
    assert resumed.json()["story_revision"] == turn["story_revision"]


def test_save_rejects_stale_turn_revision(session_client):
    turn = session_client.post("/api/sessions", json={}).json()
    session_client.post(f"/api/sessions/{turn['session_id']}/choose", json={"turn_revision": 0, "choice_id": "A_choice_01"})
    response = session_client.post(f"/api/sessions/{turn['session_id']}/saves", json={"turn_revision": 0, "name": "stale"})
    assert response.status_code == 409
```

```python
# backend/tests/game/test_session_restart.py
def test_service_restart_recovers_session(tmp_path, published_story):
    database_path = tmp_path / "restart.db"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    init_db(bind=engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    first = factory()
    created = TurnService(SessionRepository(first), StoryPublisher(published_story.build_root)).create_session()
    first.close()

    second = factory()
    recovered = TurnService(SessionRepository(second), StoryPublisher(published_story.build_root)).get_session(created.session_id)
    assert recovered.model_dump() == created.model_dump()
    second.close()
    engine.dispose()
```

- [ ] **Step 2: Run RED and confirm save endpoints are missing**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/api/test_session_saves.py backend/tests/game/test_session_restart.py -q`

Expected: FAIL because `POST /api/sessions/{session_id}/saves` and `POST /api/sessions/resume` return 404.

- [ ] **Step 3: Persist immutable save snapshots from server state only**

```python
# backend/app/game/session_repository.py
def create_save(self, session_id: str, *, expected_revision: int, name: str) -> SaveRecord:
    session = self.get(session_id)
    if session.turn_revision != expected_revision:
        raise StaleTurnRevision(expected_revision, session.turn_revision)
    row = GameSave(
        id=uuid4().hex,
        name=name,
        story_revision=session.story_revision,
        source_turn_revision=session.turn_revision,
        current_node_id=session.state.current_node_id,
        status=session.status,
        state_json=_encode_state(session.state),
        created_at=_utcnow(),
    )
    self.db.add(row)
    self.db.commit()
    return SaveRecord.from_row(row)


def resume_save(self, save_id: str) -> SessionRecord:
    save = self.db.get(GameSave, save_id)
    if save is None:
        raise SaveNotFound(save_id)
    return self.create(_decode_state(save.state_json), story_revision=save.story_revision, status=save.status)
```

- [ ] **Step 4: Add revision verification and save/resume routes**

```python
# backend/app/game/turn_service.py
def save(self, session_id: str, command: SaveCommand) -> SaveView:
    record = self.repository.get(session_id)
    self.publisher.load_revision(record.story_revision)
    saved = self.repository.create_save(session_id, expected_revision=command.turn_revision, name=command.name)
    return SaveView(save_id=saved.id, name=saved.name, story_revision=saved.story_revision, turn_revision=saved.source_turn_revision)


def resume(self, command: ResumeCommand) -> TurnView:
    record = self.repository.resume_save(command.save_id)
    snapshot = self.publisher.load_revision(record.story_revision)
    return build_turn_view(snapshot, record.state, session_id=record.id, turn_revision=record.turn_revision, result_blocks=[], status=record.status)
```

```python
# backend/app/routers/sessions.py
@router.post("/{session_id}/saves", response_model=SaveView, status_code=201)
def save_session(session_id: str, command: SaveCommand, service: TurnService = Depends(get_turn_service)):
    return service.save(session_id, command)


@router.post("/resume", response_model=TurnView, status_code=201)
def resume_session(command: ResumeCommand, service: TurnService = Depends(get_turn_service)):
    return service.resume(command)
```

Map a missing bound snapshot to HTTP 410 with `detail.code == "story_revision_unavailable"`; never load the active revision in place of the save's revision.

- [ ] **Step 5: Run GREEN**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/api/test_session_saves.py backend/tests/game/test_session_restart.py -q`

Expected: PASS; an empty temporary database supports create/save/resume, and a new service instance recovers the same session from SQLite.

- [ ] **Step 6: Run focused and full verification**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/api/test_sessions_api.py backend/tests/api/test_session_saves.py backend/tests/game/test_session_restart.py backend/tests/test_clean_database.py -q`

Expected: PASS.

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests -q -rs`

Expected: the complete backend suite passes.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/game/session_repository.py backend/app/game/turn_service.py backend/app/routers/sessions.py backend/app/schemas/session.py backend/tests/api/test_session_saves.py backend/tests/game/test_session_restart.py
git commit -m "feat: save and resume versioned sessions"
```

### Task 9: Known gameplay corrections for K, E, H, S20, and cycle semantics

**Files:**

- Create: `backend/tests/game/test_v3_gameplay_regressions.py`
- Modify: `backend/app/game/reducer.py`
- Modify: `backend/app/game/frame_builder.py`
- Test: `data/story_v3/nodes/D.json`
- Test: `data/story_v3/nodes/E.json`
- Test: `data/story_v3/nodes/H.json`
- Test: `data/story_v3/nodes/K.json`
- Test: `data/story_v3/nodes/S20.json`

- [ ] **Step 1: Write one real-snapshot regression test per known gameplay failure**

```python
# backend/tests/game/test_v3_gameplay_regressions.py
from backend.tests.game.support import state_at_node


def test_k_has_one_authoritative_exit_per_target_with_uniform_cost(published_story):
    snapshot = published_story.snapshot
    state_at_k = state_at_node(snapshot, "K")
    exits = [choice for choice in snapshot.nodes["K"].choices if choice.next.mode == "warp"]
    assert [(choice.id, choice.next.target) for choice in exits] == [(f"K_choice_{index:02d}", target) for index, target in enumerate("ABCDEFGH", start=2)]
    costs = []
    for choice in exits:
        result = reduce_choice(snapshot, state_at_k, choice.id)
        costs.append(state_at_k.player.attributes["sanity_max"] - result.state.player.attributes["sanity_max"])
    assert costs == [1] * 8


def test_e_disables_third_deep_interaction_server_side(published_story):
    snapshot = published_story.snapshot
    state_at_e = state_at_node(snapshot, "E")
    after_one = reduce_choice(snapshot, state_at_e, "E_choice_05").state
    after_two = reduce_choice(snapshot, after_one, "E_choice_06").state
    third = next(choice for choice in snapshot.nodes["E"].choices if choice.id == "E_choice_07")
    decision = evaluate_choice(snapshot, after_two, third)
    assert decision.visible is True
    assert decision.enabled is False
    assert decision.reason.code == "crossing_limit"


def test_h_choice_01_is_reachable_through_d_trust_producer(published_story):
    snapshot = published_story.snapshot
    reachable_d_state = state_at_node(snapshot, "D", completed_cycles=1, attributes={"zhang_trust": 1})
    trusted = reduce_choice(snapshot, reachable_d_state, "D_choice_05").state
    at_h = state_at_node(snapshot, "H", completed_cycles=trusted.loop.completed_cycles, attributes=dict(trusted.player.attributes), flags=dict(trusted.world.flags))
    choice = next(choice for choice in snapshot.nodes["H"].choices if choice.id == "H_choice_01")
    assert evaluate_choice(snapshot, at_h, choice).enabled is True


def test_s20_restores_entry_sanity_only_once_per_cycle(published_story):
    snapshot = published_story.snapshot
    entry_attributes = {**initial_game_state(snapshot).player.attributes, "sanity": 80}
    state_at_s20 = state_at_node(snapshot, "S20", attributes={"sanity": 40}, entry_attributes=entry_attributes)
    first = reduce_choice(snapshot, state_at_s20, "S20_choice_01").state
    assert first.player.attributes["sanity"] == state_at_s20.visit.entry_attributes["sanity"]
    choice = next(choice for choice in snapshot.nodes["S20"].choices if choice.id == "S20_choice_01")
    assert evaluate_choice(snapshot, first, choice).enabled is False


def test_first_second_and_third_cycle_conditions_are_one_based(published_story):
    snapshot = published_story.snapshot
    assert initial_game_state(snapshot).current_cycle == 1
    assert state_at_node(snapshot, "A", completed_cycles=1).current_cycle == 2
    assert state_at_node(snapshot, "A", completed_cycles=2).current_cycle == 3
```

- [ ] **Step 2: Run RED and confirm the E crossing limit is not yet enforced**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_v3_gameplay_regressions.py -q`

Expected: FAIL at `test_e_disables_third_deep_interaction_server_side` because the third deep-interaction choice remains enabled after two interactions.

- [ ] **Step 3: Enforce compiled crossing limits and record the interaction**

```python
# backend/app/game/reducer.py
def _crossing_decision(snapshot: StorySnapshotV3, state: GameState, choice: StoryChoiceV3) -> ChoiceDecision | None:
    node = snapshot.nodes[state.current_node_id]
    if not isinstance(node.routing, CrossingRoutingV3):
        return None
    interaction = next((item for item in node.routing.deep_interactions if item.choice_id == choice.id), None)
    if interaction is None:
        return None
    crossing = state.crossing
    if crossing is None:
        raise ValueError("crossing node requires crossing state")
    if crossing.interaction_count >= node.routing.max_deep_interactions:
        return ChoiceDecision(visible=True, enabled=False, reason=LockReason(code="crossing_limit", message=f"本次穿越最多深入互动 {node.routing.max_deep_interactions} 次"))
    return None


def _record_crossing_choice(snapshot: StorySnapshotV3, state: GameState, choice: StoryChoiceV3) -> GameState:
    node = snapshot.nodes[state.current_node_id]
    if not isinstance(node.routing, CrossingRoutingV3):
        return state
    interaction = next((item for item in node.routing.deep_interactions if item.choice_id == choice.id), None)
    if interaction is None or state.crossing is None:
        return state
    crossing = state.crossing.model_copy(update={
        "interaction_count": state.crossing.interaction_count + 1,
        "interacted_npcs": state.crossing.interacted_npcs | {interaction.npc_id},
    })
    return state.model_copy(update={"crossing": crossing})
```

Call `_crossing_decision()` before the normal availability success return, and call `_record_crossing_choice()` once inside `reduce_choice()` after effects succeed.

- [ ] **Step 4: Keep the canonical v3 corrections explicit and executable**

Assert without rewriting canonical data that:

- `data/story_v3/nodes/K.json` owns exactly `K_choice_02` through `K_choice_09`, each with `next.mode="warp"`, and its `routing.exit_effects` subtract one `sanity_max`.
- `data/story_v3/nodes/E.json` declares `max_deep_interactions=2` and maps `E_choice_05` through `E_choice_10` to six NPC IDs.
- `data/story_v3/nodes/D.json` produces `zhang_trust=3` on a reachable `D_choice_05`, and `data/story_v3/nodes/H.json` consumes that typed attribute for `H_choice_01`.
- `data/story_v3/nodes/S20.json` uses `restore_entry_attribute(sanity)` with `repeat_policy="once_per_cycle"`.
- all authored cycle conditions use `current_cycle`; persisted state stores only `completed_cycles` and `half_cycles`.

- [ ] **Step 5: Run GREEN**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_v3_gameplay_regressions.py -q`

Expected: PASS with five regression tests; K costs are uniform, E's third interaction is disabled, H is reachable, S20 restores once, and cycle display is one-based.

- [ ] **Step 6: Run strict story and runtime verification**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/game/test_v3_gameplay_regressions.py backend/tests/game/test_navigation.py backend/tests/game/test_condition_availability.py backend/tests/test_story_v3_compiler.py backend/tests/test_story_v3_migration.py -q`

Expected: PASS and the strict v3 snapshot compiles from the temporary story copy.

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests -q -rs`

Expected: the complete backend suite passes.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/game/reducer.py backend/app/game/frame_builder.py backend/tests/game/test_v3_gameplay_regressions.py
git commit -m "fix: enforce v3 gameplay semantics"
```

### Task 10: Frontend migration to read-only turn views

**Files:**

- Create: `frontend/src/api/sessions.ts`
- Create: `frontend/src/stores/sessionStore.ts`
- Create: `frontend/tests/sessionStore.test.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/views/GamePlay.vue`
- Modify: `frontend/package.json`

- [ ] **Step 1: Write failing store tests for retained turns and 409 refresh**

```typescript
// frontend/tests/sessionStore.test.ts
import test from 'node:test'
import assert from 'node:assert/strict'
import { createSessionActions } from '../src/stores/sessionStore.ts'
import type { TurnView } from '../src/types/index.ts'

test('ordinary choose failure retains the current turn', async () => {
  const original = { session_id: 's1', turn_revision: 3 } as TurnView
  const state = { currentTurn: original, error: null as string | null }
  const actions = createSessionActions(state, {
    chooseSession: async () => { throw new Error('offline') },
    getSession: async () => { throw new Error('must not refresh') },
  })
  await actions.choose('A_choice_01')
  assert.equal(state.currentTurn, original)
  assert.equal(state.error, 'offline')
})

test('409 refreshes the same session without creating a new game', async () => {
  const original = { session_id: 's1', turn_revision: 3 } as TurnView
  const refreshed = { session_id: 's1', turn_revision: 4 } as TurnView
  const state = { currentTurn: original, error: null as string | null }
  let creates = 0
  const actions = createSessionActions(state, {
    chooseSession: async () => { throw { isAxiosError: true, response: { status: 409 } } },
    getSession: async () => refreshed,
    createSession: async () => { creates += 1; return refreshed },
  })
  await actions.choose('A_choice_01')
  assert.equal(state.currentTurn, refreshed)
  assert.equal(creates, 0)
})
```

- [ ] **Step 2: Run RED and confirm the session store is absent**

Run: `npm run test:unit --prefix frontend`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `frontend/src/stores/sessionStore.ts`.

- [ ] **Step 3: Add a command-only session API**

```typescript
// frontend/src/api/sessions.ts
import axios from 'axios'
import type { SaveView, TurnView } from '@/types'

const api = axios.create({ baseURL: '/api' })

export const createSession = async (): Promise<TurnView> => (await api.post<TurnView>('/sessions', {})).data
export const getSession = async (sessionId: string): Promise<TurnView> => (await api.get<TurnView>(`/sessions/${sessionId}`)).data
export const chooseSession = async (sessionId: string, turnRevision: number, choiceId: string): Promise<TurnView> => (
  await api.post<TurnView>(`/sessions/${sessionId}/choose`, { turn_revision: turnRevision, choice_id: choiceId })
).data
export const saveSession = async (sessionId: string, turnRevision: number, name: string): Promise<SaveView> => (
  await api.post<SaveView>(`/sessions/${sessionId}/saves`, { turn_revision: turnRevision, name })
).data
export const resumeSession = async (saveId: string): Promise<TurnView> => (await api.post<TurnView>('/sessions/resume', { save_id: saveId })).data
```

No function in this file accepts node ID, attributes, flags, inventory, cycle counters, or a complete state object.

- [ ] **Step 4: Store the read-only turn and refresh on conflict**

```typescript
// frontend/src/stores/sessionStore.ts
export function createSessionActions(state: SessionState, api: SessionApi) {
  return {
    async choose(choiceId: string) {
      const current = state.currentTurn
      if (!current) return
      state.error = null
      try {
        state.currentTurn = await api.chooseSession(current.session_id, current.turn_revision, choiceId)
      } catch (error: unknown) {
        if (axios.isAxiosError(error) && error.response?.status === 409) {
          state.currentTurn = await api.getSession(current.session_id)
          state.error = '回合已刷新，请重新选择'
          return
        }
        state.error = error instanceof Error ? error.message : '请求失败'
      }
    },
  }
}


export const useSessionStore = defineStore('session', () => {
  const currentTurn = ref<TurnView | null>(null)
  const error = ref<string | null>(null)
  const loading = ref(false)
  const actions = createSessionActions({
    get currentTurn() { return currentTurn.value },
    set currentTurn(value) { currentTurn.value = value },
    get error() { return error.value },
    set error(value) { error.value = value },
  }, sessionsApi)
  return { currentTurn, error, loading, ...actions }
})
```

- [ ] **Step 5: Migrate `GamePlay.vue` to server choices and statuses**

Replace `useGameStore()` with `useSessionStore()`, render `turn.choices` without `visibleChoices()`, disable buttons when `available === false`, show `lock_reason.message`, render explicit `ending`, `cycle_complete`, and `blocked` panels, and keep the current turn visible beneath a non-blocking error banner. Save sends only `{turn_revision, name}` and resume sends only `{save_id}`.

```vue
<button
  v-for="choice in store.currentTurn?.choices ?? []"
  :key="choice.id"
  class="choice-btn"
  :disabled="!choice.available || store.loading"
  @click="store.choose(choice.id)"
>
  <span class="choice-text">{{ choice.text }}</span>
  <span v-if="choice.lock_reason" class="choice-lock-reason">{{ choice.lock_reason.message }}</span>
</button>
```

- [ ] **Step 6: Run GREEN**

Run: `npm run test:unit --prefix frontend`

Expected: PASS; ordinary errors retain the same object and HTTP 409 refreshes `session_id=s1` without calling `createSession`.

- [ ] **Step 7: Run frontend focused and production verification**

Run: `npm run build --prefix frontend`

Expected: `vue-tsc --noEmit` and `vite build` complete successfully with no client-owned `GameState` argument in the session code.

Run: `rg -n "GameState|resumeGame|currentState|visibleChoices" frontend/src/api/sessions.ts frontend/src/stores/sessionStore.ts frontend/src/views/GamePlay.vue`

Expected: no matches.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/api/sessions.ts frontend/src/stores/sessionStore.ts frontend/tests/sessionStore.test.ts frontend/src/types/index.ts frontend/src/views/GamePlay.vue frontend/package.json
git commit -m "feat: migrate player to session turns"
```

### Task 11: Isolated API and core Playwright journeys

**Files:**

- Modify: `backend/app/paths.py`
- Modify: `backend/app/config.py`
- Modify: `tests/e2e/conftest.py`
- Create: `tests/e2e/test_authoritative_runtime.py`
- Create: `backend/tests/api/test_session_isolation.py`

- [ ] **Step 1: Write failing isolation and browser journey tests**

```python
# backend/tests/api/test_session_isolation.py
def test_session_test_roots_are_temporary(isolated_runtime):
    assert isolated_runtime.database_path.is_relative_to(isolated_runtime.root)
    assert isolated_runtime.story_root.is_relative_to(isolated_runtime.root)
    assert isolated_runtime.build_root.is_relative_to(isolated_runtime.root)
    assert isolated_runtime.story_root != PROJECT_ROOT / "data" / "story_v3"
```

```python
# tests/e2e/test_authoritative_runtime.py
from playwright.sync_api import Page, expect


def test_create_choose_refresh_and_restart_journey(page: Page, runtime_servers):
    page.goto(f"{runtime_servers.frontend_url}/play")
    expect(page.locator("[data-testid=session-id]")).not_to_be_empty()
    session_id = page.locator("[data-testid=session-id]").inner_text()
    page.get_by_role("button", name="直接进入广场办理入住").click()
    expect(page.locator("[data-testid=turn-revision]")).to_have_text("1")

    runtime_servers.restart_backend()
    page.reload()
    expect(page.locator("[data-testid=session-id]")).to_have_text(session_id)


def test_locked_choice_and_stale_click_recovery(page: Page, runtime_servers):
    page.goto(f"{runtime_servers.frontend_url}/play")
    locked = page.locator(".choice-btn:disabled").first
    expect(locked.locator(".choice-lock-reason")).not_to_be_empty()
    runtime_servers.submit_stale_choice_from_api(page)
    page.locator(".choice-btn:not(:disabled)").first.click()
    expect(page.locator(".error-banner")).to_contain_text("回合已刷新")
    expect(page.locator(".game-play")).to_be_visible()
```

- [ ] **Step 2: Run RED and confirm isolated runtime fixtures do not exist**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/api/test_session_isolation.py -q`

Expected: FAIL because fixture `isolated_runtime` is not found.

Run: `backend\venv\Scripts\python.exe -m pytest tests/e2e/test_authoritative_runtime.py -q`

Expected: FAIL because fixture `runtime_servers` is not found.

- [ ] **Step 3: Make all runtime roots configurable before imports construct engines**

```python
# backend/app/paths.py
STORY_V3_DIR = Path(os.environ.get("CYCLE_MASTER_STORY_V3_ROOT", DATA_DIR / "story_v3")).resolve()
STORY_BUILD_DIR = Path(os.environ.get("CYCLE_MASTER_STORY_BUILD_ROOT", DATA_DIR / "story_build")).resolve()
DATABASE_PATH = Path(os.environ.get("CYCLE_MASTER_DATABASE_PATH", DATA_DIR / "cycle_master.db")).resolve()
```

`backend/app/config.py` must import the resolved `DATABASE_PATH` once and construct `DATABASE_URL` from it. Tests set all three environment variables before importing `app.main` in the server subprocess.

- [ ] **Step 4: Build isolated fixtures with temporary copies and dynamic ports**

```python
# tests/e2e/conftest.py
@pytest.fixture(scope="session")
def runtime_servers(tmp_path_factory):
    root = tmp_path_factory.mktemp("authoritative-runtime")
    story_root = root / "story_v3"
    build_root = root / "story_build"
    database_path = root / "cycle_master.db"
    shutil.copytree(PROJECT_ROOT / "data" / "story_v3", story_root)
    subprocess.run([PYTHON, "-m", "backend.scripts.compile_story_v3", "--source", str(story_root), "--build-root", str(build_root), "--strict"], cwd=PROJECT_ROOT, check=True)
    environment = {
        **os.environ,
        "CYCLE_MASTER_DATABASE_PATH": str(database_path),
        "CYCLE_MASTER_STORY_V3_ROOT": str(story_root),
        "CYCLE_MASTER_STORY_BUILD_ROOT": str(build_root),
    }
    servers = RuntimeServers.start(root=root, environment=environment)
    yield servers
    servers.stop()
```

`RuntimeServers.start()` launches hidden backend and frontend subprocesses on reserved loopback ports, polls `/api/health` and the Vite root with a 20-second deadline, exposes `restart_backend()`, and terminates only the PIDs it created. The fixture never points a write-capable process at canonical `data/story_v3`, `data/story_build`, or `data/cycle_master.db`.

- [ ] **Step 5: Run GREEN for isolation and core journeys**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/api/test_session_isolation.py -q`

Expected: PASS and all paths are children of pytest's temporary root.

Run: `backend\venv\Scripts\python.exe -m pytest tests/e2e/test_authoritative_runtime.py -q`

Expected: PASS without fixed sleeps, forced clicks, swallowed exceptions, recursive retries, or writes to canonical story/build/database paths.

- [ ] **Step 6: Run focused verification and confirm canonical data is unchanged**

Run: `git status --short data/story_v3 data/story_build data/cycle_master.db`

Expected: no output.

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/api/test_sessions_api.py backend/tests/api/test_session_saves.py backend/tests/api/test_session_isolation.py tests/e2e/test_authoritative_runtime.py -q`

Expected: PASS.

- [ ] **Step 7: Run full pre-removal gate**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests -q -rs`

Expected: the complete backend suite passes.

Run: `npm run test:unit --prefix frontend`

Expected: the frontend unit suite passes.

Run: `npm run build --prefix frontend`

Expected: TypeScript checking and production build pass.

Run: `backend\venv\Scripts\python.exe -m pytest tests/e2e/test_authoritative_runtime.py -q`

Expected: the authoritative create/choose/conflict/save/restart journeys pass.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/paths.py backend/app/config.py tests/e2e/conftest.py tests/e2e/test_authoritative_runtime.py backend/tests/api/test_session_isolation.py
git commit -m "test: isolate authoritative runtime journeys"
```

### Task 12: Removal of v2 runtime dependencies and final quality gate

**Files:**

- Delete: `backend/app/routers/game.py`
- Delete: `backend/app/routers/saves.py`
- Delete: `backend/app/engine/engine.py`
- Delete: `backend/app/engine/condition_eval.py`
- Delete: `backend/app/engine/graph.py`
- Delete: `backend/app/engine/special_router.py`
- Delete: `backend/app/engine/story_v2_loader.py`
- Delete: `backend/app/engine/turn_store.py`
- Delete: `backend/app/schemas/game.py`
- Delete: `backend/app/models/save.py`
- Delete: `backend/app/models/story.py`
- Delete: `frontend/src/api/game.ts`
- Delete: `frontend/src/stores/gameStore.ts`
- Delete: `frontend/src/player/choiceVisibility.ts`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/__init__.py`
- Modify: `backend/app/schemas/__init__.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/engine/__init__.py`
- Modify: `backend/app/story/v2_migration.py`
- Modify: `backend/tests/conftest.py`
- Delete: `backend/tests/test_turn_store.py`
- Delete: `backend/tests/test_story_v2_runtime.py`
- Delete: `backend/tests/test_engine.py`
- Delete: `backend/tests/test_condition_eval.py`
- Delete: `backend/tests/test_choice_visibility.py`
- Delete: `backend/tests/test_inventory_actions.py`
- Delete: `backend/tests/test_game_api_contract.py`
- Delete: `backend/tests/test_save_regressions.py`
- Delete: `backend/tests/test_clean_database.py`
- Modify: `backend/tests/test_story_v3_migration.py`
- Create: `backend/tests/test_no_v2_runtime.py`

- [ ] **Step 1: Re-run the complete Task 11 gate before deleting anything**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests -q -rs`

Expected: PASS.

Run: `npm run test:unit --prefix frontend`

Expected: PASS.

Run: `npm run build --prefix frontend`

Expected: PASS.

Run: `backend\venv\Scripts\python.exe -m pytest tests/e2e/test_authoritative_runtime.py -q`

Expected: PASS. If any command fails, stop this task before file deletion and repair the new runtime in its owning task.

- [ ] **Step 2: Write the failing no-v2-runtime guard**

```python
# backend/tests/test_no_v2_runtime.py
from pathlib import Path


FORBIDDEN = (
    "StoryV2Loader",
    "TurnStore",
    "/api/game/resume",
    "app.schemas.game import GameState",
    "resumeGame(",
    "currentState",
    "models.story",
)


def test_runtime_source_has_no_v2_authority_paths():
    roots = [Path("backend/app"), Path("frontend/src")]
    text = "\n".join(path.read_text(encoding="utf-8") for root in roots for path in root.rglob("*") if path.suffix in {".py", ".ts", ".vue"})
    assert [token for token in FORBIDDEN if token in text] == []
```

- [ ] **Step 3: Run RED and confirm every legacy authority token is still present**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/test_no_v2_runtime.py -q`

Expected: FAIL and list at least `StoryV2Loader` and `TurnStore`.

- [ ] **Step 4: Decouple the one-time migration from the runtime loader**

```python
# backend/app/story/v2_migration.py
def load_v2_nodes(source: Path) -> list[StoryNodeV2]:
    nodes_root = source / "nodes" if (source / "nodes").is_dir() else source
    return [
        StoryNodeV2.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(nodes_root.glob("*.json"))
    ]
```

Replace `StoryV2Loader().nodes` use in migration tests with `load_v2_nodes(STORY_DATA_V2_DIR)`. This preserves the one-time migration tool without retaining a v2 game runtime.

- [ ] **Step 5: Remove legacy runtime, save-state API, and story-table coupling**

Delete the files listed above, register only `sessions` and `editor` routers in `backend/app/main.py`, import only `GameSession`, `GameSave`, and `ChoiceAudit` for database initialization, and keep v2 authoring/migration schemas only where the one-time migration and current editor still require them. Remove every client path that posts or receives a full authoritative state.

- [ ] **Step 6: Run GREEN for the removal guard**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests/test_no_v2_runtime.py -q`

Expected: PASS with no `StoryV2Loader`, `TurnStore`, client-state resume endpoint, or legacy story ORM import under runtime source roots.

- [ ] **Step 7: Run the final full quality gate**

Run: `backend\venv\Scripts\python.exe -m pytest backend/tests -q -rs`

Expected: the complete retained backend suite passes.

Run: `npm run test:unit --prefix frontend`

Expected: the complete frontend unit suite passes.

Run: `npm run build --prefix frontend`

Expected: `vue-tsc --noEmit` and the production Vite build pass.

Run: `backend\venv\Scripts\python.exe -m backend.scripts.compile_story_v3 --source data/story_v3 --build-root "$env:TEMP\cycle-master-final-build" --strict`

Expected: strict compilation succeeds without writing to canonical `data/story_build`.

Run: `backend\venv\Scripts\python.exe -m pytest tests/e2e/test_authoritative_runtime.py -q`

Expected: the authoritative Playwright journeys pass against temporary database/story/build roots.

Run: `rg -n "StoryV2Loader|TurnStore|/api/game/resume|resumeGame\(|currentState|from app\.models\.story|from \.models\.story" backend/app frontend/src`

Expected: no matches.

Run: `git status --short data/story_v3 data/story_build data/cycle_master.db`

Expected: no output.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 8: Commit**

```powershell
git add -A backend/app backend/tests frontend/src
git commit -m "refactor: remove v2 authoritative runtime"
```

## Final implementation verification checklist

- [ ] `GameSession` and every `GameSave` persist both `story_revision` and `turn_revision` provenance.
- [ ] The client sends only command IDs plus `turn_revision`; full authoritative state is rejected by closed request schemas.
- [ ] A stale revision returns HTTP 409, leaves the prior turn intact, and cannot double-apply effects or create a second audit row.
- [ ] Every transition works on a deep copy and commits only after effects, navigation, invariants, and frame construction succeed.
- [ ] Runtime condition, effect, availability, and navigation execution consumes typed values from a verified `StorySnapshotV3` revision.
- [ ] `locked_visibility=hide` omits a locked choice; `locked_visibility=show` includes a disabled choice with `{code, message}`.
- [ ] `travel`, `warp`, and `shortcut` each execute the policy defined in Task 5.
- [ ] Only `completed_cycles` is persisted for full cycles; `current_cycle` is derived as `completed_cycles + 1`.
- [ ] K exits have a single source and uniform configured cost; E permits two deep interactions; H_choice_01 is reachable; S20 restores once per cycle scope.
- [ ] Every turn reports `active`, `ending`, `cycle_complete`, or `blocked` explicitly.
- [ ] Saves load their bound story revision, work in a clean database, and recover after a service restart.
- [ ] The frontend retains the current turn on ordinary errors and refreshes the same session on HTTP 409.
- [ ] Backend, API, and Playwright tests use temporary database/story/build roots and do not mutate canonical data.
- [ ] `StoryV2Loader`, `TurnStore`, client-state resume, and legacy story-table runtime coupling are removed only after the Task 11 gate passes.

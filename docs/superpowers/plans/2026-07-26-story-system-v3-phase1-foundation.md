# Story System v3 Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the strict v3 authoring contract, compiler, immutable snapshot publisher, safe story repository, clean-install database foundation, and deterministic migration of all 30 existing story nodes.

**Architecture:** Human-authored node-per-file JSON is validated by closed Pydantic models and compiled into a content-addressed immutable snapshot. Runtime code continues to use v2 during this phase, but v3 compilation becomes an independent quality gate and all persistence no longer depends on database-backed story rows.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2.10, SQLAlchemy 2.0, SQLite, pytest 9, JSON, SHA-256.

## Global Constraints

- Preserve the existing Vue 3 + FastAPI modular-monolith architecture.
- Do not add a v2/v3 runtime compatibility abstraction; Phase 1 may run the old runtime while the new compiler is built beside it.
- Do not preserve existing save files or database contents; `data/cycle_master.db` is disposable test data.
- Keep one authored JSON file per node under `data/story_v3/nodes/`.
- Pydantic v3 models are the single executable Schema authority; `schema_version` is required and exactly `3`.
- Reject every undeclared JSON field.
- Node and choice IDs must match `^[A-Za-z][A-Za-z0-9_-]{0,63}$`; Windows device names are also invalid.
- The order of `choices` in a node is the display order; v3 has no choice `priority`.
- Conditions and effects are typed discriminated unions; executable condition strings are forbidden in v3 data.
- The compiler must never write into the authoring source directory.
- Publishing may activate a revision only after complete validation and must switch revisions atomically.
- Every production behavior change follows RED → GREEN → REFACTOR.
- Every test that writes story data uses a temporary story root.
- Every database test uses a temporary SQLite database.

---

## File Structure

### New backend modules

- `backend/app/story/__init__.py` — public exports for compilation and publishing.
- `backend/app/story/identifiers.py` — ID validation and safe path resolution.
- `backend/app/story/diagnostics.py` — stable compiler diagnostic types.
- `backend/app/story/compiler.py` — whole-project validation, graph analysis, hashing, and snapshot construction.
- `backend/app/story/publisher.py` — immutable revision directory writer and atomic active-pointer switch.
- `backend/app/story/v2_migration.py` — pure v2-to-v3 conversion functions.
- `backend/app/schemas/story_v3.py` — closed v3 authoring and runtime snapshot contracts.
- `backend/scripts/migrate_story_v3.py` — deterministic migration CLI.
- `backend/scripts/compile_story_v3.py` — strict compile/publish CLI.
- `backend/scripts/export_story_v3_schema.py` — generated JSON Schema exporter.

### New tests

- `backend/tests/test_story_identifiers.py`
- `backend/tests/test_story_v3_schema.py`
- `backend/tests/test_story_v3_migration.py`
- `backend/tests/test_story_v3_compiler.py`
- `backend/tests/test_story_v3_publisher.py`
- `backend/tests/test_clean_database.py`

### Modified backend files

- `backend/app/editor/story_repository.py` — apply shared ID/path guard to the still-active v2 editor.
- `backend/app/models/save.py` — remove foreign keys to legacy story content tables.
- `backend/app/database.py` — make initialization independent from story seed rows.
- `backend/app/paths.py` — add authoring and build roots for v3.
- `backend/tests/conftest.py` — expose an isolated engine/session factory without story seed data.
- `backend/tests/test_story_v2_editor.py` — retain v2 editor security regression coverage.
- `backend/tests/test_save_regressions.py` — prove clean-database save behavior.

### Generated and authored data

- `data/story_v3/project.json`
- `data/story_v3/assets.json`
- `data/story_v3/story-node-v3.schema.json`
- `data/story_v3/nodes/A.json`
- `data/story_v3/nodes/B.json`
- `data/story_v3/nodes/C.json`
- `data/story_v3/nodes/D.json`
- `data/story_v3/nodes/E.json`
- `data/story_v3/nodes/F.json`
- `data/story_v3/nodes/G.json`
- `data/story_v3/nodes/H.json`
- `data/story_v3/nodes/J.json`
- `data/story_v3/nodes/K.json`
- `data/story_v3/nodes/S1.json`
- `data/story_v3/nodes/S2.json`
- `data/story_v3/nodes/S3.json`
- `data/story_v3/nodes/S4.json`
- `data/story_v3/nodes/S5.json`
- `data/story_v3/nodes/S6.json`
- `data/story_v3/nodes/S7.json`
- `data/story_v3/nodes/S8.json`
- `data/story_v3/nodes/S9.json`
- `data/story_v3/nodes/S10.json`
- `data/story_v3/nodes/S11.json`
- `data/story_v3/nodes/S12.json`
- `data/story_v3/nodes/S13.json`
- `data/story_v3/nodes/S14.json`
- `data/story_v3/nodes/S15.json`
- `data/story_v3/nodes/S16.json`
- `data/story_v3/nodes/S17.json`
- `data/story_v3/nodes/S18.json`
- `data/story_v3/nodes/S19.json`
- `data/story_v3/nodes/S20.json`

### Project metadata

- `.gitignore` — ignore `data/story_build/`, the generated runtime build root.
- `README.md` — document v3 migration, schema export, compile, and verification commands.

---

### Task 1: Block unsafe story identifiers and path traversal

**Files:**

- Create: `backend/app/story/__init__.py`
- Create: `backend/app/story/identifiers.py`
- Create: `backend/tests/test_story_identifiers.py`
- Modify: `backend/app/editor/story_repository.py`
- Modify: `backend/tests/test_story_v2_editor.py`

**Interfaces:**

- Produces: `validate_story_id(value: str, *, kind: str = "story") -> str`
- Produces: `resolve_node_path(root: Path, node_id: str) -> Path`
- Consumes: `StoryV2Editor.root`

- [ ] **Step 1: Write failing ID and directory-escape tests**

```python
@pytest.mark.parametrize(
    "node_id",
    [
        "../manifest",
        r"..\manifest",
        "/tmp/node",
        r"C:\temp\node",
        "A/B",
        "A.json",
        "CON",
        "nul",
    ],
)
def test_story_id_rejects_paths_and_windows_devices(node_id):
    with pytest.raises(ValueError, match="invalid story id"):
        validate_story_id(node_id, kind="node")


def test_v2_editor_cannot_write_outside_node_root(tmp_path):
    root = tmp_path / "nodes"
    root.mkdir()
    write_node(root, "A", "A")
    editor = StoryV2Editor(root)

    with pytest.raises(ValueError, match="invalid story id"):
        editor.save_node({"id": "../manifest", "name": "escape"})

    assert not (tmp_path / "manifest.json").exists()
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_identifiers.py backend/tests/test_story_v2_editor.py -q
```

Expected: the new identifier module is missing, or the editor creates `manifest.json` outside `nodes`; the new regression must not pass before the guard exists.

- [ ] **Step 3: Implement strict validation and safe resolution**

```python
STORY_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
WINDOWS_DEVICE_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def validate_story_id(value: str, *, kind: str = "story") -> str:
    candidate = value.strip()
    if (
        not STORY_ID_RE.fullmatch(candidate)
        or candidate.upper() in WINDOWS_DEVICE_NAMES
    ):
        raise ValueError(f"invalid story id for {kind}: {value!r}")
    return candidate


def resolve_node_path(root: Path, node_id: str) -> Path:
    safe_id = validate_story_id(node_id, kind="node")
    resolved_root = root.resolve()
    target = (resolved_root / f"{safe_id}.json").resolve()
    if target.parent != resolved_root:
        raise ValueError(f"node path escapes story root: {node_id!r}")
    return target
```

Call `validate_story_id` before every create, update, or delete lookup in `StoryV2Editor`. New node paths must be produced only by `resolve_node_path`.

- [ ] **Step 4: Run focused and complete backend tests**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_identifiers.py backend/tests/test_story_v2_editor.py -q
backend\venv\Scripts\python.exe -m pytest backend/tests -q
```

Expected: all tests pass, and no file is created outside a temporary node root.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/story backend/app/editor/story_repository.py backend/tests/test_story_identifiers.py backend/tests/test_story_v2_editor.py
git commit -m "fix(editor): prevent story path traversal"
```

---

### Task 2: Define the closed v3 authoring contract

**Files:**

- Create: `backend/app/schemas/story_v3.py`
- Create: `backend/tests/test_story_v3_schema.py`

**Interfaces:**

- Produces: `StoryProjectV3`, `AssetCatalogV3`, `StoryNodeV3`
- Produces: `ConditionV3`, `StoryEffectV3`, `ContentBlockV3`, `StoryChoiceV3`
- Produces: `StorySnapshotV3`
- Consumes: `validate_story_id`

- [ ] **Step 1: Write failing schema contract tests**

Cover all of these behaviors as separate tests:

```python
def test_schema_version_is_required():
    payload = make_node_v3()
    payload.pop("schema_version")
    with pytest.raises(ValidationError, match="schema_version"):
        StoryNodeV3.model_validate(payload)


def test_unknown_fields_are_rejected():
    payload = make_node_v3()
    payload["routing"]["fake_runtime_option"] = True
    with pytest.raises(ValidationError, match="extra"):
        StoryNodeV3.model_validate(payload)


def test_choice_order_is_array_order():
    node = StoryNodeV3.model_validate(make_node_v3(choice_ids=["later", "first"]))
    assert [choice.id for choice in node.choices] == ["later", "first"]
    assert all("priority" not in choice.model_dump() for choice in node.choices)


def test_condition_and_effect_require_known_discriminator():
    payload = make_node_v3()
    payload["choices"][0]["availability"]["condition"] = {"type": "python", "code": "True"}
    with pytest.raises(ValidationError):
        StoryNodeV3.model_validate(payload)


def test_stay_must_target_owner():
    payload = make_node_v3()
    payload["choices"][0]["next"] = {"target": "B", "mode": "stay"}
    with pytest.raises(ValidationError, match="stay"):
        StoryNodeV3.model_validate(payload)
```

Also test dialogue speaker requirements, unique node-local block IDs, explicit `allow_no_background`, typed routing variants, and v3 rejection of string conditions.

- [ ] **Step 2: Run the schema test and verify RED**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_schema.py -q
```

Expected: import failure for `app.schemas.story_v3`.

- [ ] **Step 3: Implement the v3 Pydantic models**

Use `ConfigDict(extra="forbid")` for every model. Define recursive conditions with discriminated `type` fields:

```python
StoryId = Annotated[str, AfterValidator(validate_story_id)]
CompareOperator = Literal["lt", "lte", "eq", "ne", "gte", "gt"]


class AttributeCompareCondition(StrictV3Model):
    type: Literal["attribute_compare"]
    attribute: StoryId
    operator: CompareOperator
    value: int


class FlagEqualsCondition(StrictV3Model):
    type: Literal["flag_equals"]
    flag: StoryId
    value: bool | int | str


class ItemCondition(StrictV3Model):
    type: Literal["item"]
    item_id: StoryId
    present: bool = True


class CounterCompareCondition(StrictV3Model):
    type: Literal["counter_compare"]
    counter: Literal["completed_cycles", "current_cycle", "half_cycles"]
    operator: CompareOperator
    value: int = Field(ge=0)


class AtNodeCondition(StrictV3Model):
    type: Literal["at_node"]
    node_id: StoryId


class AllCondition(StrictV3Model):
    type: Literal["all"]
    conditions: list["ConditionV3"] = Field(min_length=1)


class AnyCondition(StrictV3Model):
    type: Literal["any"]
    conditions: list["ConditionV3"] = Field(min_length=1)


class NotCondition(StrictV3Model):
    type: Literal["not"]
    condition: "ConditionV3"
```

Define effects with distinct shapes:

```python
class ModifyAttributeEffect(StrictV3Model):
    type: Literal["modify_attribute"]
    attribute: StoryId
    operation: Literal["add", "set"]
    value: int
    clamp: bool = True


class SetFlagEffect(StrictV3Model):
    type: Literal["set_flag"]
    flag: StoryId
    value: bool | int | str


class InventoryEffect(StrictV3Model):
    type: Literal["inventory"]
    item_id: StoryId
    operation: Literal["add", "remove"]
    quantity: int = Field(default=1, ge=1)


class PersistNodeItemEffect(StrictV3Model):
    type: Literal["persist_node_item"]
    node_id: StoryId
    item_id: StoryId


class RecordInteractionEffect(StrictV3Model):
    type: Literal["record_interaction"]
    group: StoryId
    subject_id: StoryId


class ModifyCounterEffect(StrictV3Model):
    type: Literal["modify_counter"]
    counter: Literal["completed_cycles", "half_cycles"]
    operation: Literal["add", "set"]
    value: int


class MarkOnceEffect(StrictV3Model):
    type: Literal["mark_once"]
    key: StoryId
    scope: Literal["visit", "cycle", "session"]


class RestoreEntryAttributeEffect(StrictV3Model):
    type: Literal["restore_entry_attribute"]
    attribute: StoryId
```

Define routing as one closed discriminated union:

```python
class CrossingInteractionV3(StrictV3Model):
    choice_id: StoryId
    npc_id: StoryId


class CrossingRoutingV3(StrictV3Model):
    type: Literal["crossing"]
    trigger_time: str
    target_era: StoryId
    max_deep_interactions: int = Field(ge=1)
    deep_interactions: list[CrossingInteractionV3] = Field(min_length=1)
    duration_note: str | None = None
    return_note: str | None = None


class ShortcutRoutingV3(StrictV3Model):
    type: Literal["shortcut"]
    entry_condition: ConditionV3
    entry_node_id: StoryId
    exit_node_id: StoryId
    counter_effects: list[StoryEffectV3] = Field(default_factory=list)


class WarpRoutingV3(StrictV3Model):
    type: Literal["warp"]
    entry_condition: ConditionV3
    allowed_targets: list[StoryId] = Field(min_length=1)
    exit_effects: list[StoryEffectV3] = Field(min_length=1)
    sacrifice_target: StoryId | None = None
```

Define project registries with closed values:

```python
class AttributeDefinitionV3(StrictV3Model):
    display_name: str
    default: int
    minimum: int
    maximum: int


class FlagDefinitionV3(StrictV3Model):
    display_name: str
    default: bool | int | str


class ItemDefinitionV3(StrictV3Model):
    display_name: str
    discardable: bool = False
    cross_surface: bool = False


class NpcDefinitionV3(StrictV3Model):
    display_name: str


class StoryProjectV3(StrictV3Model):
    schema_version: Literal[3]
    entry_node_id: StoryId
    attributes: dict[StoryId, AttributeDefinitionV3]
    flags: dict[StoryId, FlagDefinitionV3]
    items: dict[StoryId, ItemDefinitionV3]
    npcs: dict[StoryId, NpcDefinitionV3]
    counters: list[Literal["completed_cycles", "half_cycles"]]
    jump_modes: list[Literal["stay", "travel", "shortcut", "warp"]]
```

Assets and scenes use logical IDs rather than browser URLs:

```python
class AssetDefinitionV3(StrictV3Model):
    kind: Literal["background", "audio", "sprite"]
    path: str


class AssetCatalogV3(StrictV3Model):
    schema_version: Literal[3]
    assets: dict[StoryId, AssetDefinitionV3]


class SceneV3(StrictV3Model):
    background_id: StoryId | None = None
    allow_no_background: bool
    ambient_id: StoryId | None = None
    palette: str | None = None
    atmosphere: list[str] = Field(default_factory=list)
```

Node metadata carries an explicit terminal state:

```python
class TerminalSpecV3(StrictV3Model):
    type: Literal["ending", "cycle_complete"]
    ending_id: StoryId | None = None
```

`StoryChoiceV3` contains `availability`, `repeat_policy`, ordered `result`, `effects`, and `next: {target, mode}`. `EntrySequenceV3` also uses list order as precedence and has no numeric priority.

Preserve non-runtime authoring information through explicit fields:

```python
class SceneItemNoteV3(StrictV3Model):
    item_id: StoryId
    location: str
    acquisition_note: str | None = None


class NpcItemNoteV3(StrictV3Model):
    npc_id: StoryId
    item_id: StoryId
    required_flag: StoryId | None = None


class GenderVariantNoteV3(StrictV3Model):
    male: str
    female: str


class AuthoringV3(StrictV3Model):
    trigger_description: str | None = None
    npcs_present: list[StoryId] = Field(default_factory=list)
    scene_items: list[SceneItemNoteV3] = Field(default_factory=list)
    npc_item_notes: list[NpcItemNoteV3] = Field(default_factory=list)
    sensory: str | None = None
    gender_variant: GenderVariantNoteV3 | None = None
    notes: list[str] = Field(default_factory=list)
```

The immutable snapshot interface is:

```python
class StorySnapshotV3(StrictV3Model):
    schema_version: Literal[3]
    revision: str
    project: StoryProjectV3
    assets: AssetCatalogV3
    nodes: dict[StoryId, StoryNodeV3]
```

- [ ] **Step 4: Run schema tests and the existing suite**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_schema.py -q
backend\venv\Scripts\python.exe -m pytest backend/tests -q
```

Expected: all tests pass; existing v2 imports still work.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/schemas/story_v3.py backend/tests/test_story_v3_schema.py
git commit -m "feat(story): define strict v3 authoring schema"
```

---

### Task 3: Build deterministic v2 condition and effect migration

**Files:**

- Create: `backend/app/story/v2_migration.py`
- Create: `backend/tests/test_story_v3_migration.py`

**Interfaces:**

- Produces: `parse_v2_condition(expression: str | None) -> ConditionV3 | None`
- Produces: `migrate_v2_effect(effect: StoryEffectV2, *, node_id: str, choice_id: str) -> StoryEffectV3`
- Produces: `migrate_v2_node(node: StoryNodeV2) -> StoryNodeV3`
- Consumes: v2 and v3 Pydantic models

- [ ] **Step 1: Write failing parser tests for every current syntax family**

```python
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("cycle==1", {"type": "counter_compare", "counter": "current_cycle", "operator": "eq", "value": 1}),
        ("half_cycle>=2", {"type": "counter_compare", "counter": "half_cycles", "operator": "gte", "value": 2}),
        ("has_item:item_beads", {"type": "item", "item_id": "item_beads", "present": True}),
        ("not:has_item:item_beads", {"type": "not", "condition": {"type": "item", "item_id": "item_beads", "present": True}}),
        ("has_flag:river_crossed", {"type": "flag_equals", "flag": "river_crossed", "value": True}),
        ("attr:courage>=8", {"type": "attribute_compare", "attribute": "courage", "operator": "gte", "value": 8}),
        ("at_node:E", {"type": "at_node", "node_id": "E"}),
    ],
)
def test_parse_v2_atomic_condition(source, expected):
    assert parse_v2_condition(source).model_dump() == expected


def test_parse_nested_v2_condition():
    condition = parse_v2_condition(
        "or:has_flag:taoist_chant,(and:attr:courage>=8,cycle>=3)"
    )
    assert condition.type == "any"
    assert condition.conditions[1].type == "all"
```

Add a parametrized test that loads every non-null condition from all 30 v2 nodes and proves it parses.

- [ ] **Step 2: Run migration tests and verify RED**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_migration.py -q
```

Expected: import failure for `app.story.v2_migration`.

- [ ] **Step 3: Implement the recursive parser and effect conversion**

Reuse the balanced top-level comma algorithm, but return v3 models rather than evaluating strings. Map comparison symbols explicitly:

```python
OPERATOR_MAP = {
    "<": "lt",
    "<=": "lte",
    "==": "eq",
    "!=": "ne",
    ">=": "gte",
    ">": "gt",
}
```

Map effects as follows:

```python
if source.type == "add_item":
    return InventoryEffect(
        type="inventory",
        item_id=source.target,
        operation="add",
        quantity=int(source.value),
    )
if source.type == "remove_item":
    return InventoryEffect(
        type="inventory",
        item_id=source.target,
        operation="remove",
        quantity=int(source.value),
    )
if source.type in {"heal", "damage"}:
    signed = int(source.value) * (1 if source.type == "heal" else -1)
    return ModifyAttributeEffect(
        type="modify_attribute",
        attribute=source.target,
        operation="add",
        value=signed,
    )
if source.type == "set_flag" and source.target == "zhang_trust":
    return ModifyAttributeEffect(
        type="modify_attribute",
        attribute="zhang_trust",
        operation="set",
        value=int(source.value),
    )
```

Reject unknown effect types. Convert all content-block `when` values and all entry/choice conditions. Sort v2 choices by `(priority, id)` once during migration, then omit `priority`.

- [ ] **Step 4: Verify parser coverage and deterministic node conversion**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_migration.py -q
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_schema.py backend/tests/test_story_v3_migration.py -q
```

Expected: every current condition and effect converts without falling back to a free-form string.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/story/v2_migration.py backend/tests/test_story_v3_migration.py
git commit -m "feat(story): add typed v2 to v3 migration"
```

---

### Task 4: Implement whole-project compilation and diagnostics

**Files:**

- Create: `backend/app/story/diagnostics.py`
- Create: `backend/app/story/compiler.py`
- Create: `backend/tests/test_story_v3_compiler.py`
- Modify: `backend/app/story/__init__.py`

**Interfaces:**

- Produces: `DiagnosticSeverity = Literal["error", "warning", "info"]`
- Produces: immutable `StoryDiagnostic(code, severity, message, location)`
- Produces: `StoryCompilation(snapshot, diagnostics)`
- Produces: `StoryCompiler.compile(source_root: Path) -> StoryCompilation`
- Raises: `StoryCompileError` from `StoryCompilation.require_success()`

- [ ] **Step 1: Write failing compiler behavior tests**

Create small project fixtures with two or three real v3 nodes and assert stable codes:

```python
def test_compiler_rejects_missing_target(story_root):
    write_choice(story_root, source="A", choice_id="A_to_B", target="MISSING")
    result = StoryCompiler().compile(story_root)
    assert ("STORY_TARGET_MISSING", "nodes/A.json#/choices/0/next/target") in codes(result)


def test_compiler_rejects_unreachable_node(story_root):
    write_node(story_root, "ORPHAN")
    result = StoryCompiler().compile(story_root)
    assert "STORY_NODE_UNREACHABLE" in error_codes(result)


def test_compiler_rejects_parent_that_disagrees_with_incoming_edge(story_root):
    write_sub_node(story_root, "S1", parent_node_id="B", return_target="B")
    write_choice(story_root, source="A", choice_id="A_to_S1", target="S1")
    result = StoryCompiler().compile(story_root)
    assert "STORY_PARENT_MISMATCH" in error_codes(result)


def test_compiler_rejects_condition_outside_attribute_domain(story_root):
    set_attribute_domain(story_root, "trust", minimum=0, maximum=2)
    set_choice_condition(story_root, "A", attribute_gte("trust", 3))
    result = StoryCompiler().compile(story_root)
    assert "STORY_CONDITION_IMPOSSIBLE" in error_codes(result)


def test_compiler_hash_is_independent_of_json_formatting(story_root):
    first = StoryCompiler().compile(story_root).require_success().revision
    reformat_all_json(story_root, indent=4)
    second = StoryCompiler().compile(story_root).require_success().revision
    assert second == first
```

Also cover duplicate global choice/block IDs, missing default entry, missing registry references, invalid resource paths, filename/ID mismatch, non-terminal dead ends, and manifest checksum generation.

- [ ] **Step 2: Run compiler tests and verify RED**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_compiler.py -q
```

Expected: import failure for compiler and diagnostic types.

- [ ] **Step 3: Implement compiler passes**

Use a pass-oriented implementation:

```python
class StoryCompiler:
    def compile(self, source_root: Path) -> StoryCompilation:
        loaded = self._load(source_root)
        diagnostics = [
            *self._validate_ids(loaded),
            *self._validate_registry_references(loaded),
            *self._validate_graph(loaded),
            *self._validate_condition_domains(loaded),
            *self._validate_routing(loaded),
            *self._validate_assets(loaded),
        ]
        if any(item.severity == "error" for item in diagnostics):
            return StoryCompilation(snapshot=None, diagnostics=tuple(diagnostics))
        snapshot = self._build_snapshot(loaded)
        return StoryCompilation(snapshot=snapshot, diagnostics=tuple(diagnostics))
```

Required graph rules:

- Start traversal at `project.entry_node_id`.
- Ignore self-loop edges when determining sub-node ownership.
- Require every normal sub-node `parent_node_id` to match its unique incoming owner.
- Require its explicit leaving edge to return to that owner unless a typed routing mode says otherwise.
- Require every active, non-terminal node to have at least one choice.
- Validate crossing interaction choice IDs and NPC IDs.
- Validate warp allowed targets and exit-cost effects.
- Validate shortcut entry/exit IDs and condition references.

Canonical hashing must serialize with sorted object keys and compact separators while preserving list order:

```python
canonical = json.dumps(
    snapshot_payload_without_revision,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
revision = hashlib.sha256(canonical).hexdigest()
```

- [ ] **Step 4: Run focused and full tests**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_compiler.py -q
backend\venv\Scripts\python.exe -m pytest backend/tests -q
```

Expected: stable diagnostic codes and all backend tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/story/diagnostics.py backend/app/story/compiler.py backend/app/story/__init__.py backend/tests/test_story_v3_compiler.py
git commit -m "feat(story): compile and validate v3 projects"
```

---

### Task 5: Publish immutable story snapshots atomically

**Files:**

- Create: `backend/app/story/publisher.py`
- Create: `backend/tests/test_story_v3_publisher.py`
- Modify: `backend/app/paths.py`
- Modify: `.gitignore`

**Interfaces:**

- Produces: `StoryPublisher(build_root: Path)`
- Produces: `publish(compilation: StoryCompilation, *, base_revision: str | None) -> PublishedRevision`
- Produces: `load_active() -> StorySnapshotV3`
- Raises: `StoryRevisionConflict`

- [ ] **Step 1: Write failing atomic-publication tests**

```python
def test_publish_writes_content_addressed_revision_and_pointer(tmp_path, valid_compilation):
    publisher = StoryPublisher(tmp_path / "build")
    published = publisher.publish(valid_compilation, base_revision=None)

    assert (published.root / "story.snapshot.json").exists()
    assert (published.root / "manifest.json").exists()
    assert json.loads((tmp_path / "build" / "current.json").read_text()) == {
        "revision": published.revision
    }
    assert publisher.load_active().revision == published.revision


def test_stale_base_revision_is_rejected(tmp_path, first_compilation, second_compilation):
    publisher = StoryPublisher(tmp_path / "build")
    first = publisher.publish(first_compilation, base_revision=None)
    publisher.publish(second_compilation, base_revision=first.revision)

    with pytest.raises(StoryRevisionConflict):
        publisher.publish(first_compilation, base_revision=first.revision)


def test_pointer_replace_failure_keeps_previous_revision_active(
    tmp_path, first_compilation, second_compilation, monkeypatch
):
    publisher = StoryPublisher(tmp_path / "build")
    first = publisher.publish(first_compilation, base_revision=None)
    monkeypatch.setattr(publisher, "_replace_pointer", raise_disk_error)

    with pytest.raises(OSError):
        publisher.publish(second_compilation, base_revision=first.revision)

    assert StoryPublisher(tmp_path / "build").load_active().revision == first.revision
```

- [ ] **Step 2: Run publisher tests and verify RED**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_publisher.py -q
```

Expected: import failure for `StoryPublisher`.

- [ ] **Step 3: Implement revision directories and atomic pointer replacement**

Write the complete revision into a sibling temporary directory, flush and close files, rename it to `<build_root>/revisions/<sha256>`, then replace `current.json` through a same-directory temporary file.

```python
def publish(self, compilation: StoryCompilation, *, base_revision: str | None):
    snapshot = compilation.require_success()
    current = self.current_revision()
    if current != base_revision:
        raise StoryRevisionConflict(expected=base_revision, actual=current)
    revision_root = self._write_revision(snapshot)
    self._replace_pointer({"revision": snapshot.revision})
    return PublishedRevision(snapshot.revision, revision_root)
```

If the revision directory already exists, verify its manifest hashes rather than rewriting it. Never delete the active revision in this method.

Add to `backend/app/paths.py`:

```python
STORY_V3_DIR = DATA_DIR / "story_v3"
STORY_BUILD_DIR = DATA_DIR / "story_build"
```

Add `data/story_build/` to `.gitignore`.

- [ ] **Step 4: Verify publication and repository cleanliness**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_publisher.py -q
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_compiler.py backend/tests/test_story_v3_publisher.py -q
git status --short
```

Expected: tests pass and no generated build directory appears in Git status.

- [ ] **Step 5: Commit**

```powershell
git add .gitignore backend/app/paths.py backend/app/story/publisher.py backend/tests/test_story_v3_publisher.py
git commit -m "feat(story): publish immutable story revisions"
```

---

### Task 6: Decouple saves from legacy story tables

**Files:**

- Create: `backend/tests/test_clean_database.py`
- Modify: `backend/app/models/save.py`
- Modify: `backend/app/database.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_save_regressions.py`

**Interfaces:**

- Produces: save tables that store node IDs as validated strings without SQL foreign keys to `story_nodes`
- Consumes: existing `create_save`, `load_save`, `update_save`, and `delete_save`

- [ ] **Step 1: Write the clean-database failing test**

```python
def test_clean_database_can_create_and_load_save_without_story_rows(
    isolated_db_session,
):
    state = GameState(current_node_id="A")

    created = create_save("clean install", state, isolated_db_session)
    loaded = load_save(created["id"], isolated_db_session)

    assert loaded.current_node_id == "A"
    assert isolated_db_session.query(StoryNode).count() == 0
```

Add a second test proving `NodePersistentState(node_id="A")` can be stored without a `StoryNode` row.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_clean_database.py -q
```

Expected: `sqlite3.IntegrityError: FOREIGN KEY constraint failed`.

- [ ] **Step 3: Remove content-table foreign keys**

Change only the two story-content references:

```python
current_node_id = Column(String, nullable=False)
node_id = Column(String, nullable=False)
```

Keep `NodePersistentState.save_id -> saves.id` intact. Update model comments so they no longer claim the database validates story-node existence. Keep legacy `StoryNode` and `Choice` models available because the v2 runtime tests still construct them during Phase 1.

Simplify `init_db()` so a clean database can be created without story seed rows. Retain column-add migrations only if the current model still needs them.

- [ ] **Step 4: Run persistence and full backend tests**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_clean_database.py backend/tests/test_save_regressions.py -q
backend\venv\Scripts\python.exe -m pytest backend/tests -q
```

Expected: clean database tests and all legacy save tests pass without calling `add_node`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models/save.py backend/app/database.py backend/tests/conftest.py backend/tests/test_save_regressions.py backend/tests/test_clean_database.py
git commit -m "fix(storage): decouple saves from story content tables"
```

---

### Task 7: Migrate all story content and apply known semantic corrections

**Files:**

- Create: `backend/scripts/migrate_story_v3.py`
- Modify: `backend/app/story/v2_migration.py`
- Modify: `backend/tests/test_story_v3_migration.py`
- Create: `data/story_v3/project.json`
- Create: `data/story_v3/assets.json`
- Create: all 30 `data/story_v3/nodes/*.json` files listed in File Structure

**Interfaces:**

- Produces: `migrate_project(source_root: Path, destination_root: Path) -> None`
- Consumes: `StoryV2Loader`-compatible v2 files, `migrate_v2_node`, and `StoryCompiler`

- [ ] **Step 1: Write failing project migration assertions**

```python
def test_full_migration_preserves_content_counts(tmp_path):
    destination = tmp_path / "story_v3"
    migrate_project(V2_ROOT, destination)
    compilation = StoryCompiler().compile(destination)
    snapshot = compilation.require_success()

    assert len(snapshot.nodes) == 30
    assert sum(len(node.choices) for node in snapshot.nodes.values()) == 143
    assert total_content_blocks(snapshot) == 846


def test_migration_applies_known_story_repairs(tmp_path):
    destination = tmp_path / "story_v3"
    migrate_project(V2_ROOT, destination)
    story = StoryCompiler().compile(destination).require_success()

    assert story.nodes["S10"].meta.parent_node_id == "F"
    assert story.nodes["S13"].meta.parent_node_id == "G"
    assert story.nodes["S14"].meta.parent_node_id == "G"
    assert story.nodes["S19"].meta.parent_node_id == "H"
    assert choice(story, "S19_choice_02").next.target == "H"
    assert story.nodes["S20"].meta.parent_node_id == "H"
    assert choice(story, "S20_choice_02").next.target == "H"
    assert choice(story, "S20_choice_01").repeat_policy == "once_per_cycle"
    assert choice(story, "S20_choice_01").effects[0].type == "restore_entry_attribute"
    assert attribute_effect(choice(story, "D_choice_05"), "zhang_trust").value == 3
```

Add assertions that:

- A first-run content uses `current_cycle == 1`.
- E crossing lists `E_choice_05` through `E_choice_10` as deep interactions and has maximum `2`.
- K declares exactly eight static warp choices and a typed `sanity_max -1` exit cost.
- J has a typed shortcut condition, endpoints, and a `half_cycles +1` counter effect.
- every choice lacks `priority`;
- every `locked_visibility` value is preserved exactly;
- every absent background is explicitly allowed;
- no machine condition remains a string;
- running migration twice produces byte-identical files.

- [ ] **Step 2: Run full migration tests and verify RED**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_migration.py -q
```

Expected: the whole-project migration function or semantic repair assertions fail.

- [ ] **Step 3: Implement deterministic project migration**

Build `project.json` with:

- entry node `A`;
- attributes `sanity`, `sanity_max`, `courage`, `insight`, and `zhang_trust`;
- explicit integer defaults and min/max bounds;
- all item IDs from `app.domain.items.ITEM_NAMES`;
- all NPC IDs from `app.domain.npcs.NPC_NAMES`;
- every flag referenced or produced by the migrated story;
- counters `completed_cycles` and `half_cycles`;
- jump modes `stay`, `travel`, `shortcut`, and `warp`.

Apply explicit semantic transformations:

```python
PARENT_FIXES = {
    "S10": "F",
    "S13": "G",
    "S14": "G",
    "S19": "H",
    "S20": "H",
}
RETURN_TARGET_FIXES = {
    "S19_choice_02": "H",
    "S20_choice_02": "H",
}
```

For `D_choice_05`, set `zhang_trust` to `3`. For `S20_choice_01`, replace fixed healing with `restore_entry_attribute(sanity)` and set `repeat_policy="once_per_cycle"`.

For E:

```python
deep_choices = [
    {"choice_id": "E_choice_05", "npc_id": "npc_a_liu"},
    {"choice_id": "E_choice_06", "npc_id": "npc_li_ergou"},
    {"choice_id": "E_choice_07", "npc_id": "npc_liu_qisheng"},
    {"choice_id": "E_choice_08", "npc_id": "npc_huijue"},
    {"choice_id": "E_choice_09", "npc_id": "npc_shen_banxian"},
    {"choice_id": "E_choice_10", "npc_id": "npc_deleng"},
]
```

For K, keep `K_choice_02` through `K_choice_09` as the only exits. Put the common cost in typed warp routing:

```json
{
  "type": "warp",
  "allowed_targets": ["A", "B", "C", "D", "E", "F", "G", "H"],
  "exit_effects": [
    {
      "type": "modify_attribute",
      "attribute": "sanity_max",
      "operation": "add",
      "value": -1,
      "clamp": true
    }
  ]
}
```

Move prose-only `trigger_condition` values to `authoring.trigger_description`. Remove `linked_sub_nodes`; topology is derived from choices. Convert invalid background URLs to `background_id: null` with `allow_no_background: true`. `assets.json` is initially an empty typed catalog, so the compiler cannot accept dangling resources.

- [ ] **Step 4: Generate canonical v3 data and compile it**

Run:

```powershell
backend\venv\Scripts\python.exe -m backend.scripts.migrate_story_v3 --source data/story_data_v2 --destination data/story_v3
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_migration.py backend/tests/test_story_v3_compiler.py -q
```

Expected: 30 nodes, 143 choices, 846 content blocks, and zero compiler errors. Re-running the migration leaves `git diff --exit-code -- data/story_v3` clean.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/story/v2_migration.py backend/scripts/migrate_story_v3.py backend/tests/test_story_v3_migration.py data/story_v3
git commit -m "feat(story): migrate canonical content to v3"
```

---

### Task 8: Export the schema and establish the Phase 1 quality gate

**Files:**

- Create: `backend/scripts/export_story_v3_schema.py`
- Create: `backend/scripts/compile_story_v3.py`
- Modify: `backend/tests/test_story_v3_schema.py`
- Modify: `backend/tests/test_story_v3_compiler.py`
- Create: `data/story_v3/story-node-v3.schema.json`
- Modify: `README.md`

**Interfaces:**

- Produces CLI: `python -m backend.scripts.export_story_v3_schema`
- Produces CLI: `python -m backend.scripts.compile_story_v3 --strict`
- Consumes: `StoryNodeV3.model_json_schema()`, `StoryCompiler`, `StoryPublisher`

- [ ] **Step 1: Write failing generated-artifact and CLI tests**

```python
def test_committed_json_schema_matches_pydantic_model():
    expected = StoryNodeV3.model_json_schema(mode="validation")
    actual = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert actual == expected


def test_compile_cli_strict_succeeds_for_canonical_story(tmp_path):
    result = run_compile_cli(
        "--source", str(STORY_V3_ROOT),
        "--build-root", str(tmp_path / "build"),
        "--strict",
    )
    assert result.returncode == 0
    assert '"node_count": 30' in result.stdout
    assert (tmp_path / "build" / "current.json").exists()
```

Add a failure case showing `--strict` exits non-zero and prints stable diagnostics when a temporary node references a missing target.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_story_v3_schema.py backend/tests/test_story_v3_compiler.py -q
```

Expected: schema artifact or CLI helpers are missing.

- [ ] **Step 3: Implement deterministic exporters and document commands**

The schema exporter writes sorted UTF-8 JSON with a final newline:

```python
payload = StoryNodeV3.model_json_schema(mode="validation")
destination.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
```

The compiler CLI prints a JSON summary followed by diagnostics, exits `1` for any error, and also exits `1` for warnings when `--strict` is present. On success it publishes through `StoryPublisher`.

Document these commands in `README.md`:

```powershell
backend\venv\Scripts\python.exe -m backend.scripts.migrate_story_v3 --source data/story_data_v2 --destination data/story_v3
backend\venv\Scripts\python.exe -m backend.scripts.export_story_v3_schema
backend\venv\Scripts\python.exe -m backend.scripts.compile_story_v3 --strict
```

- [ ] **Step 4: Run the complete Phase 1 verification**

Run:

```powershell
backend\venv\Scripts\python.exe -m backend.scripts.export_story_v3_schema
git diff --exit-code -- data/story_v3/story-node-v3.schema.json
backend\venv\Scripts\python.exe -m backend.scripts.compile_story_v3 --strict
backend\venv\Scripts\python.exe -m pytest backend/tests -q
Set-Location frontend
npm run test:unit
npm run build
Set-Location ..
git status --short
```

Expected:

- committed Schema matches generated Schema;
- strict v3 compile succeeds with 30 reachable nodes;
- all backend tests pass;
- frontend unit tests and production build pass;
- only intended Phase 1 files are modified.

- [ ] **Step 5: Commit**

```powershell
git add backend/scripts/export_story_v3_schema.py backend/scripts/compile_story_v3.py backend/tests/test_story_v3_schema.py backend/tests/test_story_v3_compiler.py data/story_v3/story-node-v3.schema.json README.md
git commit -m "build(story): add strict v3 quality gate"
```

---

## Phase 1 Completion Review

Before starting the authoritative runtime plan, verify:

- `../manifest`, slash paths, absolute paths, dotted filenames, and Windows device names are rejected.
- A clean SQLite database can save and load state with no `story_nodes` rows.
- All 30 nodes and 143 choices exist in canonical v3 data.
- All conditions and effects are typed; no executable rule remains a free-form string.
- `cycle` conditions migrated to one-based `current_cycle` semantics.
- S10, S13, S14, S19, and S20 topology metadata matches actual choices.
- E deep interactions and K warp cost exist as typed routing rules.
- H trust can reach its required value.
- S20 expresses restoration and once-per-cycle behavior without fixed `+5`.
- Manifest content and revision hash are compiler-generated.
- A failed publish cannot change the active revision.
- Runtime v2 behavior has not been partially rewritten in this phase.

Record the exact verification output in the implementation handoff. Then write the separate Phase 2 authoritative-runtime plan against the committed Phase 1 interfaces.

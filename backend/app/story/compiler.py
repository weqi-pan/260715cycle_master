"""Whole-project compilation for Story System v3 authoring sources."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ValidationError

from app.schemas.story_v3 import (
    AssetCatalogV3,
    ConditionV3,
    StoryEffectV3,
    StoryNodeV3,
    StoryProjectV3,
    StorySnapshotV3,
)
from app.story.diagnostics import StoryCompileError, StoryDiagnostic


@dataclass(frozen=True, slots=True)
class StoryCompilation:
    """The optional compiled snapshot and all structured findings."""

    snapshot: StorySnapshotV3 | None
    diagnostics: tuple[StoryDiagnostic, ...]

    def require_success(self) -> StorySnapshotV3:
        if self.snapshot is None or any(
            diagnostic.severity == "error"
            for diagnostic in self.diagnostics
        ):
            raise StoryCompileError(self.diagnostics)
        return self.snapshot


class StoryCompiler:
    """Compile one v3 source tree into an immutable runtime snapshot."""

    def compile(self, source_root: Path) -> StoryCompilation:
        loaded, load_diagnostics = self._load(Path(source_root))
        if loaded is None:
            return StoryCompilation(
                snapshot=None,
                diagnostics=_stable_diagnostics(load_diagnostics),
            )

        diagnostics = [
            *load_diagnostics,
            *self._validate_ids(loaded),
            *self._validate_registry_references(loaded),
            *self._validate_graph(loaded),
            *self._validate_condition_domains(loaded),
            *self._validate_routing(loaded),
            *self._validate_assets(loaded),
        ]
        stable = _stable_diagnostics(diagnostics)
        if any(item.severity == "error" for item in stable):
            return StoryCompilation(snapshot=None, diagnostics=stable)
        return StoryCompilation(
            snapshot=self._build_snapshot(loaded),
            diagnostics=stable,
        )

    def _load(
        self,
        source_root: Path,
    ) -> tuple[_LoadedStory | None, list[StoryDiagnostic]]:
        diagnostics: list[StoryDiagnostic] = []
        root = source_root.resolve()
        if not root.is_dir():
            diagnostics.append(
                _error(
                    "STORY_SOURCE_ROOT_MISSING",
                    "Story source root is not a directory.",
                    ".",
                )
            )
            return None, diagnostics

        project = self._load_model(
            root / "project.json",
            StoryProjectV3,
            "project.json",
            diagnostics,
        )
        assets = self._load_model(
            root / "assets.json",
            AssetCatalogV3,
            "assets.json",
            diagnostics,
        )

        node_sources: list[_NodeSource] = []
        nodes_root = root / "nodes"
        if not nodes_root.is_dir():
            diagnostics.append(
                _error(
                    "STORY_SOURCE_MISSING",
                    "Required nodes directory is missing.",
                    "nodes",
                )
            )
        else:
            paths = sorted(
                nodes_root.glob("*.json"),
                key=lambda path: path.name,
            )
            if not paths:
                diagnostics.append(
                    _error(
                        "STORY_SOURCE_MISSING",
                        "No node source files were found.",
                        "nodes",
                    )
                )
            for path in paths:
                location = f"nodes/{path.name}"
                node = self._load_model(
                    path,
                    StoryNodeV3,
                    location,
                    diagnostics,
                )
                if node is not None:
                    node_sources.append(
                        _NodeSource(
                            filename=path.name,
                            location=location,
                            node=node,
                        )
                    )

        if (
            project is None
            or assets is None
            or not node_sources
            or diagnostics
        ):
            return None, diagnostics
        return (
            _LoadedStory(
                root=root,
                project=project,
                assets=assets,
                node_sources=tuple(node_sources),
            ),
            diagnostics,
        )

    def _load_model(
        self,
        path: Path,
        model_type: type[BaseModel],
        location: str,
        diagnostics: list[StoryDiagnostic],
    ):
        if not path.is_file():
            diagnostics.append(
                _error(
                    "STORY_SOURCE_MISSING",
                    "Required story source file is missing.",
                    location,
                )
            )
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            diagnostics.append(
                _error(
                    "STORY_SOURCE_READ_FAILED",
                    "Story source file could not be read as UTF-8.",
                    location,
                )
            )
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            diagnostics.append(
                _error(
                    "STORY_JSON_INVALID",
                    (
                        "Story source contains invalid JSON at "
                        f"line {exc.lineno}, column {exc.colno}."
                    ),
                    location,
                )
            )
            return None
        try:
            return model_type.model_validate(payload)
        except ValidationError as exc:
            for detail in exc.errors(include_url=False):
                diagnostics.append(
                    _error(
                        "STORY_SOURCE_INVALID",
                        (
                            "Story source does not satisfy the v3 schema "
                            f"({detail['type']})."
                        ),
                        location + _json_pointer(detail["loc"]),
                    )
                )
            return None

    def _validate_ids(
        self,
        loaded: _LoadedStory,
    ) -> list[StoryDiagnostic]:
        diagnostics: list[StoryDiagnostic] = []
        node_ids: set[str] = set()
        choice_ids: set[str] = set()
        block_ids: set[str] = set()

        for source in loaded.node_sources:
            node = source.node
            if source.filename != f"{node.id}.json":
                diagnostics.append(
                    _error(
                        "STORY_NODE_FILENAME_MISMATCH",
                        (
                            f"Node {node.id!r} must be stored in "
                            f"{node.id}.json."
                        ),
                        f"{source.location}#/id",
                    )
                )
            if node.id in node_ids:
                diagnostics.append(
                    _error(
                        "STORY_NODE_ID_DUPLICATE",
                        f"Node ID {node.id!r} is defined more than once.",
                        f"{source.location}#/id",
                    )
                )
            else:
                node_ids.add(node.id)

            if not any(
                sequence.when is None
                for sequence in node.entry_sequences
            ):
                diagnostics.append(
                    _error(
                        "STORY_DEFAULT_ENTRY_MISSING",
                        (
                            "Node requires an unconditional entry sequence "
                            "for fallback rendering."
                        ),
                        f"{source.location}#/entry_sequences",
                    )
                )

            for choice_index, choice in enumerate(node.choices):
                if choice.id in choice_ids:
                    diagnostics.append(
                        _error(
                            "STORY_CHOICE_ID_DUPLICATE",
                            (
                                f"Choice ID {choice.id!r} is not globally "
                                "unique."
                            ),
                            (
                                f"{source.location}#/choices/"
                                f"{choice_index}/id"
                            ),
                        )
                    )
                else:
                    choice_ids.add(choice.id)

            for block, location in _iter_blocks(source):
                if block.id in block_ids:
                    diagnostics.append(
                        _error(
                            "STORY_BLOCK_ID_DUPLICATE",
                            (
                                f"Content block ID {block.id!r} is not "
                                "globally unique."
                            ),
                            f"{location}/id",
                        )
                    )
                else:
                    block_ids.add(block.id)
        return diagnostics

    def _validate_registry_references(
        self,
        loaded: _LoadedStory,
    ) -> list[StoryDiagnostic]:
        diagnostics: list[StoryDiagnostic] = []
        project = loaded.project
        nodes = loaded.nodes

        for source in loaded.node_sources:
            node = source.node
            base = source.location
            for sequence_index, sequence in enumerate(node.entry_sequences):
                condition_location = (
                    f"{base}#/entry_sequences/{sequence_index}/when"
                )
                diagnostics.extend(
                    _validate_condition_references(
                        sequence.when,
                        condition_location,
                        project,
                        nodes,
                    )
                )
                for block_index, block in enumerate(sequence.blocks):
                    block_location = (
                        f"{base}#/entry_sequences/{sequence_index}/blocks/"
                        f"{block_index}"
                    )
                    diagnostics.extend(
                        _validate_block_references(
                            block,
                            block_location,
                            project,
                            nodes,
                        )
                    )

            for choice_index, choice in enumerate(node.choices):
                choice_location = f"{base}#/choices/{choice_index}"
                diagnostics.extend(
                    _validate_condition_references(
                        choice.availability.condition,
                        f"{choice_location}/availability/condition",
                        project,
                        nodes,
                    )
                )
                for block_index, block in enumerate(choice.result):
                    diagnostics.extend(
                        _validate_block_references(
                            block,
                            f"{choice_location}/result/{block_index}",
                            project,
                            nodes,
                        )
                    )
                for effect_index, effect in enumerate(choice.effects):
                    diagnostics.extend(
                        _validate_effect_references(
                            effect,
                            f"{choice_location}/effects/{effect_index}",
                            project,
                            nodes,
                        )
                    )

            routing = node.routing
            if routing is not None and routing.type in {"shortcut", "warp"}:
                diagnostics.extend(
                    _validate_condition_references(
                        routing.entry_condition,
                        f"{base}#/routing/entry_condition",
                        project,
                        nodes,
                    )
                )
                effects = (
                    routing.counter_effects
                    if routing.type == "shortcut"
                    else routing.exit_effects
                )
                effects_key = (
                    "counter_effects"
                    if routing.type == "shortcut"
                    else "exit_effects"
                )
                for effect_index, effect in enumerate(effects):
                    diagnostics.extend(
                        _validate_effect_references(
                            effect,
                            (
                                f"{base}#/routing/{effects_key}/"
                                f"{effect_index}"
                            ),
                            project,
                            nodes,
                        )
                    )

            authoring = node.authoring
            for npc_index, npc_id in enumerate(authoring.npcs_present):
                diagnostics.extend(
                    _require_registry_id(
                        npc_id,
                        project.npcs,
                        "NPC",
                        (
                            f"{base}#/authoring/npcs_present/"
                            f"{npc_index}"
                        ),
                    )
                )
            for item_index, note in enumerate(authoring.scene_items):
                diagnostics.extend(
                    _require_registry_id(
                        note.item_id,
                        project.items,
                        "item",
                        (
                            f"{base}#/authoring/scene_items/"
                            f"{item_index}/item_id"
                        ),
                    )
                )
            for note_index, note in enumerate(authoring.npc_item_notes):
                note_location = (
                    f"{base}#/authoring/npc_item_notes/{note_index}"
                )
                diagnostics.extend(
                    _require_registry_id(
                        note.npc_id,
                        project.npcs,
                        "NPC",
                        f"{note_location}/npc_id",
                    )
                )
                diagnostics.extend(
                    _require_registry_id(
                        note.item_id,
                        project.items,
                        "item",
                        f"{note_location}/item_id",
                    )
                )
                if note.required_flag is not None:
                    diagnostics.extend(
                        _require_registry_id(
                            note.required_flag,
                            project.flags,
                            "flag",
                            f"{note_location}/required_flag",
                        )
                    )
        return diagnostics

    def _validate_graph(
        self,
        loaded: _LoadedStory,
    ) -> list[StoryDiagnostic]:
        diagnostics: list[StoryDiagnostic] = []
        nodes = loaded.nodes
        entry_id = loaded.project.entry_node_id

        if entry_id not in nodes:
            diagnostics.append(
                _error(
                    "STORY_ENTRY_MISSING",
                    f"Project entry node {entry_id!r} does not exist.",
                    "project.json#/entry_node_id",
                )
            )

        adjacency: dict[str, list[str]] = {
            node_id: [] for node_id in nodes
        }
        incoming_owners: dict[str, set[str]] = {
            node_id: set() for node_id in nodes
        }
        for source in loaded.node_sources:
            node = source.node
            for choice_index, choice in enumerate(node.choices):
                target = choice.next.target
                if target not in nodes:
                    diagnostics.append(
                        _error(
                            "STORY_TARGET_MISSING",
                            (
                                f"Choice target {target!r} does not name "
                                "a node."
                            ),
                            (
                                f"{source.location}#/choices/{choice_index}"
                                "/next/target"
                            ),
                        )
                    )
                    continue
                adjacency[node.id].append(target)
                if target != node.id:
                    incoming_owners[target].add(node.id)

        reachable: set[str] = set()
        pending = [entry_id] if entry_id in nodes else []
        while pending:
            node_id = pending.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            pending.extend(
                target
                for target in adjacency[node_id]
                if target not in reachable
            )

        for source in loaded.node_sources:
            node = source.node
            if entry_id in nodes and node.id not in reachable:
                diagnostics.append(
                    _error(
                        "STORY_NODE_UNREACHABLE",
                        (
                            f"Node {node.id!r} is unreachable from project "
                            "entry."
                        ),
                        f"{source.location}#/id",
                    )
                )
            if (
                node.id in reachable
                and node.meta.terminal is None
                and not node.choices
            ):
                diagnostics.append(
                    _error(
                        "STORY_NODE_DEAD_END",
                        (
                            "Reachable non-terminal node requires at least "
                            "one choice."
                        ),
                        f"{source.location}#/choices",
                    )
                )

            parent_id = node.meta.parent_node_id
            if node.meta.node_type != "normal":
                continue
            if parent_id is not None and parent_id not in nodes:
                diagnostics.append(
                    _error(
                        "STORY_PARENT_MISSING",
                        f"Parent node {parent_id!r} does not exist.",
                        f"{source.location}#/meta/parent_node_id",
                    )
                )

            owners = incoming_owners[node.id]
            if len(owners) > 1:
                diagnostics.append(
                    _error(
                        "STORY_PARENT_AMBIGUOUS",
                        (
                            "Normal sub-node has multiple incoming owners: "
                            f"{', '.join(sorted(owners))}."
                        ),
                        f"{source.location}#/meta/parent_node_id",
                    )
                )
            elif len(owners) != 1 or next(iter(owners)) != parent_id:
                actual = next(iter(owners)) if owners else None
                diagnostics.append(
                    _error(
                        "STORY_PARENT_MISMATCH",
                        (
                            f"Declared parent {parent_id!r} disagrees with "
                            f"incoming owner {actual!r}."
                        ),
                        f"{source.location}#/meta/parent_node_id",
                    )
                )

            actual_owner = next(iter(owners)) if len(owners) == 1 else None
            if (
                node.routing is None
                and actual_owner is not None
                and not any(
                    choice.next.target == actual_owner
                    and choice.next.target != node.id
                    for choice in node.choices
                )
            ):
                diagnostics.append(
                    _error(
                        "STORY_RETURN_TARGET_MISMATCH",
                        (
                            "Normal sub-node requires an explicit choice "
                            f"returning to owner {actual_owner!r}."
                        ),
                        f"{source.location}#/choices",
                    )
                )
        return diagnostics

    def _validate_condition_domains(
        self,
        loaded: _LoadedStory,
    ) -> list[StoryDiagnostic]:
        diagnostics: list[StoryDiagnostic] = []
        for attribute_id, definition in loaded.project.attributes.items():
            location = f"project.json#/attributes/{attribute_id}"
            if definition.minimum > definition.maximum:
                diagnostics.append(
                    _error(
                        "STORY_ATTRIBUTE_DOMAIN_INVALID",
                        "Attribute minimum exceeds maximum.",
                        location,
                    )
                )
            elif not (
                definition.minimum
                <= definition.default
                <= definition.maximum
            ):
                diagnostics.append(
                    _error(
                        "STORY_ATTRIBUTE_DEFAULT_OUT_OF_RANGE",
                        "Attribute default is outside its declared domain.",
                        f"{location}/default",
                    )
                )

        for source in loaded.node_sources:
            for condition, location in _iter_conditions(source):
                diagnostics.extend(
                    _find_impossible_conditions(
                        condition,
                        location,
                        loaded.project,
                    )
                )
        return diagnostics

    def _validate_routing(
        self,
        loaded: _LoadedStory,
    ) -> list[StoryDiagnostic]:
        diagnostics: list[StoryDiagnostic] = []
        nodes = loaded.nodes
        jump_modes = set(loaded.project.jump_modes)

        for source in loaded.node_sources:
            node = source.node
            base = source.location
            for choice_index, choice in enumerate(node.choices):
                choice_location = f"{base}#/choices/{choice_index}/next"
                if choice.next.mode not in jump_modes:
                    diagnostics.append(
                        _error(
                            "STORY_JUMP_MODE_UNDECLARED",
                            (
                                f"Jump mode {choice.next.mode!r} is not "
                                "declared by the project."
                            ),
                            f"{choice_location}/mode",
                        )
                    )

            routing = node.routing
            if routing is None:
                for choice_index, choice in enumerate(node.choices):
                    if choice.next.mode in {"shortcut", "warp"}:
                        diagnostics.append(
                            _error(
                                "STORY_ROUTING_MISSING",
                                (
                                    f"{choice.next.mode!r} choice requires "
                                    "matching typed routing metadata."
                                ),
                                (
                                    f"{base}#/choices/{choice_index}"
                                    "/next/mode"
                                ),
                            )
                        )
                continue

            if routing.type == "crossing":
                local_choices = {choice.id for choice in node.choices}
                for interaction_index, interaction in enumerate(
                    routing.deep_interactions
                ):
                    location = (
                        f"{base}#/routing/deep_interactions/"
                        f"{interaction_index}"
                    )
                    if interaction.choice_id not in local_choices:
                        diagnostics.append(
                            _error(
                                "STORY_ROUTING_CHOICE_MISSING",
                                (
                                    f"Crossing choice "
                                    f"{interaction.choice_id!r} is not "
                                    "defined by this node."
                                ),
                                f"{location}/choice_id",
                            )
                        )
                    diagnostics.extend(
                        _require_registry_id(
                            interaction.npc_id,
                            loaded.project.npcs,
                            "NPC",
                            f"{location}/npc_id",
                        )
                    )

            elif routing.type == "shortcut":
                for field in ("entry_node_id", "exit_node_id"):
                    target = getattr(routing, field)
                    if target not in nodes:
                        diagnostics.append(
                            _error(
                                "STORY_ROUTING_TARGET_MISSING",
                                (
                                    f"Shortcut {field} {target!r} does not "
                                    "name a node."
                                ),
                                f"{base}#/routing/{field}",
                            )
                        )
                for choice_index, choice in enumerate(node.choices):
                    if (
                        choice.next.mode == "shortcut"
                        and choice.next.target != routing.exit_node_id
                    ):
                        diagnostics.append(
                            _error(
                                "STORY_SHORTCUT_EXIT_MISMATCH",
                                (
                                    "Shortcut choice target must match "
                                    "routing exit_node_id."
                                ),
                                (
                                    f"{base}#/choices/{choice_index}"
                                    "/next/target"
                                ),
                            )
                        )

            elif routing.type == "warp":
                allowed = set(routing.allowed_targets)
                for target_index, target in enumerate(
                    routing.allowed_targets
                ):
                    if target not in nodes:
                        diagnostics.append(
                            _error(
                                "STORY_ROUTING_TARGET_MISSING",
                                (
                                    f"Warp target {target!r} does not name "
                                    "a node."
                                ),
                                (
                                    f"{base}#/routing/allowed_targets/"
                                    f"{target_index}"
                                ),
                            )
                        )
                for choice_index, choice in enumerate(node.choices):
                    if (
                        choice.next.mode == "warp"
                        and choice.next.target not in allowed
                    ):
                        diagnostics.append(
                            _error(
                                "STORY_WARP_TARGET_NOT_ALLOWED",
                                (
                                    f"Warp choice target "
                                    f"{choice.next.target!r} is not in "
                                    "allowed_targets."
                                ),
                                (
                                    f"{base}#/choices/{choice_index}"
                                    "/next/target"
                                ),
                            )
                        )
                if (
                    routing.sacrifice_target is not None
                    and routing.sacrifice_target not in allowed
                ):
                    diagnostics.append(
                        _error(
                            "STORY_WARP_SACRIFICE_TARGET_INVALID",
                            (
                                "Warp sacrifice_target must be one of "
                                "allowed_targets."
                            ),
                            f"{base}#/routing/sacrifice_target",
                        )
                    )
        return diagnostics

    def _validate_assets(
        self,
        loaded: _LoadedStory,
    ) -> list[StoryDiagnostic]:
        diagnostics: list[StoryDiagnostic] = []
        root = loaded.root
        assets = loaded.assets.assets

        for asset_id, definition in assets.items():
            location = f"assets.json#/assets/{asset_id}/path"
            candidate = Path(definition.path)
            if (
                not definition.path.strip()
                or candidate.is_absolute()
                or not _is_within(root, root / candidate)
            ):
                diagnostics.append(
                    _error(
                        "STORY_ASSET_PATH_INVALID",
                        (
                            "Asset path must be non-empty, relative, and "
                            "remain inside the story source root."
                        ),
                        location,
                    )
                )
            elif not (root / candidate).is_file():
                diagnostics.append(
                    _error(
                        "STORY_ASSET_FILE_MISSING",
                        f"Asset file {definition.path!r} does not exist.",
                        location,
                    )
                )

        for source in loaded.node_sources:
            node = source.node
            for field, expected_kind in (
                ("background_id", "background"),
                ("ambient_id", "audio"),
            ):
                asset_id = getattr(node.scene, field)
                if asset_id is None:
                    continue
                location = f"{source.location}#/scene/{field}"
                definition = assets.get(asset_id)
                if definition is None:
                    diagnostics.append(
                        _error(
                            "STORY_ASSET_MISSING",
                            f"Scene asset {asset_id!r} is not registered.",
                            location,
                        )
                    )
                elif definition.kind != expected_kind:
                    diagnostics.append(
                        _error(
                            "STORY_ASSET_KIND_MISMATCH",
                            (
                                f"Scene field {field} requires an "
                                f"{expected_kind} asset, got "
                                f"{definition.kind}."
                            ),
                            location,
                        )
                    )
        return diagnostics

    def _build_snapshot(self, loaded: _LoadedStory) -> StorySnapshotV3:
        nodes = {
            node_id: loaded.nodes[node_id]
            for node_id in sorted(loaded.nodes)
        }
        payload = {
            "schema_version": 3,
            "project": loaded.project.model_dump(mode="json"),
            "assets": loaded.assets.model_dump(mode="json"),
            "nodes": {
                node_id: node.model_dump(mode="json")
                for node_id, node in nodes.items()
            },
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        revision = hashlib.sha256(canonical).hexdigest()
        return StorySnapshotV3(
            revision=revision,
            project=loaded.project,
            assets=loaded.assets,
            nodes=nodes,
            schema_version=3,
        )


@dataclass(frozen=True, slots=True)
class _NodeSource:
    filename: str
    location: str
    node: StoryNodeV3


@dataclass(frozen=True, slots=True)
class _LoadedStory:
    root: Path
    project: StoryProjectV3
    assets: AssetCatalogV3
    node_sources: tuple[_NodeSource, ...]

    @property
    def nodes(self) -> dict[str, StoryNodeV3]:
        nodes: dict[str, StoryNodeV3] = {}
        for source in self.node_sources:
            nodes.setdefault(source.node.id, source.node)
        return nodes


def _error(code: str, message: str, location: str) -> StoryDiagnostic:
    return StoryDiagnostic(
        code=code,
        severity="error",
        message=message,
        location=location,
    )


def _stable_diagnostics(
    diagnostics: Iterable[StoryDiagnostic],
) -> tuple[StoryDiagnostic, ...]:
    return tuple(
        sorted(
            diagnostics,
            key=lambda item: (
                item.location,
                item.code,
                item.severity,
                item.message,
            ),
        )
    )


def _json_pointer(parts: Iterable[object]) -> str:
    encoded = [
        str(part).replace("~", "~0").replace("/", "~1")
        for part in parts
    ]
    return "#/" + "/".join(encoded) if encoded else ""


def _iter_blocks(source: _NodeSource):
    base = source.location
    for sequence_index, sequence in enumerate(
        source.node.entry_sequences
    ):
        for block_index, block in enumerate(sequence.blocks):
            yield (
                block,
                (
                    f"{base}#/entry_sequences/{sequence_index}/blocks/"
                    f"{block_index}"
                ),
            )
    for choice_index, choice in enumerate(source.node.choices):
        for block_index, block in enumerate(choice.result):
            yield (
                block,
                f"{base}#/choices/{choice_index}/result/{block_index}",
            )


def _iter_conditions(
    source: _NodeSource,
) -> Iterable[tuple[ConditionV3 | None, str]]:
    base = source.location
    for sequence_index, sequence in enumerate(
        source.node.entry_sequences
    ):
        yield (
            sequence.when,
            f"{base}#/entry_sequences/{sequence_index}/when",
        )
        for block_index, block in enumerate(sequence.blocks):
            yield (
                block.when,
                (
                    f"{base}#/entry_sequences/{sequence_index}/blocks/"
                    f"{block_index}/when"
                ),
            )
    for choice_index, choice in enumerate(source.node.choices):
        yield (
            choice.availability.condition,
            f"{base}#/choices/{choice_index}/availability/condition",
        )
        for block_index, block in enumerate(choice.result):
            yield (
                block.when,
                (
                    f"{base}#/choices/{choice_index}/result/"
                    f"{block_index}/when"
                ),
            )
    routing = source.node.routing
    if routing is not None and routing.type in {"shortcut", "warp"}:
        yield routing.entry_condition, f"{base}#/routing/entry_condition"


def _validate_block_references(
    block,
    location: str,
    project: StoryProjectV3,
    nodes: dict[str, StoryNodeV3],
) -> list[StoryDiagnostic]:
    diagnostics = _validate_condition_references(
        block.when,
        f"{location}/when",
        project,
        nodes,
    )
    if block.type == "dialogue":
        diagnostics.extend(
            _require_registry_id(
                block.speaker_id,
                project.npcs,
                "NPC",
                f"{location}/speaker_id",
            )
        )
    return diagnostics


def _validate_condition_references(
    condition: ConditionV3 | None,
    location: str,
    project: StoryProjectV3,
    nodes: dict[str, StoryNodeV3],
) -> list[StoryDiagnostic]:
    if condition is None:
        return []
    if condition.type == "attribute_compare":
        return _require_registry_id(
            condition.attribute,
            project.attributes,
            "attribute",
            f"{location}/attribute",
        )
    if condition.type == "flag_equals":
        return _require_registry_id(
            condition.flag,
            project.flags,
            "flag",
            f"{location}/flag",
        )
    if condition.type == "item":
        return _require_registry_id(
            condition.item_id,
            project.items,
            "item",
            f"{location}/item_id",
        )
    if condition.type == "counter_compare":
        if (
            condition.counter != "current_cycle"
            and condition.counter not in project.counters
        ):
            return [
                _error(
                    "STORY_REGISTRY_REFERENCE_MISSING",
                    (
                        f"Counter {condition.counter!r} is not declared "
                        "by the project."
                    ),
                    f"{location}/counter",
                )
            ]
        return []
    if condition.type == "at_node":
        return _require_registry_id(
            condition.node_id,
            nodes,
            "node",
            f"{location}/node_id",
        )
    if condition.type in {"all", "any"}:
        diagnostics: list[StoryDiagnostic] = []
        for index, nested in enumerate(condition.conditions):
            diagnostics.extend(
                _validate_condition_references(
                    nested,
                    f"{location}/conditions/{index}",
                    project,
                    nodes,
                )
            )
        return diagnostics
    if condition.type == "not":
        return _validate_condition_references(
            condition.condition,
            f"{location}/condition",
            project,
            nodes,
        )
    return []


def _validate_effect_references(
    effect: StoryEffectV3,
    location: str,
    project: StoryProjectV3,
    nodes: dict[str, StoryNodeV3],
) -> list[StoryDiagnostic]:
    if effect.type in {"modify_attribute", "restore_entry_attribute"}:
        return _require_registry_id(
            effect.attribute,
            project.attributes,
            "attribute",
            f"{location}/attribute",
        )
    if effect.type == "set_flag":
        return _require_registry_id(
            effect.flag,
            project.flags,
            "flag",
            f"{location}/flag",
        )
    if effect.type == "inventory":
        return _require_registry_id(
            effect.item_id,
            project.items,
            "item",
            f"{location}/item_id",
        )
    if effect.type == "persist_node_item":
        return [
            *_require_registry_id(
                effect.node_id,
                nodes,
                "node",
                f"{location}/node_id",
            ),
            *_require_registry_id(
                effect.item_id,
                project.items,
                "item",
                f"{location}/item_id",
            ),
        ]
    if effect.type == "record_interaction":
        return _require_registry_id(
            effect.subject_id,
            project.npcs,
            "NPC",
            f"{location}/subject_id",
        )
    if (
        effect.type == "modify_counter"
        and effect.counter not in project.counters
    ):
        return [
            _error(
                "STORY_REGISTRY_REFERENCE_MISSING",
                (
                    f"Counter {effect.counter!r} is not declared by the "
                    "project."
                ),
                f"{location}/counter",
            )
        ]
    return []


def _require_registry_id(
    value: str,
    registry,
    registry_name: str,
    location: str,
) -> list[StoryDiagnostic]:
    if value in registry:
        return []
    return [
        _error(
            "STORY_REGISTRY_REFERENCE_MISSING",
            f"Referenced {registry_name} {value!r} is not registered.",
            location,
        )
    ]


def _find_impossible_conditions(
    condition: ConditionV3 | None,
    location: str,
    project: StoryProjectV3,
) -> list[StoryDiagnostic]:
    if condition is None:
        return []
    if condition.type in {"all", "any"}:
        diagnostics: list[StoryDiagnostic] = []
        for index, nested in enumerate(condition.conditions):
            diagnostics.extend(
                _find_impossible_conditions(
                    nested,
                    f"{location}/conditions/{index}",
                    project,
                )
            )
        return diagnostics
    if condition.type == "not":
        return _find_impossible_conditions(
            condition.condition,
            f"{location}/condition",
            project,
        )
    if condition.type != "attribute_compare":
        return []

    definition = project.attributes.get(condition.attribute)
    if definition is None or definition.minimum > definition.maximum:
        return []
    value = condition.value
    impossible = {
        "lt": definition.minimum >= value,
        "lte": definition.minimum > value,
        "eq": value < definition.minimum or value > definition.maximum,
        "ne": (
            definition.minimum
            == definition.maximum
            == value
        ),
        "gte": definition.maximum < value,
        "gt": definition.maximum <= value,
    }[condition.operator]
    if not impossible:
        return []
    return [
        _error(
            "STORY_CONDITION_IMPOSSIBLE",
            (
                f"Attribute comparison cannot hold inside declared domain "
                f"[{definition.minimum}, {definition.maximum}]."
            ),
            location,
        )
    ]


def _is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True

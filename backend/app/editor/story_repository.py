"""对 v2 JSON 进行校验后原子写入的编辑器仓库。"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from ..schemas.story_v2 import StoryNodeV2


class StoryV2Editor:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _raw_nodes(self) -> dict[str, tuple[Path, dict[str, Any]]]:
        result = {}
        for path in sorted(self.root.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            node = StoryNodeV2.model_validate(raw)
            if node.id in result:
                raise ValueError(f"duplicate node id: {node.id}")
            result[node.id] = (path, raw)
        return result

    @staticmethod
    def _validate_all(raw_nodes: dict[str, tuple[Path, dict[str, Any]]]) -> None:
        ids = set(raw_nodes)
        choice_ids: set[str] = set()
        for node_id, (_, raw) in raw_nodes.items():
            node = StoryNodeV2.model_validate(raw)
            if node.id != node_id:
                raise ValueError(f"node id mismatch: {node_id}")
            for choice in node.choices:
                if choice.id in choice_ids:
                    raise ValueError(f"duplicate choice id: {choice.id}")
                choice_ids.add(choice.id)
                if choice.next.node_id not in ids:
                    raise ValueError(
                        f"choice {choice.id} references missing node {choice.next.node_id}"
                    )

    @staticmethod
    def _atomic_write(path: Path, raw: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as handle:
            json.dump(raw, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary = Path(handle.name)
        temporary.replace(path)

    def list_nodes(self) -> list[dict[str, Any]]:
        nodes = []
        for _, raw in self._raw_nodes().values():
            node = StoryNodeV2.model_validate(raw)
            default = next(seq for seq in node.entry_sequences if seq.when is None)
            nodes.append({
                "id": node.id,
                "name": node.meta.name,
                "position": node.meta.position,
                "node_type": node.meta.node_type,
                "time_label": node.meta.time_label,
                "content": "\n\n".join(block.text for block in default.blocks),
                "speaker": None,
                "background": node.scene.background,
            })
        return sorted(nodes, key=lambda item: (item["position"], item["id"]))

    @staticmethod
    def _choice_dict(node_id: str, choice) -> dict[str, Any]:
        return {
            "id": choice.id,
            "from_node_id": node_id,
            "text": choice.label,
            "short_text": choice.short_label,
            "next_node_id": choice.next.node_id,
            "condition": choice.condition,
            "effects": [effect.model_dump(exclude_none=True) for effect in choice.effects],
            "priority": choice.priority,
            "hint": choice.hint,
            "is_hidden_when_locked": True,
            "repeat_policy": choice.repeat_policy,
            "transition_text": None,
        }

    def list_choices(self, node_id: str | None = None) -> list[dict[str, Any]]:
        choices = []
        for current_id, (_, raw) in self._raw_nodes().items():
            if node_id is not None and current_id != node_id:
                continue
            node = StoryNodeV2.model_validate(raw)
            choices.extend(self._choice_dict(current_id, choice) for choice in node.choices)
        return sorted(choices, key=lambda item: (item["priority"], item["id"]))

    def save_node(self, data: dict[str, Any]) -> dict[str, str]:
        node_id = str(data.get("id", "")).strip()
        if not node_id:
            raise ValueError("Missing node id")
        nodes = self._raw_nodes()
        if node_id in nodes:
            path, raw = nodes[node_id]
            meta = raw["meta"]
            for source, target in (
                ("name", "name"), ("position", "position"),
                ("node_type", "node_type"), ("time_label", "time_label"),
            ):
                if source in data:
                    meta[target] = data[source]
            if "background" in data:
                raw.setdefault("scene", {})["background"] = data["background"] or None
            status = "updated"
        else:
            path = self.root / f"{node_id}.json"
            raw = {
                "schema_version": 2,
                "id": node_id,
                "meta": {
                    "name": data.get("name") or node_id,
                    "node_type": data.get("node_type", "normal"),
                    "position": data.get("position", 0),
                    "time_label": data.get("time_label"),
                },
                "scene": {"background": data.get("background") or None},
                "entry_sequences": [{
                    "id": f"{node_id}.entry.default", "when": None, "priority": 0,
                    "blocks": [{
                        "id": f"{node_id}.entry.01", "type": "narration",
                        "text": data.get("content") or "新节点内容", "speaker_id": None,
                        "when": None,
                    }],
                }],
                "choices": [], "routing": {}, "authoring": {},
            }
            nodes[node_id] = (path, raw)
            status = "created"
        StoryNodeV2.model_validate(raw)
        nodes[node_id] = (path, raw)
        self._validate_all(nodes)
        self._atomic_write(path, raw)
        return {"status": status, "id": node_id}

    def save_choice(self, data: dict[str, Any]) -> dict[str, str]:
        choice_id = str(data.get("id", "")).strip()
        from_id = str(data.get("from_node_id", "")).strip()
        if not choice_id or not from_id:
            raise ValueError("Missing choice id or from_node_id")
        nodes = self._raw_nodes()
        if from_id not in nodes:
            raise ValueError(f"Unknown source node: {from_id}")
        existing = None
        for current_id, (_, raw) in nodes.items():
            for index, choice in enumerate(raw["choices"]):
                if choice["id"] == choice_id:
                    existing = (current_id, index, choice)
                    break
        target_id = str(data.get("next_node_id", "")).strip()
        if target_id not in nodes:
            raise ValueError(f"Unknown target node: {target_id}")
        preserved_blocks = existing[2].get("result_blocks", []) if existing else []
        choice = {
            "id": choice_id,
            "label": data.get("text") or choice_id,
            "short_label": data.get("short_text"),
            "condition": data.get("condition") or None,
            "locked_visibility": "hide",
            "repeat_policy": data.get("repeat_policy", "once_per_visit"),
            "priority": data.get("priority", 99),
            "hint": data.get("hint") or None,
            "result_blocks": preserved_blocks,
            "effects": data.get("effects", []),
            "next": {
                "node_id": target_id,
                "mode": "stay" if target_id == from_id else "travel",
            },
        }
        if existing:
            old_id, index, _ = existing
            nodes[old_id][1]["choices"].pop(index)
            status = "updated"
        else:
            status = "created"
        nodes[from_id][1]["choices"].append(choice)
        self._validate_all(nodes)
        changed = {from_id}
        if existing:
            changed.add(existing[0])
        for node_id in changed:
            self._atomic_write(*nodes[node_id])
        return {"status": status}

    def delete_choice(self, choice_id: str) -> dict[str, str]:
        nodes = self._raw_nodes()
        for node_id, (path, raw) in nodes.items():
            remaining = [choice for choice in raw["choices"] if choice["id"] != choice_id]
            if len(remaining) != len(raw["choices"]):
                raw["choices"] = remaining
                self._validate_all(nodes)
                self._atomic_write(path, raw)
                return {"status": "deleted"}
        raise ValueError(f"Choice not found: {choice_id}")

    def delete_node(self, node_id: str) -> dict[str, str]:
        nodes = self._raw_nodes()
        if node_id not in nodes:
            raise ValueError(f"Node not found: {node_id}")
        for other_id, (_, raw) in nodes.items():
            if other_id == node_id:
                continue
            if any(choice["next"]["node_id"] == node_id for choice in raw["choices"]):
                raise ValueError(f"Node {node_id} is still referenced")
        path, _ = nodes.pop(node_id)
        self._validate_all(nodes)
        path.unlink()
        return {"status": "deleted"}

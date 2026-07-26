"""Safe story identifier and node path helpers."""

import re
from pathlib import Path


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

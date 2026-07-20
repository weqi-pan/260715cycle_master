"""Phase 1–5 只读健康审计：v2 剧情、图完整性与 SQLite 基础状态。"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
STORY_ROOT = PROJECT_ROOT / "data" / "story_data_v2"
DATABASE_PATH = PROJECT_ROOT / "data" / "cycle_master.db"
sys.path.insert(0, str(BACKEND_DIR))

from scripts.validate_story_v2 import validate  # noqa: E402


def audit() -> tuple[list[str], list[str], dict[str, Any]]:
    """执行只读审计并返回 errors、warnings 与统计摘要。"""
    errors, warnings, story_summary = validate(STORY_ROOT)
    database_summary: dict[str, Any] = {"exists": DATABASE_PATH.exists()}

    if DATABASE_PATH.exists():
        try:
            connection = sqlite3.connect(
                f"file:{DATABASE_PATH}?mode=ro", uri=True
            )
            try:
                database_summary.update(
                    tables=[
                        row[0]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master "
                            "WHERE type='table' ORDER BY name"
                        )
                    ],
                    foreign_keys=connection.execute(
                        "PRAGMA foreign_keys"
                    ).fetchone()[0],
                    journal_mode=connection.execute(
                        "PRAGMA journal_mode"
                    ).fetchone()[0],
                )
            finally:
                connection.close()
        except sqlite3.Error as exc:
            warnings.append(f"SQLite 只读检查失败: {exc}")

    return errors, warnings, {
        "story_source": str(STORY_ROOT.relative_to(PROJECT_ROOT)),
        "story": story_summary,
        "database": database_summary,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="存在任何错误或警告时返回非零状态。",
    )
    args = parser.parse_args()

    errors, warnings, summary = audit()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for item in errors:
        print(f"ERROR {item}")
    for item in warnings:
        print(f"WARN  {item}")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())

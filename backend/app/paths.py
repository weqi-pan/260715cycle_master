"""
Project path resolver.

All paths are computed relative to this file's location. The anchor is:
    backend/app/paths.py
    └── backend/          ← BACKEND_DIR (anchor point)
        └── app/
            └── paths.py  ← __file__

To move the project to another machine, copy the entire project root
directory. No absolute paths are used; everything is derived from __file__.
"""

from pathlib import Path

# Anchor: the directory containing this file
#   cycle_master/backend/app/paths.py  →  backend/app/
_THIS_FILE = Path(__file__).resolve()
_APP_DIR = _THIS_FILE.parent            # backend/app/
BACKEND_DIR = _APP_DIR.parent           # backend/
PROJECT_ROOT = BACKEND_DIR.parent       # cycle_master/

# Derived paths
STORY_DATA_DIR = PROJECT_ROOT / "story_data"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DATABASE_PATH = BACKEND_DIR / "cycle_master.db"
DESIGN_DOCS_DIR = PROJECT_ROOT / "design_docs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
PLAN_DIR = PROJECT_ROOT / "plan"

# ── Validation (runs on import) ──
_required = {
    "BACKEND_DIR": BACKEND_DIR,
    "STORY_DATA_DIR": STORY_DATA_DIR,
}
_missing = [f"{name}: {path}" for name, path in _required.items() if not path.exists()]
if _missing:
    raise FileNotFoundError(
        f"Project structure validation failed. Missing directories:\n"
        + "\n".join(f"  - {m}" for m in _missing)
        + f"\n\nExpected project root at: {PROJECT_ROOT}"
    )


def print_paths():
    """Print all resolved paths (for debugging)."""
    import sys
    out = sys.stdout

    def p(key, val):
        out.write(f"  {key:20s} {val}\n")

    p("PROJECT_ROOT", PROJECT_ROOT)
    p("BACKEND_DIR", BACKEND_DIR)
    p("STORY_DATA_DIR", STORY_DATA_DIR)
    p("FRONTEND_DIR", FRONTEND_DIR)
    p("DATABASE_PATH", DATABASE_PATH)
    p("DESIGN_DOCS_DIR", DESIGN_DOCS_DIR)
    p("SCRIPTS_DIR", SCRIPTS_DIR)
    p("PLAN_DIR", PLAN_DIR)


if __name__ == "__main__":
    print_paths()

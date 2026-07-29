"""Resolve project paths from the repository layout."""

from pathlib import Path


_APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = _APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

DATA_DIR = PROJECT_ROOT / "data"
STORY_V3_DIR = DATA_DIR / "story_v3"
STORY_BUILD_DIR = DATA_DIR / "story_build"
ASSETS_DIR = DATA_DIR / "assets"
DATABASE_PATH = DATA_DIR / "cycle_master.db"
EXPORTS_DIR = DATA_DIR / "exports"

FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_SCRIPTS_DIR = BACKEND_DIR / "scripts"
DOCS_DIR = PROJECT_ROOT / "docs"
PLAN_DIR = PROJECT_ROOT / "plan"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TESTS_DIR = PROJECT_ROOT / "tests"

_required = {
    "BACKEND_DIR": BACKEND_DIR,
    "DATA_DIR": DATA_DIR,
    "STORY_V3_DIR": STORY_V3_DIR,
}
_missing = [f"{name}: {path}" for name, path in _required.items() if not path.exists()]
if _missing:
    raise FileNotFoundError(
        "Project layout validation failed; required directories are missing:\n"
        + "\n".join(f"  - {missing}" for missing in _missing)
        + f"\n\nExpected project root: {PROJECT_ROOT}"
    )


def print_paths() -> None:
    """Print resolved paths for diagnostics."""

    values = {
        "PROJECT_ROOT": PROJECT_ROOT,
        "BACKEND_DIR": BACKEND_DIR,
        "DATA_DIR": DATA_DIR,
        "STORY_V3_DIR": STORY_V3_DIR,
        "STORY_BUILD_DIR": STORY_BUILD_DIR,
        "ASSETS_DIR": ASSETS_DIR,
        "DATABASE_PATH": DATABASE_PATH,
        "EXPORTS_DIR": EXPORTS_DIR,
        "FRONTEND_DIR": FRONTEND_DIR,
        "BACKEND_SCRIPTS_DIR": BACKEND_SCRIPTS_DIR,
        "DOCS_DIR": DOCS_DIR,
        "PLAN_DIR": PLAN_DIR,
        "SCRIPTS_DIR": SCRIPTS_DIR,
        "TESTS_DIR": TESTS_DIR,
    }
    for key, value in values.items():
        print(f"  {key:24s} {value}")


if __name__ == "__main__":
    print_paths()

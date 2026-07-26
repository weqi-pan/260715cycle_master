"""Story identifier validation tests."""

import pytest

from app.story.identifiers import validate_story_id


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

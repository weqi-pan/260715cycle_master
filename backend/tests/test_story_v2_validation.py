"""v2 故事目录级校验器回归测试。"""

from scripts.validate_story_v2 import validate


def test_empty_node_directory_is_invalid(tmp_path):
    (tmp_path / "nodes").mkdir()

    errors, warnings, summary = validate(tmp_path)

    assert "story contains no node files" in errors
    assert warnings == []
    assert summary["node_count"] == 0

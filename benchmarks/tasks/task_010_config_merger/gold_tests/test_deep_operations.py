"""Gold tests — deep merge, diff, and patch on complex nested structures.

These tests FAIL on the buggy code because:
1. merge strategy "merge" drops tail items when override list is longer
2. diff() collapses subtrees deeper than 2 levels into a single "changed"
3. patch() with collapsed diffs overwrites entire nested dicts
"""
import copy
import pytest

from src.confmerge import deep_merge, compute_diff, apply_patch


# ================================================================== merge

class TestMergeListsOfDicts:
    def test_merge_lists_override_longer_keeps_tail(self):
        """When override list is longer, extra items must be appended."""
        base = {"plugins": [{"name": "a", "enabled": True}]}
        over = {"plugins": [
            {"name": "a", "enabled": False},
            {"name": "b", "enabled": True},
            {"name": "c", "enabled": True},
        ]}
        result = deep_merge(base, over, strategy="merge")
        assert len(result["plugins"]) == 3
        assert result["plugins"][0] == {"name": "a", "enabled": False}
        assert result["plugins"][1] == {"name": "b", "enabled": True}
        assert result["plugins"][2] == {"name": "c", "enabled": True}

    def test_merge_lists_base_longer_keeps_base_tail(self):
        """When base list is longer, base tail items must survive."""
        base = {"items": [{"x": 1}, {"x": 2}, {"x": 3}]}
        over = {"items": [{"x": 10}]}
        result = deep_merge(base, over, strategy="merge")
        assert len(result["items"]) == 3
        assert result["items"][0] == {"x": 10}
        assert result["items"][1] == {"x": 2}
        assert result["items"][2] == {"x": 3}

    def test_merge_mixed_scalars_and_dicts(self):
        """Mixed list with scalars and dicts, override longer."""
        base = {"vals": [1, {"a": 2}]}
        over = {"vals": [10, {"a": 20}, 30]}
        result = deep_merge(base, over, strategy="merge")
        assert result["vals"] == [10, {"a": 20}, 30]

    def test_merge_empty_base_list(self):
        """Empty base list + non-empty override → full override list."""
        result = deep_merge({"x": []}, {"x": [1, 2, 3]}, strategy="merge")
        assert result["x"] == [1, 2, 3]


# ================================================================== diff

class TestDiffDeepNesting:
    def test_diff_three_levels_deep(self):
        """Changes at depth 3 should produce granular diff entries."""
        old = {"a": {"b": {"c": 1, "d": 2}}}
        new = {"a": {"b": {"c": 99, "d": 2}}}
        diff = compute_diff(old, new)
        # Expect a single change at path "a.b.c", NOT a wholesale
        # replacement of "a.b".
        assert len(diff) == 1
        assert diff[0]["path"] == "a.b.c"
        assert diff[0]["op"] == "changed"
        assert diff[0]["old"] == 1
        assert diff[0]["value"] == 99

    def test_diff_four_levels_deep(self):
        old = {"x": {"y": {"z": {"w": "old"}}}}
        new = {"x": {"y": {"z": {"w": "new"}}}}
        diff = compute_diff(old, new)
        assert len(diff) == 1
        assert diff[0]["path"] == "x.y.z.w"

    def test_diff_added_at_depth_3(self):
        old = {"a": {"b": {"c": 1}}}
        new = {"a": {"b": {"c": 1, "d": 2}}}
        diff = compute_diff(old, new)
        assert len(diff) == 1
        assert diff[0]["op"] == "added"
        assert diff[0]["path"] == "a.b.d"

    def test_diff_removed_at_depth_3(self):
        old = {"a": {"b": {"c": 1, "d": 2}}}
        new = {"a": {"b": {"c": 1}}}
        diff = compute_diff(old, new)
        assert len(diff) == 1
        assert diff[0]["op"] == "removed"
        assert diff[0]["path"] == "a.b.d"

    def test_diff_multiple_changes_at_depth(self):
        old = {"srv": {"db": {"host": "old", "port": 3306, "name": "mydb"}}}
        new = {"srv": {"db": {"host": "new", "port": 5432, "name": "mydb"}}}
        diff = compute_diff(old, new)
        paths = {e["path"] for e in diff}
        assert paths == {"srv.db.host", "srv.db.port"}


# ================================================================== patch

class TestPatchDeep:
    def test_patch_preserves_sibling_keys_at_depth(self):
        """Applying a diff must not wipe unchanged siblings."""
        old = {"a": {"b": {"changed": 1, "untouched": 99}}}
        new = {"a": {"b": {"changed": 2, "untouched": 99}}}
        diff = compute_diff(old, new)
        result = apply_patch(old, diff)
        assert result["a"]["b"]["changed"] == 2
        assert result["a"]["b"]["untouched"] == 99

    def test_roundtrip_diff_patch_deep_dicts(self):
        """diff(old, new) → patch(old, diff) must equal new.

        Changes inside 3+ level dicts must not collapse siblings.
        """
        old = {
            "infra": {
                "cluster": {
                    "nodes": {"count": 3, "type": "m5.large"},
                    "region": "us-east-1",
                },
            },
        }
        new = {
            "infra": {
                "cluster": {
                    "nodes": {"count": 5, "type": "m5.large"},
                    "region": "us-east-1",
                },
            },
        }
        diff = compute_diff(old, new)
        result = apply_patch(old, diff)
        assert result == new
        # "nodes.type" and "region" must survive
        assert result["infra"]["cluster"]["nodes"]["type"] == "m5.large"
        assert result["infra"]["cluster"]["region"] == "us-east-1"

    def test_roundtrip_with_deep_additions_and_removals(self):
        """Additions and removals at depth > 2 must round-trip."""
        old = {"a": {"b": {"c": {"x": 1, "y": 2}}}}
        new = {"a": {"b": {"c": {"x": 1, "z": 3}}}}
        diff = compute_diff(old, new)
        result = apply_patch(old, diff)
        assert result == new

    def test_patch_does_not_mutate_original(self):
        config = {"a": {"b": {"c": 1}}}
        original = copy.deepcopy(config)
        diff = [{"op": "changed", "path": "a.b.c", "old": 1, "value": 2}]
        apply_patch(config, diff)
        assert config == original

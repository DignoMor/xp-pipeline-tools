"""TreeVisualizer abstract-path tree (SPEC007 slice; no networkx).

Encodes build_tree / get_subtree / tree2str layout, intermediate display nodes,
TreeError on multiple roots, and that networkx is not required. StorageManager
CRUD helpers are used only as fixtures; Allocator / CLI are out of scope.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest


def _pkg():
    return importlib.import_module("YuLabDataAllocator")


def _storage_manager_cls():
    pkg = _pkg()
    assert hasattr(pkg, "StorageManager")
    return pkg.StorageManager


def _tree_visualizer_cls():
    pkg = _pkg()
    assert hasattr(pkg, "TreeVisualizer")
    return pkg.TreeVisualizer


def _exc(name: str):
    pkg = _pkg()
    assert hasattr(pkg, name), f"expected YuLabDataAllocator.{name}"
    return getattr(pkg, name)


def _sm_with(tmp_path: Path, branches: dict[str, str]):
    """Open StorageManager and record branch_path → drive mappings."""
    sm = _storage_manager_cls()(tmp_path / "loc.db")
    for branch, drive in branches.items():
        sm.record_location(branch, drive)
    return sm


# --- no networkx ---


def test_tree_visualizer_does_not_import_networkx(tmp_path: Path) -> None:
    """TreeVisualizer works without pulling in networkx (SPEC007 dependency cleanup)."""
    sys.modules.pop("networkx", None)
    sm = _sm_with(tmp_path, {"a/b": "d1"})
    TreeVisualizer = _tree_visualizer_cls()
    viz = TreeVisualizer(sm)
    tree = viz.build_tree()
    TreeVisualizer.tree2str(tree)
    assert "networkx" not in sys.modules


# --- build_tree ---


def test_build_tree_empty_db_has_synthetic_empty_root(tmp_path: Path) -> None:
    """Falsy root_branch includes all branches with synthetic root node ''."""
    sm = _storage_manager_cls()(tmp_path / "loc.db")
    TreeVisualizer = _tree_visualizer_cls()
    tree = TreeVisualizer(sm).build_tree()
    text = TreeVisualizer.tree2str(tree)
    # Empty root prints as empty label line in full mode (legacy)
    assert text.splitlines()[0] == ""


def test_build_tree_all_branches_under_empty_root(tmp_path: Path) -> None:
    """build_tree() with no root includes every DB branch under ''."""
    sm = _sm_with(
        tmp_path,
        {
            "proj/a": "d1",
            "proj/b": "d1",
            "other": "d2",
        },
    )
    TreeVisualizer = _tree_visualizer_cls()
    tree = TreeVisualizer(sm).build_tree()
    text = TreeVisualizer.tree2str(tree, short_tree=False)
    lines = text.splitlines()
    assert lines[0] == ""
    assert "proj/a" in text
    assert "proj/b" in text
    assert "other" in text


def test_build_tree_invents_intermediate_nodes(tmp_path: Path) -> None:
    """build_tree inserts /-split intermediate nodes even without a DB row."""
    sm = _sm_with(tmp_path, {"a/b/c": "d1"})
    TreeVisualizer = _tree_visualizer_cls()
    tree = TreeVisualizer(sm).build_tree()
    text = TreeVisualizer.tree2str(tree, short_tree=False)
    labels = {ln.strip() for ln in text.splitlines()}
    # Leaf plus intermediates for display only (no DB rows for "a" / "a/b")
    assert "a/b/c" in labels
    assert "a" in labels
    assert "a/b" in labels
    assert sm.get_drive("a") is None
    assert sm.get_drive("a/b") is None


def test_build_tree_with_root_branch_filters_prefix(tmp_path: Path) -> None:
    """Non-empty root_branch keeps startswith children and excludes the root itself as a leaf DB key."""
    sm = _sm_with(
        tmp_path,
        {
            "proj": "d1",
            "proj/a": "d1",
            "proj/b": "d1",
            "other/x": "d2",
        },
    )
    TreeVisualizer = _tree_visualizer_cls()
    tree = TreeVisualizer(sm).build_tree(root_branch="proj")
    text = TreeVisualizer.tree2str(tree, short_tree=False)
    lines = text.splitlines()
    assert lines[0] == "proj"
    assert "proj/a" in text
    assert "proj/b" in text
    assert "other/x" not in text


def test_build_tree_empty_string_root_same_as_all(tmp_path: Path) -> None:
    """root_branch='' is falsy and uses the synthetic empty root (all branches)."""
    sm = _sm_with(tmp_path, {"x/y": "d1"})
    TreeVisualizer = _tree_visualizer_cls()
    tree = TreeVisualizer(sm).build_tree(root_branch="")
    text = TreeVisualizer.tree2str(tree)
    assert text.splitlines()[0] == ""
    assert "x/y" in text


# --- tree2str layout ---


def test_tree2str_indent_is_four_spaces(tmp_path: Path) -> None:
    """Indent is four spaces per level; children sorted lexicographically."""
    sm = _sm_with(
        tmp_path,
        {
            "root/b": "d1",
            "root/a": "d1",
        },
    )
    TreeVisualizer = _tree_visualizer_cls()
    tree = TreeVisualizer(sm).build_tree(root_branch="root")
    text = TreeVisualizer.tree2str(tree, short_tree=False)
    lines = text.splitlines()
    assert lines[0] == "root"
    # Children of root at indent level 1 → four spaces; lex order a before b
    child_lines = [ln for ln in lines[1:] if ln.startswith("    ") and not ln.startswith("        ")]
    labels = [ln.strip() for ln in child_lines]
    assert labels == sorted(labels)
    assert any(ln.startswith("    ") for ln in lines[1:])
    # Exactly four-space indent (not two)
    for ln in lines[1:]:
        if ln.strip():
            leading = len(ln) - len(ln.lstrip(" "))
            assert leading % 4 == 0
            assert leading >= 4


def test_tree2str_short_tree_uses_basename(tmp_path: Path) -> None:
    """short_tree=True labels nodes with os.path.basename (empty root → empty)."""
    sm = _sm_with(tmp_path, {"proj/run": "d1"})
    TreeVisualizer = _tree_visualizer_cls()
    tree = TreeVisualizer(sm).build_tree()
    text = TreeVisualizer.tree2str(tree, short_tree=True)
    assert "proj/run" not in text
    assert os.path.basename("proj/run") in text
    assert "proj" in text  # intermediate basename


def test_tree2str_full_mode_uses_full_node_string(tmp_path: Path) -> None:
    """short_tree=False uses the full node string as the label."""
    sm = _sm_with(tmp_path, {"proj/run": "d1"})
    TreeVisualizer = _tree_visualizer_cls()
    tree = TreeVisualizer(sm).build_tree()
    text = TreeVisualizer.tree2str(tree, short_tree=False)
    assert "proj/run" in text


def test_tree2str_multiple_roots_raises_tree_error() -> None:
    """tree2str with more than one in-degree-0 root raises TreeError."""
    TreeVisualizer = _tree_visualizer_cls()
    TreeError = _exc("TreeError")
    # Ordinary adjacency: node → children, two roots (no shared parent)
    multi_root = {"a": ["a/x"], "b": ["b/y"], "a/x": [], "b/y": []}
    with pytest.raises(TreeError):
        TreeVisualizer.tree2str(multi_root)


# --- get_subtree ---


def test_get_subtree_returns_subgraph_rooted_at_node(tmp_path: Path) -> None:
    """get_subtree(graph, root) returns the subgraph rooted at root (legacy helper)."""
    sm = _sm_with(
        tmp_path,
        {
            "proj/a": "d1",
            "proj/b": "d1",
            "other": "d2",
        },
    )
    TreeVisualizer = _tree_visualizer_cls()
    full = TreeVisualizer(sm).build_tree()
    sub = TreeVisualizer.get_subtree(full, "proj")
    text = TreeVisualizer.tree2str(sub, short_tree=False)
    labels = {ln.strip() for ln in text.splitlines()}
    assert text.splitlines()[0] == "proj"
    assert "proj/a" in labels
    assert "proj/b" in labels
    assert "other" not in labels

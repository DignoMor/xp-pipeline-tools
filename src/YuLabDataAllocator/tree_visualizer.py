"""Abstract-path tree visualization without networkx."""

from __future__ import annotations

import os
from typing import Iterable

from .exceptions import TreeError
from .storage_manager import StorageManager


class _DiGraph:
    """Minimal directed adjacency structure (node → children / parents)."""

    def __init__(self) -> None:
        self._succ: dict[str, set[str]] = {}
        self._pred: dict[str, set[str]] = {}

    def add_node(self, node: str) -> None:
        self._succ.setdefault(node, set())
        self._pred.setdefault(node, set())

    def add_edge(self, parent: str, child: str) -> None:
        self.add_node(parent)
        self.add_node(child)
        self._succ[parent].add(child)
        self._pred[child].add(parent)

    def nodes(self) -> Iterable[str]:
        return self._succ.keys()

    def successors(self, node: str) -> Iterable[str]:
        return self._succ.get(node, set())

    def predecessors(self, node: str) -> Iterable[str]:
        return self._pred.get(node, set())

    def in_degree(self, node: str) -> int:
        return len(self._pred.get(node, set()))

    def has_node(self, node: str) -> bool:
        return node in self._succ

    def copy_empty(self) -> _DiGraph:
        return _DiGraph()


class TreeVisualizer:
    """Build and render directed trees of abstract branch paths from the DB."""

    def __init__(self, storage_manager: StorageManager) -> None:
        self.storage_manager = storage_manager

    def build_tree(self, root_branch: str | None = None) -> _DiGraph:
        """Build a directed tree of abstract paths from DB branch keys.

        If ``root_branch`` is falsy / ``""``, include all branches under a
        synthetic root ``""``. Otherwise include branches that start with
        ``root_branch`` (excluding equality) under root ``root_branch``.

        Intermediate ``/``-split nodes are inserted even without a DB row.
        Candidates are sorted by length ascending before linking.
        """
        locations = self.storage_manager.get_all_locations2drive()
        branches = list(locations.keys())

        if not root_branch:
            root = ""
            candidates = list(branches)
        else:
            root = root_branch
            candidates = [
                b
                for b in branches
                if b.startswith(root_branch) and b != root_branch
            ]

        candidates.sort(key=len)

        graph = _DiGraph()
        graph.add_node(root)

        for branch in candidates:
            self._link_path(graph, root, branch)

        return graph

    @staticmethod
    def _link_path(graph: _DiGraph, root: str, branch: str) -> None:
        """Ensure progressive edges from ``root`` down to ``branch``."""
        if root == "":
            parts = branch.split("/")
            parent = ""
            for i in range(len(parts)):
                node = "/".join(parts[: i + 1])
                graph.add_edge(parent, node)
                parent = node
            return

        # Proper child under root (avoid ambiguous prefix matches like root "a/b"
        # vs branch "a/b2").
        if not branch.startswith(root + "/"):
            return

        suffix = branch[len(root) + 1 :]
        if not suffix:
            return

        parts = suffix.split("/")
        parent = root
        for i in range(len(parts)):
            node = f"{root}/{'/'.join(parts[: i + 1])}"
            graph.add_edge(parent, node)
            parent = node

    @staticmethod
    def get_subtree(graph: _DiGraph, root: str) -> _DiGraph:
        """Return the subgraph of nodes reachable from ``root`` (inclusive)."""
        if not graph.has_node(root):
            sub = graph.copy_empty()
            sub.add_node(root)
            return sub

        sub = graph.copy_empty()
        stack = [root]
        seen: set[str] = set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            sub.add_node(node)
            for child in graph.successors(node):
                sub.add_edge(node, child)
                stack.append(child)
        return sub

    @staticmethod
    def _coerce_tree(tree: _DiGraph | dict) -> _DiGraph:
        """Accept ``_DiGraph`` or adjacency ``dict`` (node → children)."""
        if isinstance(tree, _DiGraph):
            return tree
        if isinstance(tree, dict):
            graph = _DiGraph()
            for parent, children in tree.items():
                graph.add_node(parent)
                for child in children:
                    graph.add_edge(parent, child)
            return graph
        raise TypeError(
            f"tree2str expected _DiGraph or dict adjacency, got {type(tree)!r}"
        )

    @staticmethod
    def tree2str(
        tree: _DiGraph | dict, indent_level: int = 0, short_tree: bool = False
    ) -> str:
        """Depth-first string of ``tree`` with lexicographically sorted children.

        Indent is four spaces per level. Requires exactly one in-degree-0 root
        or raises ``TreeError``. Labels are basenames when ``short_tree`` else
        the full node string (empty root → empty label line in full mode).

        ``tree`` may be a ``_DiGraph`` (as from ``build_tree``) or a plain
        adjacency dict mapping node → iterable of children.
        """
        graph = TreeVisualizer._coerce_tree(tree)
        roots = [n for n in graph.nodes() if graph.in_degree(n) == 0]
        if len(roots) != 1:
            raise TreeError(
                f"tree2str requires exactly one root; found {len(roots)}"
            )
        root = roots[0]

        def _render(node: str, indent: int) -> list[str]:
            if short_tree:
                label = os.path.basename(node)
            else:
                label = node
            lines = [f"{'    ' * indent}{label}"]
            for child in sorted(graph.successors(node)):
                lines.extend(_render(child, indent + 1))
            return lines

        # "\n".join([""]) == "" has no splitlines entries; keep empty label line.
        return "\n".join(_render(root, indent_level)) or "\n"

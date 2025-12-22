from __future__ import annotations
from dataclasses import dataclass, field
from .attrs import Node, Edge


@dataclass(slots=True)
class Patch:
    """
    Minimal delta structure describing how the graph changed.
    This is useful for frontend incremental updates and later undo/redo.

    For now, we keep it simple: added/removed IDs and updated objects.
    """
    added_nodes: List[Node] = field(default_factory=list)
    removed_node_ids: List[str] = field(default_factory=list)

    added_edges: List[Edge] = field(default_factory=list)
    removed_edge_ids: List[str] = field(default_factory=list)

    updated_nodes: List[Node] = field(default_factory=list)
    updated_edges: List[Edge] = field(default_factory=list)

    topology_changed: bool = False

    def merge(self, other: "Patch") -> "Patch":
        self.added_nodes.extend(other.added_nodes)
        self.removed_node_ids.extend(other.removed_node_ids)
        self.added_edges.extend(other.added_edges)
        self.removed_edge_ids.extend(other.removed_edge_ids)
        self.updated_nodes.extend(other.updated_nodes)
        self.updated_edges.extend(other.updated_edges)
        self.topology_changed = self.topology_changed or other.topology_changed
        return self


# backend/app/domain/graph.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal, Tuple, Optional, Dict, Set, List
from collections import deque


# -----------------------------
# Types: ports and endpoints
# -----------------------------
Port = Literal["IN", "OUT"]
Endpoint = Tuple[str, Port]  # (node_id, port)


# -----------------------------
# Domain objects (typed minimal)
# -----------------------------
@dataclass(slots=True)
class Node:
    """
    Core assembly-graph node (segment/vertex).
    """
    id: str
    length_bp: Optional[int] = None
    coverage: Optional[float] = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Edge:
    """
    Port-based edge.

    Instead of storing GFA orientations (+/-) directly, we store endpoints as:
        start = (node_id, port)
        end   = (node_id, port)

    Mapping from GFA L-line (from, from_orient, to, to_orient) is:
        start = (from, end_port(from_orient))
        end   = (to,   start_port(to_orient))

    where:
        end_port('+')   = IN     end_port('-')   = OUT
        start_port('+') = OUT    start_port('-') = IN
    """
    id: str
    start: Endpoint
    end: Endpoint
    overlap: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)


# -----------------------------
# Patch: delta after edits
# -----------------------------
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


# -----------------------------
# Components index (cached)
# -----------------------------
@dataclass(slots=True)
class ComponentSummary:
    cid: int
    num_nodes: int
    num_edges: int


@dataclass(slots=True)
class ComponentsIndex:
    # node_id -> component id
    node_to_cid: Dict[str, int]
    summaries: List[ComponentSummary]

# -----------------------------
# CoreGraph (port-based)
# -----------------------------
@dataclass
class CoreGraph:
    """
    In-memory port graph suitable for assembly graphs.

    Key representation choices:
    - Nodes and edges are stored in dicts by ID.
    - Adjacency is stored per *port*:
        port_edges[(node_id, 'IN')]  = set(edge_ids)
        port_edges[(node_id, 'OUT')] = set(edge_ids)

    Connected components:
    - computed as undirected connectivity over node IDs
    - cached and recomputed lazily after topology changes
    """

    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: Dict[str, Edge] = field(default_factory=dict)

    # port adjacency: each endpoint is incident to a set of edges
    port_edges: Dict[Endpoint, Set[str]] = field(default_factory=dict)

    _components_dirty: bool = True
    _components: Optional[ComponentsIndex] = None

    # -------------------------
    # Internal helpers
    # -------------------------
    def _ensure_ports(self, node_id: str) -> None:
        """
        Ensure both ports exist in the adjacency map.
        This makes adjacency queries safe even for isolated nodes.
        """
        self.port_edges.setdefault((node_id, "IN"), set())
        self.port_edges.setdefault((node_id, "OUT"), set())

    def _touch_topology(self) -> None:
        """
        Mark derived/cached structures as invalid.
        """
        self._components_dirty = True

    # -------------------------
    # Basic accessors
    # -------------------------
    def get_node(self, node_id: str) -> Node:
        try:
            return self.nodes[node_id]
        except KeyError as e:
            raise NodeNotFound(node_id) from e

    def get_edge(self, edge_id: str) -> Edge:
        try:
            return self.edges[edge_id]
        except KeyError as e:
            raise EdgeNotFound(edge_id) from e

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def has_edge(self, edge_id: str) -> bool:
        return edge_id in self.edges

    # -------------------------
    # Adjacency queries
    # -------------------------
    def incident_edges_at_port(self, node_id: str, port: Port) -> Set[str]:
        """
        Return edge IDs incident to (node_id, port).
        """
        if node_id not in self.nodes:
            raise NodeNotFound(node_id)
        self._ensure_ports(node_id)
        return set(self.port_edges.get((node_id, port), set()))

    def incident_edges(self, node_id: str) -> Set[str]:
        """
        Return edge IDs incident to either port of a node.
        """
        return self.incident_edges_at_port(node_id, "IN") | self.incident_edges_at_port(node_id, "OUT")

    def neighbors_undirected(self, node_id: str) -> Set[str]:
        """
        Neighbor nodes ignoring orientation/direction.
        Used for connected components in MVP.

        A node u is adjacent to v if any edge connects any port of u to any port of v.
        """
        if node_id not in self.nodes:
            raise NodeNotFound(node_id)

        nbrs: Set[str] = set()
        for eid in self.incident_edges(node_id):
            e = self.edges[eid]
            a = e.start[0]
            b = e.end[0]
            if a != node_id:
                nbrs.add(a)
            if b != node_id:
                nbrs.add(b)
        nbrs.discard(node_id)
        return nbrs

    # -------------------------
    # Mutations: nodes
    # -------------------------
    def add_node(self, node: Node) -> Patch:
        """
        Add a node and initialize both ports in adjacency.
        """
        if node.id in self.nodes:
            raise NodeExists(node.id)
        self.nodes[node.id] = node
        self._ensure_ports(node.id)
        self._touch_topology()
        return Patch(added_nodes=[node], topology_changed=True)

    def update_node_attrs(
        self,
        node_id: str,
        *,
        length_bp: Optional[int] = None,
        coverage: Optional[float] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Patch:
        """
        Update typed node attributes. This is not a topology change.
        """
        n = self.get_node(node_id)
        if length_bp is not None:
            n.length_bp = length_bp
        if coverage is not None:
            n.coverage = coverage
        if tags is not None:
            n.tags = tags
        return Patch(updated_nodes=[n], topology_changed=False)

    def remove_node(self, node_id: str) -> Patch:
        """
        Remove node and all incident edges.

        In a port-graph, edges are incident to ports; remove both port sets and clean edges.
        """
        if node_id not in self.nodes:
            raise NodeNotFound(node_id)

        patch = Patch(topology_changed=True)

        # Remove all incident edges first (copy to avoid mutating during iteration)
        for eid in sorted(self.incident_edges(node_id)):
            patch.merge(self.remove_edge(eid))

        # Remove adjacency entries for both ports
        self.port_edges.pop((node_id, "IN"), None)
        self.port_edges.pop((node_id, "OUT"), None)

        # Remove node
        del self.nodes[node_id]
        patch.removed_node_ids.append(node_id)

        self._touch_topology()
        return patch

    def remove_nodes(self, node_ids: Iterable[str]) -> Patch:
        patch = Patch(topology_changed=True)
        for nid in node_ids:
            patch.merge(self.remove_node(nid))
        return patch

    # -------------------------
    # Mutations: edges
    # -------------------------
    def add_edge(self, edge: Edge) -> Patch:
        """
        Add an edge connecting two endpoints (node_id, port).

        Note:
        - We store adjacency on both endpoints.
        - We do not enforce any direction semantics here; start/end is just an ordering.
        """
        if edge.id in self.edges:
            raise EdgeExists(edge.id)

        (u, pu) = edge.start
        (v, pv) = edge.end

        if u not in self.nodes or v not in self.nodes:
            raise InvalidEdgeEndpoint(f"{edge.start} -> {edge.end}")

        self.edges[edge.id] = edge

        self._ensure_ports(u)
        self._ensure_ports(v)
        self.port_edges[(u, pu)].add(edge.id)
        self.port_edges[(v, pv)].add(edge.id)

        self._touch_topology()
        return Patch(added_edges=[edge], topology_changed=True)

    def remove_edge(self, edge_id: str) -> Patch:
        """
        Remove edge and update both endpoint adjacency sets.
        """
        e = self.get_edge(edge_id)

        self.port_edges.get(e.start, set()).discard(edge_id)
        self.port_edges.get(e.end, set()).discard(edge_id)

        del self.edges[edge_id]
        self._touch_topology()
        return Patch(removed_edge_ids=[edge_id], topology_changed=True)

    def reconnect_edge_end(
        self,
        edge_id: str,
        *,
        new_start: Optional[Endpoint] = None,
        new_end: Optional[Endpoint] = None,
    ) -> Patch:
        """
        Reconnect edge endpoints (topology edit).

        Use-cases:
        - Move an edge from (A, OUT) to (B, IN)
        - Swap one end while keeping the other unchanged

        This is the primitive you will build many editing operations on.
        """
        e = self.get_edge(edge_id)

        old_start = e.start
        old_end = e.end

        if new_start is None:
            new_start = old_start
        if new_end is None:
            new_end = old_end

        (u, pu) = new_start
        (v, pv) = new_end
        if u not in self.nodes or v not in self.nodes:
            raise InvalidEdgeEndpoint(f"{new_start} -> {new_end}")

        # Update adjacency: remove old incidence, add new
        self.port_edges.get(old_start, set()).discard(edge_id)
        self.port_edges.get(old_end, set()).discard(edge_id)

        self._ensure_ports(u)
        self._ensure_ports(v)
        self.port_edges[(u, pu)].add(edge_id)
        self.port_edges[(v, pv)].add(edge_id)

        # Update edge object
        e.start = new_start
        e.end = new_end

        self._touch_topology()
        return Patch(updated_edges=[e], topology_changed=True)

    # -------------------------
    # Connected components
    # -------------------------
    def get_components(self) -> ComponentsIndex:
        """
        Compute (if needed) and return connected components over nodes, treating the graph as undirected.

        This is recomputed lazily after topology changes. For MVP, BFS over node IDs is sufficient.
        """
        if self._components is not None and not self._components_dirty:
            return self._components

        node_ids = list(self.nodes.keys())
        node_to_cid: Dict[str, int] = {}
        summaries: List[ComponentSummary] = []

        cid = 0
        for start in node_ids:
            if start in node_to_cid:
                continue

            q = deque([start])
            node_to_cid[start] = cid
            nodes_in_comp = 0

            while q:
                u = q.popleft()
                nodes_in_comp += 1
                for v in self.neighbors_undirected(u):
                    if v not in node_to_cid:
                        node_to_cid[v] = cid
                        q.append(v)

            cid += 1
            summaries.append(ComponentSummary(cid=cid - 1, num_nodes=nodes_in_comp, num_edges=0))

        # Count edges per component (assign by the start node's component)
        edge_counts: Dict[int, int] = {s.cid: 0 for s in summaries}
        for e in self.edges.values():
            c = node_to_cid.get(e.start[0])
            if c is not None:
                edge_counts[c] += 1

        summaries = [
            ComponentSummary(cid=s.cid, num_nodes=s.num_nodes, num_edges=edge_counts.get(s.cid, 0))
            for s in summaries
        ]

        self._components = ComponentsIndex(node_to_cid=node_to_cid, summaries=summaries)
        self._components_dirty = False
        return self._components

    def nodes_in_component(self, cid: int) -> List[str]:
        comps = self.get_components()
        return [nid for nid, c in comps.node_to_cid.items() if c == cid]

# backend/app/domain/components.py
from __future__ import annotations
from dataclasses import dataclass
from collections import deque


@dataclass(slots=True)
class ComponentSummary:
    cid: int
    num_nodes: int
    num_edges: int


@dataclass(slots=True)
class ComponentsIndex:
    # node_id -> component id
    node_to_cid: dict[str, int]
    summaries: list[ComponentSummary]


def compute_undirected_components(
    node_ids: list[str],
    neighbors_fn,
    edge_count_fn=None,
) -> ComponentsIndex:
    """
    neighbors_fn(node_id) -> iterable[str] giving adjacent node IDs (undirected view)
    edge_count_fn(optional): cid -> num edges; if absent, edges reported as 0.
    """
    node_to_cid: dict[str, int] = {}
    summaries: list[ComponentSummary] = []

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
            for v in neighbors_fn(u):
                if v not in node_to_cid:
                    node_to_cid[v] = cid
                    q.append(v)

        num_edges = edge_count_fn(cid) if edge_count_fn is not None else 0
        summaries.append(ComponentSummary(cid=cid, num_nodes=nodes_in_comp, num_edges=num_edges))
        cid += 1

    return ComponentsIndex(node_to_cid=node_to_cid, summaries=summaries)

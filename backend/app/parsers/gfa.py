# backend/app/parsers/gfa.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, Literal, Optional, TextIO, Tuple, Union

from app.domain.graph import CoreGraph, Node, Edge, Port, Endpoint


Orient = Literal["+", "-"]


class GFAParseError(Exception):
    pass


def _parse_tags(tag_fields: Iterable[str]) -> Dict[str, str]:
    """
    Parse GFA tags: TAG:TYPE:VALUE
    Returns dict[tag] = "TYPE:VALUE" (preserves type).
    """
    tags: Dict[str, str] = {}
    for t in tag_fields:
        # tolerate empty / malformed tags
        if not t or t.count(":") < 2:
            continue
        tag, typ, val = t.split(":", 2)
        tags[tag] = f"{typ}:{val}"
    return tags


def _get_int_tag(tags: Dict[str, str], key: str) -> Optional[int]:
    v = tags.get(key)
    if v is None:
        return None
    # v looks like "i:123"
    try:
        typ, val = v.split(":", 1)
        if typ != "i":
            return None
        return int(val)
    except Exception:
        return None


def _get_float_tag(tags: Dict[str, str], key: str) -> Optional[float]:
    v = tags.get(key)
    if v is None:
        return None
    # v looks like "f:12.3"
    try:
        typ, val = v.split(":", 1)
        if typ not in ("f", "i"):
            return None
        return float(val)
    except Exception:
        return None


def _infer_coverage(tags: Dict[str, str]) -> Optional[float]:
    """
    Try common coverage tags (varies by toolchain).
    Priority:
      dp:f (common), DP:f, KC:i, RC:i
    """
    for key in ("dp", "DP"):
        v = _get_float_tag(tags, key)
        if v is not None:
            return v
    for key in ("KC", "RC"):
        v = _get_float_tag(tags, key)
        if v is not None:
            return v
    return None


def _start_port(orient: Orient) -> Port:
    # In GFA, a segment in '+' orientation has start at IN, end at OUT.
    # In '-' orientation, start and end swap.
    return "IN" if orient == "+" else "OUT"


def _end_port(orient: Orient) -> Port:
    return "OUT" if orient == "+" else "IN"


def _edge_endpoints_from_gfa_link(
    from_seg: str,
    from_orient: Orient,
    to_seg: str,
    to_orient: Orient,
) -> Tuple[Endpoint, Endpoint]:
    """
    GFA L-line semantics:
      connect the END of 'from' (in from_orient) to the START of 'to' (in to_orient).
    """
    start: Endpoint = (from_seg, _end_port(from_orient))
    end: Endpoint = (to_seg, _start_port(to_orient))
    return start, end


@dataclass(slots=True)
class GFAParseOptions:
    """
    Options controlling parsing policy.

    store_sequence:
      - if True, store sequences in tags or extend Node model later.
      - with the current Node type (id, length_bp, coverage, tags), we do NOT store sequence.
      - length can still be inferred from sequence length when sequence is present and not '*'.
    """
    store_sequence: bool = False  # reserved for future Node extension


def parse_gfa(
    source: Union[str, Path, TextIO],
    *,
    options: Optional[GFAParseOptions] = None,
) -> CoreGraph:
    """
    Parse a GFA v1 file into a CoreGraph.

    Supported records:
      - S (segments) -> Node
      - L (links)    -> Edge with port endpoints

    Unrecognized lines are ignored for now.

    Parameters
    ----------
    source:
      - file path (str/Path) or an open text file object.

    Returns
    -------
    CoreGraph
    """
    if options is None:
        options = GFAParseOptions()

    g = CoreGraph()

    # Edge IDs are not guaranteed unique in GFA L-lines (no explicit edge id).
    # We generate stable IDs using a counter.
    edge_counter = 0

    def _iter_lines(f: TextIO) -> Iterator[Tuple[int, str]]:
        for i, line in enumerate(f, start=1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            yield i, s

    def _open_if_path(src: Union[str, Path, TextIO]) -> Tuple[TextIO, bool]:
        if hasattr(src, "read"):
            return src, False  # already a file-like
        p = Path(src)
        return p.open("rt", encoding="utf-8"), True

    f, should_close = _open_if_path(source)
    try:
        for lineno, line in _iter_lines(f):
            fields = line.split("\t")
            rec = fields[0]

            # -------------------------
            # Segment: S <name> <seq> [tags...]
            # -------------------------
            if rec == "S":
                if len(fields) < 3:
                    raise GFAParseError(f"GFA parse error at line {lineno}: invalid S record")

                seg_id = fields[1]
                seq = fields[2]
                tags = _parse_tags(fields[3:])

                length_bp = _get_int_tag(tags, "LN")
                if length_bp is None:
                    # If sequence is given (not '*'), infer length
                    if seq != "*" and seq != "":
                        length_bp = len(seq)

                cov = _infer_coverage(tags)

                # Optionally store sequence: not supported by current Node type.
                # If you later extend Node with `sequence: str|None`, store it here.
                node = Node(id=seg_id, length_bp=length_bp, coverage=cov, tags=tags)
                g.add_node(node)

            # -------------------------
            # Link: L <from> <from_orient> <to> <to_orient> <overlap> [tags...]
            # -------------------------
            elif rec == "L":
                if len(fields) < 6:
                    raise GFAParseError(f"GFA parse error at line {lineno}: invalid L record")

                from_seg = fields[1]
                from_or = fields[2]
                to_seg = fields[3]
                to_or = fields[4]
                overlap = fields[5]
                tags = _parse_tags(fields[6:])

                if from_or not in ("+", "-") or to_or not in ("+", "-"):
                    raise GFAParseError(
                        f"GFA parse error at line {lineno}: invalid orientation in L record"
                    )

                start_ep, end_ep = _edge_endpoints_from_gfa_link(
                    from_seg, from_or, to_seg, to_or
                )

                # Generate an edge ID that is stable within this parse:
                # include endpoints and a counter to avoid collisions.
                edge_id = f"e{edge_counter}:{start_ep[0]}:{start_ep[1]}->{end_ep[0]}:{end_ep[1]}"
                edge_counter += 1

                edge = Edge(id=edge_id, start=start_ep, end=end_ep, overlap=overlap, tags=tags)
                g.add_edge(edge)

            else:
                # Ignore H/P/W/etc in MVP
                continue

    finally:
        if should_close:
            f.close()

    return g

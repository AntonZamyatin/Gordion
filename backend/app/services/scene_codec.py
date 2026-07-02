# backend/app/services/scene_codec.py
"""Binary scene wire format ("GSC1").

JSON does not survive 10^5-10^6 elements; deck.gl consumes typed arrays. A scene
is a set of columnar typed-array "columns" (contig ribbon geometry + links) plus
a small JSON manifest describing them.

Layout on the wire:
    [4 bytes] magic  = b"GSC1"
    [4 bytes] uint32 LE = header length H
    [H bytes] UTF-8 JSON manifest
    [.......] body = columns concatenated in manifest order

Manifest:
    {
      "version": 1,
      "source": "<name>",
      "contigCount": N,
      "linkCount": L,
      "columns": {
        "<name>": {"dtype": "f32"|"u8", "size": <components>, "offset": <byte>, "length": <elements>},
        ...
      },
      "idTable": [core_id_0, ...],   # contig index -> core node id (for picking)
      "bbox": [minx, miny, maxx, maxy]
    }

f32 columns are emitted before u8 columns so every float column starts at a
4-byte-aligned offset. The decoder copies each column into a fresh typed array
(alignment-safe); a zero-copy variant is a later optimization.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import struct

import numpy as np

MAGIC = b"GSC1"

_DTYPE_TO_TAG = {np.dtype(np.float32): "f32", np.dtype(np.uint8): "u8"}
_TAG_TO_DTYPE = {"f32": np.float32, "u8": np.uint8}


@dataclass(slots=True)
class Scene:
    source: str
    contig_positions: np.ndarray  # float32, flat [inX,inY,outX,outY]* -> len N*4
    contig_width: np.ndarray      # float32, len N
    contig_color: np.ndarray      # uint8, flat RGBA -> len N*4
    link_positions: np.ndarray    # float32, flat [x0,y0,x1,y1]* -> len L*4
    id_table: list[str]
    bbox: tuple[float, float, float, float]

    @property
    def contig_count(self) -> int:
        return int(self.contig_width.size)

    @property
    def link_count(self) -> int:
        return int(self.link_positions.size // 4)


def encode_scene(scene: Scene) -> bytes:
    body = bytearray()
    columns: dict[str, dict] = {}

    def add(name: str, arr: np.ndarray, dtype, size: int) -> None:
        a = np.ascontiguousarray(arr, dtype=dtype).ravel()
        columns[name] = {
            "dtype": _DTYPE_TO_TAG[np.dtype(dtype)],
            "size": size,
            "offset": len(body),
            "length": int(a.size),
        }
        body.extend(a.tobytes())

    # float columns first (keeps every f32 offset 4-byte aligned), u8 last
    add("contigPositions", scene.contig_positions, np.float32, 4)
    add("contigWidth", scene.contig_width, np.float32, 1)
    add("linkPositions", scene.link_positions, np.float32, 4)
    add("contigColor", scene.contig_color, np.uint8, 4)

    manifest = {
        "version": 1,
        "source": scene.source,
        "contigCount": scene.contig_count,
        "linkCount": scene.link_count,
        "columns": columns,
        "idTable": scene.id_table,
        "bbox": list(scene.bbox),
    }
    header = json.dumps(manifest, separators=(",", ":")).encode("utf-8")

    out = bytearray()
    out += MAGIC
    out += struct.pack("<I", len(header))
    out += header
    out += body
    return bytes(out)


def decode_scene(buf: bytes) -> Scene:
    if buf[:4] != MAGIC:
        raise ValueError(f"bad magic: {buf[:4]!r}")
    (hlen,) = struct.unpack_from("<I", buf, 4)
    manifest = json.loads(buf[8 : 8 + hlen])
    body = memoryview(buf)[8 + hlen :]

    def col(name: str) -> np.ndarray:
        c = manifest["columns"][name]
        dt = np.dtype(_TAG_TO_DTYPE[c["dtype"]])
        start = c["offset"]
        nbytes = c["length"] * dt.itemsize
        return np.frombuffer(body[start : start + nbytes], dtype=dt).copy()

    bbox = tuple(manifest["bbox"])  # type: ignore[assignment]
    return Scene(
        source=manifest["source"],
        contig_positions=col("contigPositions"),
        contig_width=col("contigWidth"),
        link_positions=col("linkPositions"),
        contig_color=col("contigColor"),
        id_table=list(manifest["idTable"]),
        bbox=bbox,  # type: ignore[arg-type]
    )

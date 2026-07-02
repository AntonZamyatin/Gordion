// Decoder for the "GSC1" binary scene format (see backend scene_codec.py).
//
//   [4]  magic "GSC1"
//   [4]  uint32 LE header length H
//   [H]  UTF-8 JSON manifest
//   [..] body: columns concatenated in manifest order
//
// Each column is copied into a fresh typed array (alignment-safe).

export type SceneColumn = { dtype: 'f32' | 'u8'; size: number; offset: number; length: number };

export type Scene = {
  source: string;
  contigCount: number;
  linkCount: number;
  contigPositions: Float32Array; // [inX,inY,outX,outY] per contig
  contigWidth: Float32Array; // per contig
  contigColor: Uint8Array; // RGBA per contig
  linkPositions: Float32Array; // [x0,y0,x1,y1] per link
  idTable: string[]; // contig index -> core node id
  bbox: [number, number, number, number];
};

export function decodeScene(buf: ArrayBuffer): Scene {
  const dv = new DataView(buf);
  const magic = String.fromCharCode(dv.getUint8(0), dv.getUint8(1), dv.getUint8(2), dv.getUint8(3));
  if (magic !== 'GSC1') throw new Error(`bad scene magic: ${magic}`);

  const headerLen = dv.getUint32(4, true);
  const manifest = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 8, headerLen)));
  const bodyStart = 8 + headerLen;

  const columns: Record<string, SceneColumn> = manifest.columns;
  const f32 = (name: string): Float32Array => {
    const c = columns[name];
    const start = bodyStart + c.offset;
    return new Float32Array(buf.slice(start, start + c.length * 4));
  };
  const u8 = (name: string): Uint8Array => {
    const c = columns[name];
    const start = bodyStart + c.offset;
    return new Uint8Array(buf.slice(start, start + c.length));
  };

  return {
    source: manifest.source,
    contigCount: manifest.contigCount,
    linkCount: manifest.linkCount,
    contigPositions: f32('contigPositions'),
    contigWidth: f32('contigWidth'),
    contigColor: u8('contigColor'),
    linkPositions: f32('linkPositions'),
    idTable: manifest.idTable,
    bbox: manifest.bbox,
  };
}

// Cross-language check: decode a GSC1 blob with the real sceneCodec (esbuild'd)
// and print a summary to compare against the Python decoder.
import { readFileSync } from 'node:fs';
import { decodeScene } from '../dist-codec/sceneCodec.js';

const buf = readFileSync(process.argv[2]);
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
const s = decodeScene(ab);

const round = (x) => Math.round(x * 1000) / 1000;
const sum = (a) => { let t = 0; for (let i = 0; i < a.length; i++) t += a[i]; return round(t); };

console.log(
  JSON.stringify({
    source: s.source,
    contigCount: s.contigCount,
    linkCount: s.linkCount,
    lenPos: s.contigPositions.length,
    lenWidth: s.contigWidth.length,
    lenColor: s.contigColor.length,
    lenLink: s.linkPositions.length,
    idHead: s.idTable.slice(0, 3),
    bbox: s.bbox.map(round),
    pos8: Array.from(s.contigPositions.slice(0, 8)).map(round),
    color8: Array.from(s.contigColor.slice(0, 8)),
    sumPos: sum(s.contigPositions),
    sumWidth: sum(s.contigWidth),
    sumColor: sum(s.contigColor),
    sumLink: sum(s.linkPositions),
  })
);

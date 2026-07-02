# Phase 1 spike — deck.gl ribbons

Throwaway de-risking spike for the deck.gl migration. It renders ~200k
synthetic 2-point ribbons with `@deck.gl/core` `OrthographicView` + a
`PathLayer` (positions as a **binary** typed-array attribute), and reports FPS
and the picked ribbon.

## Run
```bash
cd spikes/deckgl-ribbons
npm install
npm run dev
```
Open the printed localhost URL. Push the scale with a query param:
`http://localhost:5173/?n=500000`.

## What to check (exit criteria)
- **Pan/zoom is smooth** at 200k (drag to pan, wheel to zoom). Watch the `fps`
  readout in the HUD, and use Chrome DevTools' FPS meter for a true reading —
  the HUD's rAF counter is only a proxy that drops when the main thread saturates.
- **Picking is correct**: hovering a ribbon highlights it (yellow) and the HUD
  shows its index/width/color; clicking pins the same. This proves a contig will
  be pickable as a single object (no per-node reducer gymnastics).
- **Width scaling** looks right across zoom levels (`widthUnits: 'pixels'`).

## Notes
- Non-React on purpose: isolates the renderer (the thing being de-risked) from
  React integration, which comes in Phase 5.
- Data generation mirrors the planned binary scene contract: `positions`
  (`Float32Array` [inX,inY,outX,outY]), `widths` (`Float32Array`), `colors`
  (`Uint8Array` RGBA), `startIndices` (`Uint32Array`).
- This whole folder is disposable; nothing here is imported by the app.
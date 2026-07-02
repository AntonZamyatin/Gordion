# Phase 2 spike — 2D SGD layout

De-risks the layout half of the migration: build the **port graph** (2 nodes per
contig) from a parsed GFA and lay it out with **2D stochastic gradient descent**
(stress minimization), which unfolds genome graphs into BandageNG-like backbones
instead of the knots FR/SFDP produced.

The real modules live in the backend and are keepers:
- `backend/app/layout/port_graph.py`
- `backend/app/layout/engine_sgd.py`

This folder is just a driver that runs them on the example GFAs and produces
(a) a matplotlib PNG for quick eyeballing and (b) a `scene.json` for the deck.gl
spike.

## Run
```bash
# from repo root, using the project venv
.venv/bin/python spikes/layout-sgd/run_layout.py backend/data/example3.gfa
```
Outputs:
- `spikes/layout-sgd/out/<name>_sgd.png` — static preview (ribbons colored by
  component, width by coverage, thin grey links).
- `spikes/deckgl-ribbons/public/scene.json` — load it in the deck.gl spike:
  ```bash
  cd spikes/deckgl-ribbons && npm run dev
  # then open http://localhost:5173/?scene=/scene.json
  ```

Useful flags: `--iterations`, `--pivots`, `--length-scale`.

## Debug dependency
Needs `matplotlib` in the venv (PNG rendering only — NOT a backend runtime dep):
```bash
.venv/bin/pip install matplotlib
```

## What to check (exit criteria)
- Layouts are **unfolded / not knotted** on the example graphs (small
  `example1`, larger `example3`), comparable in character to BandageNG.
- Long contigs are drawn long (length encodes bp); high-coverage contigs are
  thicker; separate components don't overlap.

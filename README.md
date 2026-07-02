# Gordion

Interactive assembly-graph visualization tool — a browser-based, Bandage/BandageNG-style
viewer for `.gfa` assembly graphs. WORK IN PROGRESS.

<img width="1271" height="1148" alt="image" src="https://github.com/user-attachments/assets/abf575c3-d785-4344-a7af-466e2ac8508f" />

## Architecture

Two parts, talking over a compact binary scene format.

**Backend** (`backend/`, Python + FastAPI)
- `domain/` — `CoreGraph`, a topology-only port graph (each contig has an IN and an OUT
  port; edges connect `(node, port)` endpoints). No coordinates live here.
- `parsers/gfa.py` — GFA v1 → `CoreGraph`.
- `layout/` — `port_graph.py` builds a small 2-node-per-contig layout graph; `engine_sgd.py`
  lays it out with sequential, annealed **2D SGD stress minimization** (diameter-backbone
  seed + sparse pivot terms), giving unfolded, Bandage-style layouts. The inner loop is
  JIT-compiled with numba.
- `services/` — `ribbon.py` turns a laid-out port graph into ribbon geometry; `scene_codec.py`
  encodes it as the binary **GSC1** format (typed-array columns + JSON manifest);
  `session_store.py` / `scene_service.py` cache layouts per session.
- `api/` — `POST /graphs/load?name=`, `GET /graphs/{id}/scene` (binary), `GET /graphs/{id}/components`.

**Frontend** (`frontend/`, React + Vite + deck.gl)
- Renders contigs as GPU **ribbons** (`PathLayer` on an `OrthographicView`); a contig is a
  single pickable path, so hover/select work per-contig directly.
- `lib/sceneCodec.ts` decodes GSC1; `store/useGraphStore.ts` (Zustand) holds session/scene/
  selection; the app shell has collapsible sidebars, dataset switching, and search-by-id.

## Running

**Backend** (Python 3.12):
```bash
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
bash backend/run_back.sh          # serves on http://localhost:8000
```

**Frontend** (Node):
```bash
cd frontend
npm install
npm run dev                       # serves on http://localhost:5173
```

Put GFA files in `backend/data/` (git-ignored); the app loads them by name (e.g. `example3.gfa`).

## Repo layout
```
backend/     FastAPI app + tests (pytest)
frontend/    React + deck.gl client
docs/        design notes (deck.gl migration plan)
spikes/      throwaway prototypes (deck.gl renderer, SGD layout driver)
```

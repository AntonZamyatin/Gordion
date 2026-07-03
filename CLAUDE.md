# Gordion — context for AI agents

Interactive assembly-graph viewer: a browser-based, **Bandage/BandageNG-style** tool for
`.gfa` assembly graphs. Backend computes a layout + ribbon geometry and ships it to the
browser as a compact binary scene; the frontend renders it on the GPU with deck.gl.

This file is the root of a **hierarchy of context docs** — read the one closest to what you're
touching before editing:

- `backend/CLAUDE.md` — Python/FastAPI service: parse → port graph → SGD layout → ribbon → GSC1.
- `frontend/CLAUDE.md` — React + Vite + deck.gl client: decode GSC1 → PathLayers → interaction.
- `docs/architecture.md` — end-to-end data flow + the **GSC1** binary scene format spec.
- `docs/deckgl-migration-plan.md` — the completed re-platforming plan (historical rationale).
- `README.md` — user-facing overview + how to run.

## What it does (one paragraph)

A GFA file is parsed into a topology-only `CoreGraph`. Each contig becomes **two layout nodes**
(an IN port and an OUT port) in a small "port graph"; the internal IN↔OUT edge length encodes
contig length (bp), external edges come from GFA links. A **2D SGD stress solver** lays out that
small graph into an unfolded, Bandage-style picture. The result is turned into **ribbon geometry**
(one path per contig, width ∝ coverage, color per component) and encoded as the binary **GSC1**
scene. The browser decodes GSC1 zero-copy into deck.gl `PathLayer`s; because one contig is one
pickable path, hover/select work per-contig for free.

## Golden rules (read before changing anything)

1. **Do NOT "improve" the layout solver.** The approved look is the *under-converged, sequential,
   annealed SGD **with pivots on*** (`iterations=30, n_pivots=50`). Converging harder
   (SMACOF / full stress majorization) straightens chain graphs into a line; degree-averaged
   Jacobi collapses them. Both regress the signed-off aesthetic. See `backend/app/layout/engine_sgd.py`
   and the memory note `gordion-layout-solver`. The numba JIT is bit-identical to the reference
   Python solver — keep it that way (RNG shuffle stays on the numpy Generator).
2. **The GSC1 scene contract is cross-language.** Any change to `scene_codec.py` must be mirrored in
   `frontend/src/lib/sceneCodec.ts` (and vice-versa). f32 columns come first for 4-byte alignment.
3. Only commit/push when the user asks. Local `master` is ahead of `origin/master` and needs
   reconciling before any push.

## Stack

Backend: Python 3.12, FastAPI, Pydantic, numpy, **numba** (JIT), pytest.
Frontend: React 19, Vite, **deck.gl 9** (`OrthographicView` + `PathLayer`), Zustand, TypeScript.

## Repo layout
```
backend/     FastAPI app + pytest suite   (see backend/CLAUDE.md)
frontend/    React + deck.gl client       (see frontend/CLAUDE.md)
docs/        architecture + design notes
spikes/      throwaway prototypes (deck.gl renderer, SGD driver) — not shipped
chat*.json   original ChatGPT design conversations (reference only)
```
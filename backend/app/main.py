from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models.schemas import GraphDTO, NodeDTO, EdgeDTO
from app.parsers.gfa import parse_gfa
from app.api.routes_graph import router as graphs_router


app = FastAPI(title="Gordion")

app.include_router(graphs_router)

# Allow the frontend dev server to call the backend during development.
# In production you will tighten this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

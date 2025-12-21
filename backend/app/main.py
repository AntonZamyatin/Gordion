from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models.schemas import GraphDTO, NodeDTO, EdgeDTO


app = FastAPI(title="Gordion")

# Allow the frontend dev server to call the backend during development.
# In production you will tighten this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/graph/demo", response_model=GraphDTO)
def graph_demo() -> GraphDTO:
    nodes = [
        NodeDTO(id="1", x=0, y=0, label="1", size=10),
        NodeDTO(id="2", x=100, y=0, label="2", size=10),
        NodeDTO(id="3", x=50, y=80, label="3", size=10),
    ]
    edges = [
        EdgeDTO(source="1", target="2"),
        EdgeDTO(source="2", target="3"),
        EdgeDTO(source="3", target="1"),
    ]
    return GraphDTO(nodes=nodes, edges=edges)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

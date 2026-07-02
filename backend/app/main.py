from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes_graph import router as graphs_router
from app.api.routes_scene import router as scene_router


app = FastAPI(title="Gordion")

app.include_router(graphs_router)
app.include_router(scene_router)

# Allow the frontend dev server to call the backend during development.
# In production you will tighten this.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Scene-Source"],
)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

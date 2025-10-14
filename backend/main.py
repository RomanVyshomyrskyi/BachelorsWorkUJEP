from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config_store import load_config
from core.db import init_engine, init_db
from api.setup import router as setup_router

app = FastAPI()

# Allow frontend to call the API in dev (5173) and prod (8080 if behind Nginx)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://localhost:8080", "*"],  # can be specify ["http://localhost:5173"]
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

# bootstrap from saved config if present
_cfg = load_config()
if _cfg:
    init_engine(_cfg["dsn"])
    init_db()

@app.get("/api/health")
def health():
    """Simple health-check endpoint."""
    return {"ok": True, "service": "FastAPI backend"}

app.include_router(setup_router)

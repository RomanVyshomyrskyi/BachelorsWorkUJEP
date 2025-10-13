from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow frontend to call the API in dev (5173) and prod (8080 if behind Nginx)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # can be specify ["http://localhost:5173"]
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    """Simple health-check endpoint."""
    return {"ok": True, "service": "FastAPI backend"}

from fastapi import FastAPI

# Create FastAPI instance
app = FastAPI(
    title="My FastAPI App",
    version="1.0.0",
    description="Basic template for first run."
)

# Root route
@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI is running!"}

# Example endpoint with path parameter
@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "query": q}

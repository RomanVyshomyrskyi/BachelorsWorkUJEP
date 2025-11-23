from fastapi import APIRouter

router = APIRouter()

@router.get("/hello", tags=["Hello World"])
async def read_hello():
    """
    Returns a simple hello world message.
    """
    return {"message": "Hello from the hello_world module!"}

@router.get("/tools", tags=["Hello World"])
async def list_tools():
    """
    Lists the tools available in this module.
    """
    return {"tools": ["/hello", "/tools"]}

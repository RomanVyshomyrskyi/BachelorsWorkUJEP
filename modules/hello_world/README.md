# Hello World Module

A simple demonstration module for testing MCP server registration and basic connectivity.

---

## User Documentation

### Features
- Provides a basic "Hello" message to verify that the system is up and running.

### Available Tools (MCP)
- `say_hello`: Returns a simple hello world message. Use this to test if the server is responding or to greet the user.

---

## Developer Documentation

### Architecture
- **`main.py`**: Contains the tool definition and the `register(mcp: FastMCP)` function.

### Adding New Tools
To add a new tool to this module, simply define a new function and register it within the `register` function in `main.py`:
```python
@mcp.tool(name="new_tool")
def new_tool():
    return "New tool response"
```

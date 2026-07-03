# LocalAPI Module

A helper module to provide information about the local server environment and configuration for integration with external tools like Open WebUI.

---

## User Documentation

### Features
- Retrieves hostname and local IP address.
- Provides guidance on how to connect the Local API with Open WebUI.

### Available Tools (MCP)
- `get_local_api_info`: Returns information about the running Local API (hostname, IP).

### Connecting with Open WebUI
1. Start the server in SSE mode (`python main.py --sse`).
2. The default URL is typically `http://localhost:8000/sse`.
3. Configure Open WebUI to use this as an OpenAI-compatible endpoint or MCP server.

---

## Developer Documentation

### Architecture
- **`main.py`**: Uses the `socket` library to detect network information and defines the helper tool.

### Customizing Network Detection
You can modify the `get_api_info` function in `main.py` if you need to detect additional environment variables or network configurations specific to your deployment.

---

## Cross-Module Interface

### Dependency Declaration
`depends_on = []` — this module has no dependencies on other modules.

### Public API (`get_module_api()`)
This module exposes no public API (returns an empty dict). It is a leaf module with no callable functionality for other modules to consume.

# oci-mcp-server

A Python MCP (Multi-Client Protocol) server for Oracle Cloud Infrastructure (OCI) API Gateway management, with both programmatic and LLM-powered clients.

---

## Features

- **List API Gateways** in a given OCI compartment.
- **Get details** for a specific API Gateway.
- **MCP stdio transport** for easy integration with LLM agents and other clients.
- **LlamaIndex/Ollama client** for natural language interaction with OCI API Gateway resources.

---

## Quickstart

### 1. Prerequisites

- Python 3.11 (required)
- [uv](https://github.com/astral-sh/uv) (fast Python package/dependency manager)
- OCI account with API Gateway access
- OCI session authentication files (`~/.oci/sessions/DEFAULT/token` and `oci_api_key.pem`)

### 2. Install `uv`

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

Or, from [PyPI](https://pypi.org/project/uv/):
```bash
# With pip.
pip install uv
```
```bash
# Or pipx.
pipx install uv
```

If installed via the standalone installer, uv can update itself to the latest version:

```bash
uv self-update
```

Or see [uv installation docs](https://github.com/astral-sh/uv#installation) for other methods.

### 3. Create and Activate a Virtual Environment

```bash
uv venv --python 3.11
source .venv/bin/activate
```

### 4. Install Dependencies

```bash
uv pip install -r pyproject.toml
```

Or, if you want to use `uv` directly:

```bash
uv pip install -e .
```

---

## Cursor & MCP Integration

### 5. Install Cursor

[Cursor](https://www.cursor.com/) is an AI-powered code editor that can natively interact with MCP servers.

To install Cursor:

- Download and install Cursor from the [official website](https://www.cursor.com/) for your platform (macOS, Windows, Linux).
- Follow the installation instructions for your OS.

### 6. Update your `mcp.json` configuration

To connect Cursor to your custom MCP server, you need to update or create an `mcp.json` file in your project root. Use the provided template in `src/mcp_template.json` as a starting point.

Steps

1. Open Cursor Settings by navigating to `Cursor > Settings... > Cursor Settings`

2. Select `MCP > + Add new global MCP server`

You should also be able to edit mcp.json from `vi ~/.cursor/mcp.json`

**Steps:**

1. Copy the content of `src/mcp_template.json` to `~/.cursor/mcp.json` (or to `mcp.json` from the editor):

2. Edit `mcp.json` and update the paths:
   - Replace `<path to Python>` with the absolute path to your Python 3.11 executable if using a virtual environment).
   - Replace `<path to server.py>` with the absolute path to your `server.py` script.


3. Save the file. Cursor will now be able to discover and connect to your MCP server.

---

## Configuration

Edit `src/config.py` to set your OCI compartment and gateway OCIDs, region, and profile as needed:

```python
PROFILE_NAME = 'DEFAULT'
REGION = 'ap-mumbai-1'
SERVICE_ENDPOINT = '<SERVICE ENDPOINT>'
COMPARTMENT_ID = '<COMPARTMENT_ID>'
GATEWAY_ID = '<GATEWAY_ID>' # For Programmatic Client
```

You must have valid OCI session files in `~/.oci/sessions/DEFAULT/`.

You can do so by something like this `oci session authenticate --tenancy-name <TENANCY_NAME> --profile-name DEFAULT --region $REGION`

---

## Running the MCP Server

From the project root: (I have found that its better to run the server in a separate terminal)

```bash
python src/server.py
```

This will start the MCP server using stdio transport, exposing the following tools:
- `list_gateways_tool(compartment_id)`
- `get_gateway_tool(gateway_id)`

---

## Cursor Client (Agent Mode)
> You do not need to run the MCP server for Cursor. As Cursor Agent will run it from the server resource provided in mcp.json

See `src/mcp_template.json` for an example MCP server config:

```json
{
    "mcpServers": {
        "oci_api_gateway": { 
            "command": "<absolute path to Python (preferably from .venv)>",
            "args": [
                "<absolute path to server.py>"
            ]
        }
    }
}
```

---

In the Cursor editor, you can now interact with the MCP server using natural language queries.

For example, to list all the gateways in a specific compartment, you can type:

Example:
```text
list all the gateways in ocid1.compartment.oc1..aaaaaaaai2zzsg.............................m4pjq
```

The Cursor agent will process your request and return the results from the MCP server.

## Programmatic Client

> The Programmatic Client allows you to test and interact with your custom MCP tools directly using Python code, without involving an AI agent.
It's useful for verifying tool functionality and debugging server responses in a straightforward, scriptable way.

See `src/client_stdio.py` for a simple example:

```bash
python src/client_stdio.py
```

This will:
- Connect to the MCP server
- List available tools
- Call the `list_gateways_tool` and `get_gateway_tool` methods and print results

---

## WIP: LlamaIndex + Ollama Client
> The LlamaIndex + Ollama Client is a work in progress (WIP) that aims to enable natural language interaction with your MCP tools using an self hosted LLM agent

See `src/client_llama_react.py` for an advanced example using LlamaIndex and Ollama (Llama 3.2):

- Make sure you have [Ollama](https://ollama.com/) running locally with the `llama3.2` model.
- Edit the `server_params` path in `client_llama_react.py` if needed.

```bash
python src/client_llama_react.py
```

This will:
- Connect to the MCP server
- Wrap the tools for LlamaIndex
- Run a natural language query using the LLM

---


## Streamable HTTP Server

The project includes a **fully functional** Streamable HTTP transport server that fixes the parameter validation issues found in the standard FastMCP implementation:

### Running the Streamable HTTP Server

```bash
python src/streaming_server.py
```

This starts the server on `http://127.0.0.1:8000/mcp` with Server-Sent Events (SSE) support.

### Key Features

- ✅ **Fully Functional**: All MCP operations work correctly (unlike FastMCP's broken implementation)
- ✅ **Fixed Parameter Validation**: Properly handles tools/list and tools/call requests
- ✅ **Session Management**: Automatic session creation and tracking
- ✅ **Error Recovery**: Graceful error handling and reporting
- ✅ **Health Monitoring**: Built-in health check endpoint

### Testing with curl

The Streamable HTTP transport uses JSON-RPC over HTTP with SSE responses. Required headers:
- `Content-Type: application/json`
- `Accept: application/json, text/event-stream`

#### Complete Working Flow

```bash
# 1. Initialize Session (creates session automatically)
RESPONSE=$(curl -s -D - -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "curl-client",
        "version": "1.0"
      }
    }
  }')

# Extract session ID
SESSION_ID=$(echo "$RESPONSE" | grep -i "mcp-session-id:" | cut -d' ' -f2 | tr -d '\r')

# 2. List Available Tools (NOW WORKS!)
curl -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2
  }'

# 3. Call list_gateways_tool
curl -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 3,
    "params": {
      "name": "list_gateways_tool",
      "arguments": {
        "compartment_id": "ocid1.compartment.oc1..aaaaaaaaXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
      }
    }
  }'

# 4. Health Check
curl -X GET http://127.0.0.1:8000/health
```

#### Automated Testing

Use the provided test script for comprehensive validation:

```bash
./test_streaming.sh
```

This script tests initialization, tools listing, tool calls, and health checks.

**Note:** Replace the redacted OCIDs with your actual compartment and gateway IDs for real testing.

---

## Development

- All source code is in the `src/` directory.
- Dependencies are managed via `pyproject.toml`.
- To add new tools, edit `src/server.py` (or `src/streaming_server.py` for HTTP) and implement logic in `src/gateway_services.py`(for gateway resources).


---

## Troubleshooting

- Ensure your OCI session files are present and valid.
- Use Python 3.13.5 and the provided virtual environment.
- For LlamaIndex/Ollama, ensure the Ollama server is running and accessible.
- For Streamable HTTP, ensure the server is running on port 8000 and use the correct headers.

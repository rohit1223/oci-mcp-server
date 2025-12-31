# oci-mcp-server

A Python MCP (Multi-Client Protocol) server for Oracle Cloud Infrastructure (OCI) API Gateway management, with both programmatic and LLM-powered clients.

---

## Features

- **List API Gateways** in a given OCI compartment.
- **Get details** for a specific API Gateway.
- **OAuth 2.0 Authentication** with Oracle IDCS for secure API Gateway access.
- **HTTP/JSON Streaming** MCP server with both GET and POST support.
- **MCP stdio transport** for easy integration with LLM agents and other clients.
- **LlamaIndex/Ollama client** for natural language interaction with OCI API Gateway resources.

---

## Quickstart

### 1. Prerequisites

- Python 3.11 (required)
- [uv](https://github.com/astral-sh/uv) (fast Python package/dependency manager)
- OCI account with API Gateway access
- Oracle IDCS application for OAuth authentication (for HTTP servers)
- OCI session authentication files (`~/.oci/sessions/DEFAULT/token` and `oci_api_key.pem`) (for stdio server)

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

## OAuth Setup for HTTP Servers

The HTTP streaming servers (`streaming_server.py` and `streaming_server_post.py`) use OAuth 2.0 authentication with Oracle IDCS for secure access through API Gateway.

### 1. Configure OAuth Settings

Copy the OAuth configuration template:
```bash
cp src/oauth_config_template.py src/oauth_config.py
```

Edit `src/oauth_config.py` with your IDCS application details:

```python
OAUTH_CONFIG = {
    "client_id": "your_client_id_from_idcs",
    "client_secret": "your_client_secret_from_idcs", 
    "authorization_endpoint": "https://idcs-YOUR-TENANT.identity.oraclecloud.com/oauth2/v1/authorize",
    "token_endpoint": "https://idcs-YOUR-TENANT.identity.oraclecloud.com/oauth2/v1/token",
    "redirect_uri": "https://your-gateway.apigateway.region.oci.customer-oci.com/mcp_no_auth/auth/callback",
    "scope": "openid https://your-gateway.apigateway.region.oci.customer-oci.com/api_gateway_access",
    "audience": "https://your-gateway.apigateway.region.oci.customer-oci.com"
}
```

### 2. IDCS Application Setup

In Oracle IDCS, configure your application with:

**Resource Server Configuration:**
- Primary Audience: Your API Gateway base URL (exactly as used above)
- Exposed Scopes: `api_gateway_access`

**Client Configuration:**
- Grant Types: Authorization Code, Refresh Token
- Enable PKCE
- Redirect URLs: Include your `/mcp_no_auth/auth/callback` URL
- Allowed Scopes: Include `openid` and your resource scope

### 3. API Gateway Setup

Configure your API Gateway with two deployments:

**Protected Deployment (`/mcp`):**
- Authentication: OAuth/JWT validation
- Audience: Your API Gateway base URL
- Required Scope: `api_gateway_access`

**No-Auth Deployment (`/mcp_no_auth`):**
- Authentication: None
- Used only for OAuth callback endpoint

### 4. Running HTTP Servers

**GET Version (Port 8000):**
```bash
python src/streaming_server.py
```

**POST Version (Port 8001):**
```bash
python src/streaming_server_post.py
```

### 5. OAuth Flow

1. Navigate to: `https://your-gateway.com/mcp_no_auth/auth/start`
2. Login with IDCS credentials
3. Get redirected back with access token
4. Use the "Initialize MCP Session" button to start using MCP tools
5. The session ID is automatically stored in cookies for subsequent calls

For detailed OAuth troubleshooting, see `OAUTH_SETUP.md`.

---

## Cursor & MCP Integration

### 6. Install Cursor

[Cursor](https://www.cursor.com/) is an AI-powered code editor that can natively interact with MCP servers.

To install Cursor:

- Download and install Cursor from the [official website](https://www.cursor.com/) for your platform (macOS, Windows, Linux).
- Follow the installation instructions for your OS.

### 7. Update your `mcp.json` configuration

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


## HTTP Streaming Servers with OAuth

The project includes **two HTTP streaming servers** with OAuth 2.0 authentication support:

### Available Servers

**GET Server (`streaming_server.py`):**
- Uses GET requests with query parameters
- Runs on port 8000
- MCP endpoints: `/r1`, `/mcp`

**POST Server (`streaming_server_post.py`):**
- Uses POST requests with JSON body  
- Runs on port 8001
- MCP endpoints: `/r2`, `/mcp`

### Running the Servers

**GET Version:**
```bash
python src/streaming_server.py
```

**POST Version:**
```bash
python src/streaming_server_post.py
```

Both servers start with OAuth authentication and serve on their respective ports.

### Key Features

- ✅ **OAuth 2.0 Authentication**: Secure access through Oracle IDCS
- ✅ **API Gateway Integration**: Works behind OCI API Gateway with JWT validation
- ✅ **Dual Transport Support**: Both GET (query params) and POST (JSON body) methods
- ✅ **Session Management**: Automatic MCP and auth session tracking
- ✅ **Browser Interface**: Built-in OAuth test client with MCP tool testing
- ✅ **PKCE Support**: Secure OAuth flow with PKCE and state validation

### Testing with OAuth and curl

The HTTP servers require OAuth authentication. Here's how to test:

#### 1. Get OAuth Token via Browser
1. Navigate to `https://your-gateway.com/mcp_no_auth/auth/start`
2. Complete OAuth flow and copy the access token from the success page

#### 2. Test with curl (GET Version)
```bash
# Set your OAuth token
TOKEN="your_access_token_here"

# 1. Initialize MCP Session
RESPONSE=$(curl -s -D - "https://your-gateway.com/mcp/r1?jsonrpc=2.0&method=initialize&params=%7B%22protocolVersion%22%3A%221.0.0%22%2C%22capabilities%22%3A%7B%7D%2C%22clientInfo%22%3A%7B%22name%22%3A%22curl-client%22%2C%22version%22%3A%221.0%22%7D%7D&id=1" \
  -H "Authorization: Bearer $TOKEN")

# Extract session ID
SESSION_ID=$(echo "$RESPONSE" | grep -i "mcp-session-id:" | cut -d' ' -f2 | tr -d '\r')

# 2. List Available Tools
curl "https://your-gateway.com/mcp/r1?jsonrpc=2.0&method=tools/list&id=2&session_id=$SESSION_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "mcp-session-id: $SESSION_ID"

# 3. Call Dummy Gateway Tool
curl "https://your-gateway.com/mcp/r1?jsonrpc=2.0&method=tools/call&params=%7B%22name%22%3A%22get_dummy_gateways_tool%22%2C%22arguments%22%3A%7B%7D%7D&id=3&session_id=$SESSION_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "mcp-session-id: $SESSION_ID"
```

#### 3. Test with curl (POST Version)
```bash
# Set your OAuth token
TOKEN="your_access_token_here"

# 1. Initialize MCP Session
RESPONSE=$(curl -s -D - -X POST "https://your-gateway.com/mcp/r2" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "1.0.0",
      "capabilities": {},
      "clientInfo": {"name": "curl-client", "version": "1.0"}
    },
    "id": 1
  }')

# Extract session ID
SESSION_ID=$(echo "$RESPONSE" | grep -i "mcp-session-id:" | cut -d' ' -f2 | tr -d '\r')

# 2. List Available Tools
curl -X POST "https://your-gateway.com/mcp/r2" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2
  }'

# 3. Call Dummy Gateway Tool
curl -X POST "https://your-gateway.com/mcp/r2" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_dummy_gateways_tool",
      "arguments": {}
    },
    "id": 3
  }'
```

**Note:** Replace `your-gateway.com` with your actual API Gateway URL and use real compartment OCIDs for testing with actual OCI resources.

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

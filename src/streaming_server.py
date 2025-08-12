#!/usr/bin/env python3
"""
Streamable HTTP MCP Server
Fixed implementation that properly handles tools/list and tools/call
Bypasses the broken FastMCP streamable-http transport validation issues
"""

import asyncio
import json
import logging
import sys
import uuid
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlparse

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, Query
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from gateway_services import list_gateways, get_gateway, get_dumy_gateways_json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JSON-RPC Models
class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Optional[str] = None

# MCP Tool Models
class Tool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]

class ToolResult(BaseModel):
    content: List[Dict[str, Any]]

# Session Management
class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.initialized = False
        self.capabilities = {}
        self.client_info = {}
        self.auth_token = None  # Store OAuth token
        self.authenticated = False

# In-memory session store
sessions: Dict[str, Session] = {}

# OAuth token store (in production, use a proper cache/database)
oauth_tokens: Dict[str, Dict[str, Any]] = {}

app = FastAPI(title="MCP Streamable HTTP Server")

# Available tools
AVAILABLE_TOOLS = [
    Tool(
        name="list_gateways_tool",
        description="List all API gateways in a compartment",
        inputSchema={
            "type": "object",
            "properties": {
                "compartment_id": {
                    "type": "string",
                    "description": "The OCID of the compartment"
                }
            },
            "required": ["compartment_id"]
        }
    ),
    Tool(
        name="get_gateway_tool", 
        description="Get details for a specific gateway",
        inputSchema={
            "type": "object",
            "properties": {
                "gateway_id": {
                    "type": "string", 
                    "description": "The OCID of the gateway"
                }
            },
            "required": ["gateway_id"]
        }
    ),
    Tool(
        name="get_dummy_gateways_tool",
        description="Get dummy gateways JSON with 'Successful OIDC flow' message",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    )
]

def create_sse_response(data: dict) -> str:
    """Create SSE formatted response"""
    return f"event: message\ndata: {json.dumps(data)}\n\n"

def create_error_response(request_id: Optional[Union[str, int]], code: int, message: str, data: Optional[str] = None) -> dict:
    """Create JSON-RPC error response"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
            "data": data or ""
        }
    }

def create_success_response(request_id: Optional[Union[str, int]], result: dict) -> dict:
    """Create JSON-RPC success response"""
    return {
        "jsonrpc": "2.0", 
        "id": request_id,
        "result": result
    }

async def handle_initialize(request: JSONRPCRequest, session: Session) -> dict:
    """Handle initialize method"""
    if not request.params:
        return create_error_response(request.id, -32602, "Missing parameters")
    
    protocol_version = request.params.get("protocolVersion")
    if not protocol_version:
        return create_error_response(request.id, -32602, "Missing protocolVersion")
    
    session.initialized = True
    session.capabilities = request.params.get("capabilities", {})
    session.client_info = request.params.get("clientInfo", {})
    
    result = {
        "protocolVersion": protocol_version,
        "capabilities": {
            "experimental": {},
            "prompts": {"listChanged": False},
            "resources": {"subscribe": False, "listChanged": False}, 
            "tools": {"listChanged": False}
        },
        "serverInfo": {
            "name": "oci_api_gateway",
            "version": "1.0.0"
        }
    }
    
    return create_success_response(request.id, result)

async def handle_tools_list(request: JSONRPCRequest, session: Session) -> dict:
    """Handle tools/list method - FIXED VERSION"""
    if not session.initialized:
        return create_error_response(request.id, -32600, "Session not initialized")
    
    # Accept any params format for tools/list (null, {}, {"cursor": "..."})
    # This fixes the parameter validation issue
    cursor = None
    if request.params:
        cursor = request.params.get("cursor")
    
    tools_data = []
    for tool in AVAILABLE_TOOLS:
        tools_data.append(tool.model_dump())
    
    result = {"tools": tools_data}
    if cursor:  # If cursor was provided, include nextCursor in response
        result["nextCursor"] = None  # No more pages
        
    return create_success_response(request.id, result)

async def handle_tools_call(request: JSONRPCRequest, session: Session) -> dict:
    """Handle tools/call method - FIXED VERSION"""
    if not session.initialized:
        return create_error_response(request.id, -32600, "Session not initialized")
    
    if not request.params:
        return create_error_response(request.id, -32602, "Missing parameters")
    
    tool_name = request.params.get("name")
    arguments = request.params.get("arguments", {})
    
    if not tool_name:
        return create_error_response(request.id, -32602, "Missing tool name")
    
    try:
        # Call the actual tool functions
        if tool_name == "list_gateways_tool":
            compartment_id = arguments.get("compartment_id")
            if not compartment_id:
                return create_error_response(request.id, -32602, "Missing compartment_id")
            
            logger.info(f"Calling list_gateways_tool with compartment_id: {compartment_id}")
            result_data = list_gateways(compartment_id)
            tool_result = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"gateways": result_data})
                    }
                ]
            }
            
        elif tool_name == "get_gateway_tool":
            gateway_id = arguments.get("gateway_id")
            if not gateway_id:
                return create_error_response(request.id, -32602, "Missing gateway_id")
                
            logger.info(f"Calling get_gateway_tool with gateway_id: {gateway_id}")
            result_data = get_gateway(gateway_id)
            tool_result = {
                "content": [
                    {
                        "type": "text", 
                        "text": json.dumps({"gateway": result_data})
                    }
                ]
            }
            
        elif tool_name == "get_dummy_gateways_tool":
            logger.info("Calling get_dummy_gateways_tool")
            result_data = get_dumy_gateways_json()
            tool_result = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result_data)
                    }
                ]
            }
            
        else:
            return create_error_response(request.id, -32601, f"Unknown tool: {tool_name}")
            
        return create_success_response(request.id, tool_result)
        
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        # Return the error as tool output instead of JSON-RPC error
        error_result = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"error": str(e)})
                }
            ]
        }
        return create_success_response(request.id, error_result)

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """Main MCP endpoint with proper session handling"""
    try:
        # Get or create session
        session_id = request.headers.get("mcp-session-id")
        if not session_id:
            # Create new session
            session_id = str(uuid.uuid4())
            session = Session(session_id)
            sessions[session_id] = session
        else:
            session = sessions.get(session_id)
            if not session:
                # Session not found, create new one
                session = Session(session_id)
                sessions[session_id] = session
        
        # Parse JSON-RPC request
        body = await request.body()
        try:
            json_data = json.loads(body.decode())
            rpc_request = JSONRPCRequest(**json_data)
        except Exception as e:
            logger.error(f"Invalid JSON-RPC request: {e}")
            error_resp = create_error_response(None, -32700, "Parse error")
            return StreamingResponse(
                iter([create_sse_response(error_resp)]),
                media_type="text/event-stream",
                headers={"mcp-session-id": session_id}
            )
        
        # Route to appropriate handler
        if rpc_request.method == "initialize":
            response_data = await handle_initialize(rpc_request, session)
        elif rpc_request.method == "tools/list":
            response_data = await handle_tools_list(rpc_request, session)
        elif rpc_request.method == "tools/call":
            response_data = await handle_tools_call(rpc_request, session)
        else:
            response_data = create_error_response(rpc_request.id, -32601, f"Method not found: {rpc_request.method}")
        
        # Return SSE response
        sse_content = create_sse_response(response_data)
        return StreamingResponse(
            iter([sse_content]),
            media_type="text/event-stream", 
            headers={
                "mcp-session-id": session_id,
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        error_resp = create_error_response(None, -32603, "Internal error")
        return StreamingResponse(
            iter([create_sse_response(error_resp)]),
            media_type="text/event-stream"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "sessions": len(sessions)}

@app.get("/auth/start")
async def start_auth():
    """Start OAuth flow - redirect to OIDC provider"""
    # Generate a state token for CSRF protection
    state = str(uuid.uuid4())
    
    # Store state temporarily (in production, use secure storage)
    oauth_tokens[state] = {"created": "pending"}
    
    # This is the OIDC authorization URL that your API Gateway redirects to
    # We'll trigger it directly
    auth_url = "https://irlxwomijighis2rzx3aj7n2c4.apigateway.us-ashburn-1.oci.oc-test.com/rdb/r1"
    
    # Return HTML that will POST to the API Gateway to trigger OIDC
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Starting Authentication...</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                text-align: center;
            }}
            h2 {{ color: #333; }}
            p {{ color: #666; margin: 20px 0; }}
            .spinner {{
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 20px auto;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🔐 Starting Authentication</h2>
            <div class="spinner"></div>
            <p>Redirecting to login page...</p>
            <p style="font-size: 14px; color: #999;">State: {state[:8]}...</p>
        </div>
        <form id="authForm" action="{auth_url}" method="POST" style="display: none;">
            <input type="hidden" name="state" value="{state}">
        </form>
        <script>
            // Auto-submit the form to trigger OIDC
            setTimeout(() => {{
                document.getElementById('authForm').submit();
            }}, 1000);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

@app.get("/auth/callback")
async def auth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None)
):
    """Handle OAuth callback from OIDC provider"""
    
    if error:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Error</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: #f5f5f5;
                }}
                .error {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    max-width: 500px;
                }}
                h2 {{ color: #dc3545; }}
                p {{ color: #666; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h2>❌ Authentication Failed</h2>
                <p><strong>Error:</strong> {error}</p>
                <p>{error_description or 'No additional details provided'}</p>
                <p><a href="/auth/start">Try Again</a></p>
            </div>
        </body>
        </html>
        """)
    
    if not code:
        # This might be the "Method Not Allowed" response from the API Gateway
        # Let's provide a success page anyway since cookies are set
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Complete</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                }
                .success {
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    text-align: center;
                    max-width: 500px;
                }
                h2 { color: #28a745; }
                p { color: #666; margin: 20px 0; }
                .code-box {
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    font-family: monospace;
                    margin: 20px 0;
                    word-break: break-all;
                }
                button {
                    background: #28a745;
                    color: white;
                    border: none;
                    padding: 12px 30px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 16px;
                    margin: 10px;
                }
                button:hover {
                    background: #218838;
                }
            </style>
        </head>
        <body>
            <div class="success">
                <h2>✅ Authentication May Be Complete</h2>
                <p>If you completed the OIDC login, your session cookies should now be set.</p>
                <p>You can now test the MCP endpoints:</p>
                <div class="code-box">
                    <strong>Test URL:</strong><br>
                    http://localhost:8000/test
                </div>
                <button onclick="window.location.href='/test'">Open Test Interface</button>
                <button onclick="testInitialize()">Test Initialize</button>
                
                <div id="result" style="margin-top: 20px;"></div>
            </div>
            
            <script>
                async function testInitialize() {
                    const result = document.getElementById('result');
                    result.innerHTML = '<p>Testing MCP initialize...</p>';
                    
                    try {
                        const response = await fetch('/mcp', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Accept': 'text/event-stream'
                            },
                            body: JSON.stringify({
                                jsonrpc: "2.0",
                                method: "initialize",
                                id: 1,
                                params: {
                                    protocolVersion: "2024-11-05",
                                    capabilities: {},
                                    clientInfo: {name: "auth-test", version: "1.0"}
                                }
                            }),
                            credentials: 'include'
                        });
                        
                        const text = await response.text();
                        result.innerHTML = '<div class="code-box" style="text-align: left;"><strong>Response:</strong><br>' + text.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</div>';
                    } catch (error) {
                        result.innerHTML = '<p style="color: red;">Error: ' + error.message + '</p>';
                    }
                }
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    
    # Store the authorization code
    if state and state in oauth_tokens:
        oauth_tokens[state] = {
            "code": code,
            "state": state,
            "authenticated": True
        }
    
    # Create a session for this authenticated user
    session_id = str(uuid.uuid4())
    session = Session(session_id)
    session.authenticated = True
    session.auth_token = code
    sessions[session_id] = session
    
    # Return success page with session info
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Authentication Successful</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            }}
            .success {{
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                text-align: center;
                max-width: 600px;
            }}
            h2 {{ color: #28a745; }}
            p {{ color: #666; margin: 20px 0; }}
            .code-box {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                font-family: monospace;
                margin: 20px 0;
                word-break: break-all;
            }}
            button {{
                background: #28a745;
                color: white;
                border: none;
                padding: 12px 30px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                margin-top: 20px;
            }}
            button:hover {{
                background: #218838;
            }}
        </style>
    </head>
    <body>
        <div class="success">
            <h2>✅ Authentication Successful!</h2>
            <p>You have been successfully authenticated.</p>
            <div class="code-box">
                <strong>Session ID:</strong><br>
                {session_id}
            </div>
            <p>Use this session ID in the <code>mcp-session-id</code> header for API calls.</p>
            <button onclick="window.location.href='/test'">Open Test Interface</button>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

@app.get("/test")
async def test_interface():
    """Serve a test interface for the MCP server"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MCP Server Test Interface</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
            }
            h1 { margin: 0; }
            .container {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }
            .panel {
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .full-width {
                grid-column: span 2;
            }
            input, textarea {
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 5px;
                font-family: monospace;
                margin: 10px 0;
            }
            button {
                background: #667eea;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                margin: 5px;
            }
            button:hover {
                background: #5a67d8;
            }
            .response {
                background: #1e1e1e;
                color: #d4d4d4;
                padding: 15px;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
                white-space: pre-wrap;
                max-height: 400px;
                overflow-y: auto;
                margin-top: 20px;
            }
            .status {
                padding: 10px;
                border-radius: 5px;
                margin: 10px 0;
            }
            .success { background: #d4edda; color: #155724; }
            .error { background: #f8d7da; color: #721c24; }
            .info { background: #d1ecf1; color: #0c5460; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 MCP Server Test Interface</h1>
            <p>Test your MCP server endpoints directly</p>
        </div>

        <div class="container">
            <div class="panel">
                <h3>🔐 Authentication</h3>
                <button onclick="window.location.href='/auth/start'">Start OAuth Flow</button>
                <p style="font-size: 14px; color: #666;">
                    Click to authenticate with OIDC. After login, you'll get a session ID.
                </p>
            </div>

            <div class="panel">
                <h3>📝 Session</h3>
                <input type="text" id="sessionId" placeholder="Session ID (optional)">
                <p style="font-size: 14px; color: #666;">
                    Enter session ID from auth callback or leave empty for new session.
                </p>
            </div>

            <div class="panel full-width">
                <h3>🧪 Quick Tests</h3>
                <button onclick="testInitialize()">Initialize</button>
                <button onclick="testListTools()">List Tools</button>
                <button onclick="88c4071c-a162-4d52-ac07-a68d142ea294()">Call Dummy Tool</button>
                <button onclick="testListGateways()">List Gateways</button>
            </div>

            <div class="panel full-width">
                <h3>📤 Custom Request</h3>
                <textarea id="customRequest" rows="10">{
  "jsonrpc": "2.0",
  "method": "initialize",
  "id": 1,
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "test", "version": "1.0"}
  }
}</textarea>
                <button onclick="sendCustomRequest()">Send Custom Request</button>
            </div>

            <div class="panel full-width">
                <h3>📥 Response</h3>
                <div id="status"></div>
                <div class="response" id="response">Ready to send requests...</div>
            </div>
        </div>

        <script>
            async function sendRequest(data) {
                const sessionId = document.getElementById('sessionId').value;
                const status = document.getElementById('status');
                const response = document.getElementById('response');
                
                status.className = 'status info';
                status.textContent = 'Sending request...';
                response.textContent = JSON.stringify(data, null, 2) + '\\n\\nWaiting for response...';
                
                try {
                    const headers = {
                        'Content-Type': 'application/json',
                        'Accept': 'text/event-stream'
                    };
                    
                    if (sessionId) {
                        headers['mcp-session-id'] = sessionId;
                    }
                    
                    const res = await fetch('/mcp', {
                        method: 'POST',
                        headers: headers,
                        body: JSON.stringify(data),
                        credentials: 'include'
                    });
                    
                    const text = await res.text();
                    
                    // Extract session ID from response headers if present
                    const newSessionId = res.headers.get('mcp-session-id');
                    if (newSessionId && !sessionId) {
                        document.getElementById('sessionId').value = newSessionId;
                        status.className = 'status success';
                        status.textContent = 'Success! Session ID: ' + newSessionId;
                    } else {
                        status.className = 'status success';
                        status.textContent = 'Request successful';
                    }
                    
                    response.textContent = text;
                    
                } catch (error) {
                    status.className = 'status error';
                    status.textContent = 'Error: ' + error.message;
                    response.textContent = 'Error: ' + error.message;
                }
            }

            function testInitialize() {
                sendRequest({
                    jsonrpc: "2.0",
                    method: "initialize",
                    id: 1,
                    params: {
                        protocolVersion: "2024-11-05",
                        capabilities: {},
                        clientInfo: {name: "test-client", version: "1.0"}
                    }
                });
            }

            function testListTools() {
                sendRequest({
                    jsonrpc: "2.0",
                    method: "tools/list",
                    id: 2
                });
            }

            function testDummyTool() {
                sendRequest({
                    jsonrpc: "2.0",
                    method: "tools/call",
                    id: 3,
                    params: {
                        name: "get_dummy_gateways_tool",
                        arguments: {}
                    }
                });
            }

            function testListGateways() {
                const compartmentId = prompt('Enter Compartment ID:', 'ocid1.compartment.oc1..aaaaaaaai2zzsg...');
                if (compartmentId) {
                    sendRequest({
                        jsonrpc: "2.0",
                        method: "tools/call",
                        id: 4,
                        params: {
                            name: "list_gateways_tool",
                            arguments: {
                                compartment_id: compartmentId
                            }
                        }
                    });
                }
            }

            function sendCustomRequest() {
                try {
                    const customData = JSON.parse(document.getElementById('customRequest').value);
                    sendRequest(customData);
                } catch (error) {
                    document.getElementById('status').className = 'status error';
                    document.getElementById('status').textContent = 'Invalid JSON: ' + error.message;
                }
            }
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    print("Starting Streamable HTTP MCP Server on http://0.0.0.0:8000", file=sys.stderr)
    print("OAuth endpoints:", file=sys.stderr)
    print("  - Start auth: http://0.0.0.0:8000/auth/start", file=sys.stderr)
    print("  - Callback: http://0.0.0.0:8000/auth/callback", file=sys.stderr)
    print("  - Test interface: http://0.0.0.0:8000/test", file=sys.stderr)
    print("  - MCP endpoint: http://0.0.0.0:8000/mcp", file=sys.stderr)
    uvicorn.run(app, host="0.0.0.0", port=8000)
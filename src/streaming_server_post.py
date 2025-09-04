#!/usr/bin/env python3
"""
Streamable HTTP MCP Server - POST version
Handles MCP protocol over HTTP POST with JSON body
"""

import json
import logging
import sys
import uuid
import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode

import uvicorn
import httpx
from fastapi import FastAPI, HTTPException, Request, Query, Response as FastAPIResponse, Cookie
from fastapi.responses import StreamingResponse, Response, RedirectResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from gateway_services import list_gateways, get_gateway, get_dumy_gateways_json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import OAuth Configuration
try:
    from oauth_config import OAUTH_CONFIG
    logger.info("OAuth configuration loaded from oauth_config.py")
except ImportError:
    logger.warning("oauth_config.py not found. Copy oauth_config_template.py to oauth_config.py and configure it.")
    # Fallback to empty config - server will fail on OAuth endpoints
    OAUTH_CONFIG = {
        "client_id": "",
        "client_secret": "",
        "authorization_endpoint": "",
        "token_endpoint": "",
        "redirect_uri": "",
        "scope": "",
        "audience": ""
    }

# JSON-RPC Models
class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

# MCP Tool Models
class Tool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]

# Enhanced Session Management with OAuth
class AuthSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        self.authenticated = False
        self.state = None  # For CSRF protection
        self.code_verifier = None  # For PKCE
        self.created_at = datetime.utcnow()
        self.last_accessed = datetime.utcnow()

class MCPSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.initialized = False
        self.capabilities = {}
        self.client_info = {}

# In-memory session stores
auth_sessions: Dict[str, AuthSession] = {}  # Keyed by session cookie
mcp_sessions: Dict[str, MCPSession] = {}    # Keyed by MCP session ID

app = FastAPI(title="MCP Streamable HTTP Server with OAuth")

# Add CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["mcp-session-id"]
)

# OAuth Helper Functions
def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge"""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge

def generate_state() -> str:
    """Generate CSRF protection state"""
    return secrets.token_urlsafe(32)

def create_auth_session() -> AuthSession:
    """Create a new authentication session"""
    session_id = secrets.token_urlsafe(32)
    session = AuthSession(session_id)
    auth_sessions[session_id] = session
    return session

def get_auth_session(session_id: str) -> Optional[AuthSession]:
    """Get an authentication session by ID"""
    session = auth_sessions.get(session_id)
    if session:
        session.last_accessed = datetime.utcnow()
        # Clean up old sessions (>1 hour idle)
        now = datetime.utcnow()
        expired = [sid for sid, s in auth_sessions.items() 
                  if (now - s.last_accessed).total_seconds() > 3600]
        for sid in expired:
            if sid != session_id:
                del auth_sessions[sid]
    return session

def validate_auth(request: Request) -> Optional[AuthSession]:
    """Validate authentication from request cookies or Authorization header"""
    
    # First check if there's a Bearer token in Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        # If API Gateway validated the token, we trust it
        # Create a temporary session for this request
        temp_session = AuthSession("bearer-validated")
        temp_session.authenticated = True
        temp_session.access_token = auth_header.replace("Bearer ", "")
        return temp_session
    
    # Otherwise check cookies
    session_id = request.cookies.get("mcp_auth_session")
    if not session_id:
        return None
    
    session = get_auth_session(session_id)
    if not session or not session.authenticated:
        return None
    
    # Check token expiry
    if session.token_expiry and datetime.utcnow() >= session.token_expiry:
        session.authenticated = False
        return None
    
    return session

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
        description="Get dummy gateways JSON for testing",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    )
]


def create_error_response(request_id: Optional[Union[str, int]], code: int, message: str) -> dict:
    """Create JSON-RPC error response"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message
        }
    }

def create_success_response(request_id: Optional[Union[str, int]], result: dict) -> dict:
    """Create JSON-RPC success response"""
    return {
        "jsonrpc": "2.0", 
        "id": request_id,
        "result": result
    }

async def handle_initialize(request: JSONRPCRequest, session: MCPSession) -> dict:
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
            "tools": {"listChanged": False}
        },
        "serverInfo": {
            "name": "oci_api_gateway",
            "version": "1.0.0"
        }
    }
    
    return create_success_response(request.id, result)

async def handle_tools_list(request: JSONRPCRequest, session: MCPSession) -> dict:
    """Handle tools/list method"""
    if not session.initialized:
        return create_error_response(request.id, -32600, "Session not initialized")
    
    tools_data = [tool.model_dump() for tool in AVAILABLE_TOOLS]
    result = {"tools": tools_data}
    
    return create_success_response(request.id, result)

async def handle_tools_call(request: JSONRPCRequest, session: MCPSession) -> dict:
    """Handle tools/call method"""
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
        error_result = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"error": str(e)})
                }
            ]
        }
        return create_success_response(request.id, error_result)

@app.post("/r2")
async def mcp_endpoint(
    request: Request
):
    """MCP endpoint - POST with JSON body"""
    try:
        # Check authentication for protected endpoints
        auth_session = validate_auth(request)
        if not auth_session:
            return JSONResponse(
                content={"error": "Authentication required", "auth_url": "/auth/start"},
                status_code=401,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Credentials": "true"
                }
            )
        
        # Get or create MCP session
        mcp_session_id = request.headers.get("mcp-session-id")
        if not mcp_session_id:
            mcp_session_id = str(uuid.uuid4())
            session = MCPSession(mcp_session_id)
            mcp_sessions[mcp_session_id] = session
        else:
            session = mcp_sessions.get(mcp_session_id)
            if not session:
                session = MCPSession(mcp_session_id)
                mcp_sessions[mcp_session_id] = session
        
        # Parse JSON-RPC request from POST body
        try:
            # Read JSON body
            json_data = await request.json()
            
            # Handle session_id if provided in the body (for compatibility)
            if "session_id" in json_data:
                mcp_session_id = json_data.pop("session_id", mcp_session_id)
            
            rpc_request = JSONRPCRequest(**json_data)
            
        except Exception as e:
            logger.error(f"Invalid JSON-RPC request: {e}")
            error_resp = create_error_response(None, -32700, f"Parse error: {str(e)}")
            return StreamingResponse(
                iter([json.dumps(error_resp)]),
                media_type="application/json",
                headers={
                    "mcp-session-id": mcp_session_id,
                    "Cache-Control": "no-cache",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type, Accept, mcp-session-id",
                    "Access-Control-Expose-Headers": "mcp-session-id"
                }
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
        
        # Return JSON response with streaming
        return StreamingResponse(
            iter([json.dumps(response_data)]),
            media_type="application/json",
            headers={
                "mcp-session-id": mcp_session_id,
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type, Accept, mcp-session-id",
                "Access-Control-Expose-Headers": "mcp-session-id"
            }
        )
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        error_resp = create_error_response(None, -32603, "Internal error")
        return StreamingResponse(
            iter([json.dumps(error_resp)]),
            media_type="application/json"
        )

@app.options("/r2")
async def r2_options():
    """Handle CORS preflight for /r2 endpoint"""
    return Response(
        content="",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept, mcp-session-id, Authorization",
            "Access-Control-Max-Age": "3600"
        }
    )

@app.post("/mcp")
async def mcp_endpoint_alt(
    request: Request
):
    """MCP endpoint - Alternative path for API Gateway"""
    return await mcp_endpoint(request)

@app.options("/mcp")
async def mcp_options():
    """Handle CORS preflight for /mcp endpoint"""
    return Response(
        content="",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept, mcp-session-id, Authorization",
            "Access-Control-Max-Age": "3600"
        }
    )

@app.get("/auth/start")
async def auth_start(response: FastAPIResponse):
    """Start OAuth authentication flow"""
    
    try:
        # Create new auth session
        session = create_auth_session()
        
        # Generate PKCE parameters
        code_verifier, code_challenge = generate_pkce_pair()
        session.code_verifier = code_verifier
        
        # Generate state for CSRF protection
        state = generate_state()
        session.state = state
        
        # Build authorization URL
        auth_params = {
            "response_type": "code",
            "client_id": OAUTH_CONFIG["client_id"],
            "redirect_uri": OAUTH_CONFIG["redirect_uri"],
            "scope": OAUTH_CONFIG["scope"],
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        
        # Log the parameters for debugging
        logger.info(f"OAuth params: client_id={OAUTH_CONFIG['client_id']}")
        logger.info(f"OAuth params: redirect_uri={OAUTH_CONFIG['redirect_uri']}")
        logger.info(f"OAuth params: scope={OAUTH_CONFIG['scope']}")
        
        auth_url = f"{OAUTH_CONFIG['authorization_endpoint']}?{urlencode(auth_params)}"
        
        logger.info(f"Full auth URL: {auth_url}")
        
        # Set session cookie
        response = RedirectResponse(url=auth_url, status_code=302)
        response.set_cookie(
            key="mcp_auth_session",
            value=session.session_id,
            httponly=True,
            secure=True,  # Required for HTTPS
            samesite="none",  # Allow cross-site cookies for OAuth flow
            max_age=3600,
            path="/"  # Ensure cookie is available for all paths
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error starting auth flow: {e}")
        raise HTTPException(status_code=500, detail="Failed to start authentication")

@app.get("/auth/callback")
async def auth_callback(
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    session_id: str = Cookie(None, alias="mcp_auth_session")
):
    """Handle OAuth callback and exchange code for token"""
    try:
        # Validate session
        if not session_id:
            raise HTTPException(status_code=400, detail="No session found")
        
        session = get_auth_session(session_id)
        if not session:
            raise HTTPException(status_code=400, detail="Invalid session")
        
        # Validate state (CSRF protection)
        logger.info(f"Session state: {session.state}")
        logger.info(f"Received state: {state}")
        
        # IDCS might append additional data to state with semicolon
        received_state = state.split(';')[0] if ';' in state else state
        
        if session.state != received_state:
            logger.error(f"State mismatch: expected {session.state}, got {received_state}")
            raise HTTPException(status_code=400, detail=f"Invalid state parameter: expected {session.state}, got {received_state}")
        
        # Exchange authorization code for token
        async with httpx.AsyncClient() as client:
            # Prepare Basic Auth for client credentials
            import base64
            client_creds = f"{OAUTH_CONFIG['client_id']}:{OAUTH_CONFIG['client_secret']}"
            client_creds_b64 = base64.b64encode(client_creds.encode()).decode()
            
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": OAUTH_CONFIG["redirect_uri"],
                "code_verifier": session.code_verifier
                # IDCS ignores audience for authorization_code grant
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {client_creds_b64}"
            }
            
            logger.info(f"Exchanging code for token at: {OAUTH_CONFIG['token_endpoint']}")
            
            token_response = await client.post(
                OAUTH_CONFIG["token_endpoint"],
                data=token_data,
                headers=headers
            )
            
            if token_response.status_code != 200:
                logger.error(f"Token exchange failed: {token_response.text}")
                raise HTTPException(status_code=400, detail="Token exchange failed")
            
            token_info = token_response.json()
            
            # Store tokens in session
            session.access_token = token_info.get("access_token")
            session.refresh_token = token_info.get("refresh_token")
            expires_in = token_info.get("expires_in", 3600)
            session.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
            session.authenticated = True
            
            # Clear PKCE and state
            session.code_verifier = None
            session.state = None
            
            # Return success HTML directly with token info and MCP initialize button
            return HTMLResponse(content=f"""
                <html>
                    <head>
                        <title>Authentication Successful</title>
                        <script>
                            // Get cookie value by name
                            function getCookie(name) {{
                                const value = `; ${{document.cookie}}`;
                                const parts = value.split(`; ${{name}}=`);
                                if (parts.length === 2) return parts.pop().split(';').shift();
                                return null;
                            }}
                            
                            async function initializeMCP() {{
                                const btn = document.getElementById('initBtn');
                                const result = document.getElementById('initResult');
                                
                                btn.disabled = true;
                                result.innerHTML = 'Initializing MCP session...';
                                
                                try {{
                                    const payload = {{
                                        jsonrpc: "2.0",
                                        method: "initialize",
                                        params: {{
                                            protocolVersion: "1.0.0",
                                            capabilities: {{}},
                                            clientInfo: {{
                                                name: "oauth-client",
                                                version: "1.0"
                                            }}
                                        }},
                                        id: 1
                                    }};
                                    
                                    const response = await fetch('https://odhtce4qlvkvbgbg3nacivcyxq.apigateway.us-ashburn-1.oci.oc-test.com/mcp/r2', {{
                                        method: 'POST',
                                        headers: {{
                                            'Content-Type': 'application/json',
                                            'Authorization': 'Bearer {session.access_token}'
                                        }},
                                        body: JSON.stringify(payload)
                                    }});
                                    
                                    const sessionId = response.headers.get('mcp-session-id');
                                    const data = await response.json();
                                    
                                    if (data.result) {{
                                        // Store MCP session ID in cookie
                                        if (sessionId) {{
                                            document.cookie = `mcp_session_id=${{sessionId}}; path=/; max-age=3600; SameSite=None; Secure`;
                                        }}
                                        
                                        result.innerHTML = `
                                            <div style="background: #d4edda; padding: 15px; border-radius: 5px; margin-top: 10px;">
                                                <strong>✅ MCP Session Initialized!</strong><br>
                                                Session ID: ${{sessionId}}<br>
                                                Protocol Version: ${{data.result.protocolVersion}}<br>
                                                Server: ${{data.result.serverInfo.name}} v${{data.result.serverInfo.version}}
                                            </div>
                                        `;
                                        
                                        // Show the tool buttons now that we have a session
                                        document.getElementById('toolButtons').style.display = 'block';
                                    }} else {{
                                        result.innerHTML = `<div style="background: #f8d7da; padding: 15px; border-radius: 5px; margin-top: 10px;">Error: ${{JSON.stringify(data.error || data)}}</div>`;
                                    }}
                                }} catch (error) {{
                                    result.innerHTML = `<div style="background: #f8d7da; padding: 15px; border-radius: 5px; margin-top: 10px;">Failed to initialize: ${{error.message}}</div>`;
                                }} finally {{
                                    btn.disabled = false;
                                }}
                            }}
                            
                            async function callMCPTool(toolName, args = {{}}) {{
                                const result = document.getElementById('toolResult');
                                const mcp_session_id = getCookie('mcp_session_id');
                                
                                if (!mcp_session_id) {{
                                    result.innerHTML = '<div style="background: #f8d7da; padding: 15px; border-radius: 5px;">Please initialize MCP session first!</div>';
                                    return;
                                }}
                                
                                result.innerHTML = 'Calling tool...';
                                
                                try {{
                                    const payload = {{
                                        jsonrpc: "2.0",
                                        method: "tools/call",
                                        params: {{
                                            name: toolName,
                                            arguments: args
                                        }},
                                        id: Date.now()
                                    }};
                                    
                                    const response = await fetch('https://odhtce4qlvkvbgbg3nacivcyxq.apigateway.us-ashburn-1.oci.oc-test.com/mcp/r2', {{
                                        method: 'POST',
                                        headers: {{
                                            'Content-Type': 'application/json',
                                            'Authorization': 'Bearer {session.access_token}',
                                            'mcp-session-id': mcp_session_id
                                        }},
                                        body: JSON.stringify(payload)
                                    }});
                                    
                                    const data = await response.json();
                                    
                                    if (data.result) {{
                                        const content = data.result.content[0].text;
                                        result.innerHTML = `
                                            <div style="background: #d4edda; padding: 15px; border-radius: 5px;">
                                                <strong>✅ Tool Result:</strong>
                                                <pre style="overflow-x: auto; background: white; padding: 10px; border-radius: 3px; margin-top: 10px;">${{content}}</pre>
                                            </div>
                                        `;
                                    }} else {{
                                        result.innerHTML = `<div style="background: #f8d7da; padding: 15px; border-radius: 5px;">Error: ${{JSON.stringify(data.error || data)}}</div>`;
                                    }}
                                }} catch (error) {{
                                    result.innerHTML = `<div style="background: #f8d7da; padding: 15px; border-radius: 5px;">Failed to call tool: ${{error.message}}</div>`;
                                }}
                            }}
                            
                            async function getDummyGateways() {{
                                await callMCPTool('get_dummy_gateways_tool');
                            }}
                            
                            async function listTools() {{
                                const result = document.getElementById('toolResult');
                                const mcp_session_id = getCookie('mcp_session_id');
                                
                                if (!mcp_session_id) {{
                                    result.innerHTML = '<div style="background: #f8d7da; padding: 15px; border-radius: 5px;">Please initialize MCP session first!</div>';
                                    return;
                                }}
                                
                                result.innerHTML = 'Fetching available tools...';
                                
                                try {{
                                    const payload = {{
                                        jsonrpc: "2.0",
                                        method: "tools/list",
                                        id: Date.now()
                                    }};
                                    
                                    const response = await fetch('https://odhtce4qlvkvbgbg3nacivcyxq.apigateway.us-ashburn-1.oci.oc-test.com/mcp/r2', {{
                                        method: 'POST',
                                        headers: {{
                                            'Content-Type': 'application/json',
                                            'Authorization': 'Bearer {session.access_token}',
                                            'mcp-session-id': mcp_session_id
                                        }},
                                        body: JSON.stringify(payload)
                                    }});
                                    
                                    const data = await response.json();
                                    
                                    if (data.result) {{
                                        const tools = data.result.tools;
                                        result.innerHTML = `
                                            <div style="background: #d4edda; padding: 15px; border-radius: 5px;">
                                                <strong>✅ Available Tools:</strong>
                                                <ul style="margin-top: 10px;">
                                                    ${{tools.map(tool => `<li><strong>${{tool.name}}</strong>: ${{tool.description}}</li>`).join('')}}
                                                </ul>
                                            </div>
                                        `;
                                    }} else {{
                                        result.innerHTML = `<div style="background: #f8d7da; padding: 15px; border-radius: 5px;">Error: ${{JSON.stringify(data.error || data)}}</div>`;
                                    }}
                                }} catch (error) {{
                                    result.innerHTML = `<div style="background: #f8d7da; padding: 15px; border-radius: 5px;">Failed to list tools: ${{error.message}}</div>`;
                                }}
                            }}
                        </script>
                    </head>
                    <body style="font-family: sans-serif; padding: 50px; max-width: 800px; margin: 0 auto;">
                        <h1>✅ Authentication Successful!</h1>
                        <p>You have been successfully authenticated.</p>
                        
                        <div style="background: #f0f0f0; padding: 20px; border-radius: 5px; margin: 20px 0;">
                            <h3>Your Access Token:</h3>
                            <textarea readonly style="width: 100%; height: 100px; font-family: monospace; font-size: 12px;">{session.access_token}</textarea>
                            <p><small>This token expires at: {session.token_expiry.isoformat() if session.token_expiry else 'Unknown'}</small></p>
                        </div>
                        
                        <div style="background: #fff3cd; padding: 20px; border-radius: 5px; margin: 20px 0;">
                            <h3>Initialize MCP Session</h3>
                            <p>Click the button below to initialize an MCP session using your access token:</p>
                            <button id="initBtn" onclick="initializeMCP()" style="padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">
                                Initialize MCP Session
                            </button>
                            <div id="initResult"></div>
                        </div>
                        
                        <div id="toolButtons" style="background: #e7f3ff; padding: 20px; border-radius: 5px; margin: 20px 0; display: none;">
                            <h3>MCP Tools</h3>
                            <p>Use these tools to interact with the MCP server:</p>
                            <button onclick="listTools()" style="padding: 10px 20px; background: #17a2b8; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; margin: 5px;">
                                List Available Tools
                            </button>
                            <button onclick="getDummyGateways()" style="padding: 10px 20px; background: #6c757d; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; margin: 5px;">
                                Get Dummy Gateways
                            </button>
                            <div id="toolResult" style="margin-top: 15px;"></div>
                        </div>
                        
                        <div style="background: #e8f4f8; padding: 20px; border-radius: 5px; margin: 20px 0;">
                            <h3>How to use the token:</h3>
                            <p>Include this token in the Authorization header when calling protected endpoints:</p>
                            <code style="background: white; padding: 10px; display: block; border-radius: 3px;">
                                Authorization: Bearer YOUR_TOKEN_HERE
                            </code>
                        </div>
                        
                        <div style="margin-top: 30px;">
                            <a href="/mcp_no_auth/auth/status" style="display: inline-block; margin: 10px; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px;">Check Auth Status</a>
                            <p>Use this token to access protected MCP endpoints.</p>
                        </div>
                    </body>
                </html>
            """)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in auth callback: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")


@app.get("/auth/status")
async def auth_status(session_id: str = Cookie(None, alias="mcp_auth_session")):
    """Check authentication status"""
    session = get_auth_session(session_id) if session_id else None
    
    if not session:
        return JSONResponse(
            content={"authenticated": False, "message": "No session"},
            status_code=200
        )
    
    if not session.authenticated:
        return JSONResponse(
            content={"authenticated": False, "message": "Not authenticated"},
            status_code=200
        )
    
    # Check token expiry
    if session.token_expiry and datetime.utcnow() >= session.token_expiry:
        session.authenticated = False
        return JSONResponse(
            content={"authenticated": False, "message": "Token expired"},
            status_code=200
        )
    
    return JSONResponse(
        content={
            "authenticated": True,
            "expires_at": session.token_expiry.isoformat() if session.token_expiry else None,
            "access_token": session.access_token  # Include token for client to use
        }
    )

@app.post("/auth/logout")
async def auth_logout(
    response: FastAPIResponse,
    session_id: str = Cookie(None, alias="mcp_auth_session")
):
    """Logout and clear session"""
    if session_id and session_id in auth_sessions:
        del auth_sessions[session_id]
    
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie("mcp_auth_session")
    return response

@app.get("/")
async def serve_client():
    """Serve the OAuth test client HTML"""
    import os
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "oauth-client.html")
    if os.path.exists(html_path):
        with open(html_path, "r") as f:
            content = f.read()
        return HTMLResponse(content=content)
    else:
        return HTMLResponse(content="<h1>OAuth client not found. Please create oauth-client.html</h1>")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "auth_sessions": len(auth_sessions),
        "mcp_sessions": len(mcp_sessions)
    }

@app.get("/test")
async def test_endpoint(request: Request):
    """Test endpoint to verify request details"""
    return {
        "message": "Test endpoint working",
        "headers": dict(request.headers),
        "cookies": request.cookies,
        "url": str(request.url)
    }

if __name__ == "__main__":
    print("Starting MCP Server (POST version) with OAuth on http://0.0.0.0:8000", file=sys.stderr)
    print("\nOAuth endpoints:", file=sys.stderr)
    print("  - http://0.0.0.0:8000/auth/start    - Start OAuth flow", file=sys.stderr)
    print("  - http://0.0.0.0:8000/auth/callback - OAuth callback", file=sys.stderr)
    print("  - http://0.0.0.0:8000/auth/status   - Check auth status", file=sys.stderr)
    print("  - http://0.0.0.0:8000/auth/logout   - Logout", file=sys.stderr)
    print("\nMCP endpoints (POST only, protected):", file=sys.stderr)
    print("  - POST http://0.0.0.0:8000/r2  - MCP endpoint", file=sys.stderr)
    print("  - POST http://0.0.0.0:8000/mcp - Alternative MCP endpoint", file=sys.stderr)
    print("\nOther endpoints:", file=sys.stderr)
    print("  - GET http://0.0.0.0:8000/       - OAuth test client", file=sys.stderr)
    print("  - GET http://0.0.0.0:8000/health - Health check", file=sys.stderr)
    print("\n⚠️  Note: This server accepts POST requests with JSON body for MCP endpoints", file=sys.stderr)
    uvicorn.run(app, host="0.0.0.0", port=8000)
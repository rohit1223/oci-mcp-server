#!/usr/bin/env python3
"""
Streamable HTTP MCP Server - No Authentication Version
Handles MCP protocol over HTTP GET with query parameters
WARNING: This version has NO AUTHENTICATION - use only in secure/internal environments
"""

import json
import logging
import sys
import uuid
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Query, Response as FastAPIResponse
from fastapi.responses import StreamingResponse, Response, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

# MCP Session Storage (in-memory for simplicity)
class MCPSession:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.created_at = datetime.now()
        self.initialized = False
        self.capabilities = {}
        self.client_info = {}

mcp_sessions: Dict[str, MCPSession] = {}

# Initialize FastAPI app
app = FastAPI(
    title="MCP Server - No Auth",
    description="Model Context Protocol Server without authentication",
    version="1.0.0"
)

# Add CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["mcp-session-id"]
)

def create_mcp_session() -> MCPSession:
    """Create a new MCP session"""
    session = MCPSession()
    mcp_sessions[session.id] = session
    logger.info(f"Created MCP session: {session.id}")
    return session

def get_mcp_session(session_id: Optional[str]) -> Optional[MCPSession]:
    """Get MCP session by ID"""
    if not session_id:
        return None
    return mcp_sessions.get(session_id)

async def generate_sse_stream(response: JSONRPCResponse, session_id: Optional[str] = None) -> AsyncGenerator[bytes, None]:
    """
    Generate SSE (Server-Sent Events) stream for MCP responses
    Format: "event: <event_name>\ndata: <json_data>\n\n"
    """
    # Send session ID as first event if available
    if session_id:
        yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n".encode('utf-8')
        await asyncio.sleep(0.01)  # Small delay for demonstration
    
    # Send the main response data
    response_json = response.model_dump_json(exclude_none=True)
    yield f"event: message\ndata: {response_json}\n\n".encode('utf-8')
    await asyncio.sleep(0.01)
    
    # Send completion event
    yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n".encode('utf-8')

async def handle_initialize(params: Dict[str, Any], session: MCPSession) -> Dict[str, Any]:
    """Handle MCP initialization"""
    logger.info(f"Initializing MCP session {session.id}")
    
    session.initialized = True
    session.capabilities = params.get("capabilities", {})
    session.client_info = params.get("clientInfo", {})
    
    return {
        "protocolVersion": "1.0.0",
        "capabilities": {
            "tools": {}
        },
        "serverInfo": {
            "name": "oci-mcp-server-noauth",
            "version": "1.0.0"
        }
    }

async def handle_tools_list() -> Dict[str, Any]:
    """List available tools"""
    tools = [
        {
            "name": "list_gateways_tool",
            "description": "List all API Gateways in a compartment",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "compartment_id": {
                        "type": "string",
                        "description": "The OCID of the compartment"
                    }
                },
                "required": ["compartment_id"]
            }
        },
        {
            "name": "get_gateway_tool",
            "description": "Get details of a specific API Gateway",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "gateway_id": {
                        "type": "string",
                        "description": "The OCID of the gateway"
                    }
                },
                "required": ["gateway_id"]
            }
        },
        {
            "name": "get_dummy_gateways_tool",
            "description": "Get dummy gateway data for testing",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        }
    ]
    return {"tools": tools}

async def handle_tools_call(params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool call"""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    logger.info(f"Executing tool: {tool_name} with args: {arguments}")
    
    try:
        if tool_name == "list_gateways_tool":
            compartment_id = arguments.get("compartment_id")
            if not compartment_id:
                raise ValueError("compartment_id is required")
            gateways = list_gateways(compartment_id)
            return {"content": [{"type": "text", "text": json.dumps({"gateways": gateways})}]}
            
        elif tool_name == "get_gateway_tool":
            gateway_id = arguments.get("gateway_id")
            if not gateway_id:
                raise ValueError("gateway_id is required")
            gateway = get_gateway(gateway_id)
            return {"content": [{"type": "text", "text": json.dumps({"gateway": gateway})}]}
            
        elif tool_name == "get_dummy_gateways_tool":
            dummy_data = get_dumy_gateways_json()
            return {"content": [{"type": "text", "text": json.dumps(dummy_data)}]}
            
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
            
    except Exception as e:
        logger.error(f"Tool execution failed: {str(e)}", exc_info=True)
        return {"error": {"code": -32603, "message": str(e)}}

async def process_request(request_data: JSONRPCRequest, session_id: Optional[str]) -> tuple[JSONRPCResponse, str]:
    """Process a JSON-RPC request"""
    method = request_data.method
    params = request_data.params or {}
    
    logger.info(f"Processing method: {method}, session: {session_id}")
    
    try:
        # Handle different methods
        if method == "initialize":
            # Initialize creates a new session, doesn't require existing one
            session = create_mcp_session()
            result = await handle_initialize(params, session)
            return JSONRPCResponse(
                jsonrpc="2.0",
                result=result,
                id=request_data.id
            ), session.id  # Return the new session ID
            
        # All other methods require a valid session
        elif method in ["tools/list", "tools/call"]:
            # Check if session_id was provided
            if not session_id:
                return JSONRPCResponse(
                    jsonrpc="2.0",
                    error={
                        "code": -32002,
                        "message": "Session ID required. Call initialize first to get a session."
                    },
                    id=request_data.id
                ), session_id or ""

            # Verify if session exists in memory
            session = mcp_sessions.get(session_id)
            if not session:
                return JSONRPCResponse(
                    jsonrpc="2.0",
                    error={
                        "code": -32002,
                        "message": f"Invalid session ID: {session_id}. Call initialize first."
                    },
                    id=request_data.id
                ), session_id or ""

            # Check if initialize was called on this session
            if not session.initialized:
                return JSONRPCResponse(
                    jsonrpc="2.0",
                    error={
                        "code": -32002,
                        "message": "Session not initialized. Call initialize first."
                    },
                    id=request_data.id
                ), session_id or ""
            
            # Execute the method
            if method == "tools/list":
                result = await handle_tools_list()
            else:  # tools/call
                result = await handle_tools_call(params)
            
            return JSONRPCResponse(
                jsonrpc="2.0",
                result=result,
                id=request_data.id
            ), session_id 
            
        else:
            # Handle unrecognized methods
            return JSONRPCResponse(
                jsonrpc="2.0",
                error={
                    "code": -32601,
                    "message": f"Method not found: {method}"
                },
                id=request_data.id
            ), None

    # Catch all unhandled exceptions
    except Exception as e:
        logger.error(f"Request processing failed: {str(e)}", exc_info=True)
        return JSONRPCResponse(
            jsonrpc="2.0",
            error={
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            },
            id=request_data.id
        ), None

@app.get("/mcp")
async def mcp_endpoint(
    request: Request,
    payload: Optional[str] = Query(None, description="JSON-RPC request as JSON string"),
    jsonrpc: Optional[str] = Query(None, description="JSON-RPC version"),
    method: Optional[str] = Query(None, description="Method name"),
    id: Optional[Union[str, int]] = Query(None, description="Request ID"),
    params: Optional[str] = Query(None, description="Method parameters as JSON string"),
    session_id: Optional[str] = Query(None, description="MCP session ID (optional for initialize)")
):
    """
    MCP endpoint - Session ID required except for initialize
    Accepts JSON-RPC requests via query parameters
    """
    
    try:
        # Build request from query params or payload
        if payload:
            request_dict = json.loads(payload)
        else:
            request_dict = {
                "jsonrpc": jsonrpc or "2.0",
                "method": method,
                "id": id
            }
            if params:
                request_dict["params"] = json.loads(params)
        
        # Process request
        request_obj = JSONRPCRequest(**request_dict)
        response, session_id = await process_request(request_obj, session_id)
        
        # Return SSE streaming response
        return StreamingResponse(
            generate_sse_stream(response, session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
                "mcp-session-id": session_id if session_id else ""
            }
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid JSON: {str(e)}"}
        )
    except Exception as e:
        logger.error(f"Request failed: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.post("/mcp")
async def mcp_endpoint_post(
    request: Request,
    body: JSONRPCRequest,
    session_id: Optional[str] = Query(None, description="MCP session ID (optional for initialize)")
):
    """
    MCP endpoint (POST) - Session ID required except for initialize
    Accepts JSON-RPC requests in request body
    """
    
    try:
        # Process request
        response, session_id = await process_request(body, session_id)
        
        # Return SSE streaming response
        return StreamingResponse(
            generate_sse_stream(response, session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
                "mcp-session-id": session_id if session_id else ""
            }
        )
        
    except Exception as e:
        logger.error(f"Request failed: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "sessions": len(mcp_sessions)
    }

@app.get("/")
async def root():
    """Root endpoint with test interface"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MCP Server - No Auth</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
            .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
            button { padding: 10px 20px; margin: 5px; cursor: pointer; }
            .success { color: green; }
            .error { color: red; }
            .warning { background-color: #fff3cd; padding: 10px; border: 1px solid #ffc107; border-radius: 5px; }
            pre { background: #f4f4f4; padding: 10px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MCP Server - No Authentication</h1>
                    
            <div class="section">
                <h2>Test MCP Tools</h2>
                <button onclick="initializeMCP()">1. Initialize MCP</button>
                <button onclick="listTools()">2. List Tools</button>
                <button onclick="callDummyTool()">3. Call Dummy Gateway Tool</button>
                <div id="result"></div>
            </div>
            
            <div class="section">
                <h2>Session Info</h2>
                <div id="sessionInfo">No active session</div>
            </div>
        </div>
        
        <script>
            let sessionId = null;
            
            async function initializeMCP() {
                try {
                    const params = {
                        protocolVersion: "1.0.0",
                        capabilities: {},
                        clientInfo: { name: "web-test", version: "1.0" }
                    };
                    
                    const response = await fetch(`/mcp?jsonrpc=2.0&method=initialize&params=${encodeURIComponent(JSON.stringify(params))}&id=1`);
                    const data = await response.json();
                    
                    // Get session ID from header
                    sessionId = response.headers.get('mcp-session-id');
                    
                    document.getElementById('result').innerHTML = `<pre class="success">${JSON.stringify(data, null, 2)}</pre>`;
                    document.getElementById('sessionInfo').innerHTML = `Session ID: ${sessionId}`;
                } catch (error) {
                    document.getElementById('result').innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            }
            
            async function listTools() {
                try {
                    const url = sessionId 
                        ? `/mcp?jsonrpc=2.0&method=tools/list&id=2&session_id=${sessionId}`
                        : `/mcp?jsonrpc=2.0&method=tools/list&id=2`;
                        
                    const response = await fetch(url);
                    const data = await response.json();
                    
                    document.getElementById('result').innerHTML = `<pre class="success">${JSON.stringify(data, null, 2)}</pre>`;
                } catch (error) {
                    document.getElementById('result').innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            }
            
            async function callDummyTool() {
                try {
                    const params = {
                        name: "get_dummy_gateways_tool",
                        arguments: {}
                    };
                    
                    const url = sessionId
                        ? `/mcp?jsonrpc=2.0&method=tools/call&params=${encodeURIComponent(JSON.stringify(params))}&id=3&session_id=${sessionId}`
                        : `/mcp?jsonrpc=2.0&method=tools/call&params=${encodeURIComponent(JSON.stringify(params))}&id=3`;
                        
                    const response = await fetch(url);
                    const data = await response.json();
                    
                    document.getElementById('result').innerHTML = `<pre class="success">${JSON.stringify(data, null, 2)}</pre>`;
                } catch (error) {
                    document.getElementById('result').innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Starting MCP Server - NO AUTHENTICATION VERSION")
    logger.info("WARNING: This server has no authentication!")
    logger.info("Use only in secure/internal environments")
    logger.info("=" * 50)
    logger.info("Server running at http://0.0.0.0:8000")
    logger.info("Test interface at http://localhost:8000/")
    logger.info("MCP endpoint at http://localhost:8000/mcp")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
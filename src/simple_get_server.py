#!/usr/bin/env python3
"""
Simplified GET-based MCP Server following streaming_server.py structure
"""

import json
import logging
import sys
import uuid
from typing import Any, Dict, List, Optional, Union

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, Response
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

# MCP Tool Models
class Tool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]

# Session Management
class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.initialized = False
        self.capabilities = {}
        self.client_info = {}

# In-memory session store
sessions: Dict[str, Session] = {}

app = FastAPI(title="MCP GET Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["mcp-session-id"]
)

# Available tools (same as streaming server)
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

def create_success_response(request_id: Optional[Union[str, int]], result: dict) -> dict:
    """Create JSON-RPC success response"""
    return {
        "jsonrpc": "2.0", 
        "id": request_id,
        "result": result
    }

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
            "tools": {"listChanged": False}
        },
        "serverInfo": {
            "name": "oci_api_gateway",
            "version": "1.0.0"
        }
    }
    
    return create_success_response(request.id, result)

async def handle_tools_list(request: JSONRPCRequest, session: Session) -> dict:
    """Handle tools/list method"""
    if not session.initialized:
        return create_error_response(request.id, -32600, "Session not initialized")
    
    tools_data = [tool.model_dump() for tool in AVAILABLE_TOOLS]
    result = {"tools": tools_data}
    
    return create_success_response(request.id, result)

async def handle_tools_call(request: JSONRPCRequest, session: Session) -> dict:
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
        # Call the actual tool functions (same as streaming server)
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

@app.get("/mcp")
async def mcp_get_endpoint(
    request: Request,
    jsonrpc: Optional[str] = Query("2.0", description="JSON-RPC version"),
    method: Optional[str] = Query(None, description="Method name"),
    id: Optional[Union[str, int]] = Query(None, description="Request ID"),
    params: Optional[str] = Query(None, description="Method parameters as JSON string")
):
    """MCP GET endpoint - similar to streaming server but GET only"""
    try:
        # Get or create session (same pattern as streaming server)
        session_id = request.headers.get("mcp-session-id")
        if not session_id:
            session_id = str(uuid.uuid4())
            session = Session(session_id)
            sessions[session_id] = session
        else:
            session = sessions.get(session_id)
            if not session:
                session = Session(session_id)
                sessions[session_id] = session
        
        # Parse JSON-RPC request from query parameters
        if not method:
            return StreamingResponse(
                iter([json.dumps(create_error_response(None, -32600, "Missing method"))]),
                media_type="application/json",
                headers={"mcp-session-id": session_id}
            )
        
        # Parse parameters
        parsed_params = None
        if params:
            try:
                parsed_params = json.loads(params)
            except:
                return StreamingResponse(
                    iter([json.dumps(create_error_response(id, -32700, "Parse error"))]),
                    media_type="application/json",
                    headers={"mcp-session-id": session_id}
                )
        
        # Create request object
        rpc_request = JSONRPCRequest(
            jsonrpc=jsonrpc,
            method=method,
            id=id,
            params=parsed_params
        )
        
        # Route to appropriate handler (same as streaming server)
        if rpc_request.method == "initialize":
            response_data = await handle_initialize(rpc_request, session)
        elif rpc_request.method == "tools/list":
            response_data = await handle_tools_list(rpc_request, session)
        elif rpc_request.method == "tools/call":
            response_data = await handle_tools_call(rpc_request, session)
        else:
            response_data = create_error_response(rpc_request.id, -32601, f"Method not found: {rpc_request.method}")
        
        # Return JSON response (simplified from SSE)
        return StreamingResponse(
            iter([json.dumps(response_data)]),
            media_type="application/json",
            headers={
                "mcp-session-id": session_id,
                "Access-Control-Allow-Origin": "*",
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

@app.options("/mcp")
async def mcp_options():
    """Handle CORS preflight for /mcp endpoint"""
    return Response(
        content="",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept, mcp-session-id",
            "Access-Control-Max-Age": "3600"
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "sessions": len(sessions)}

if __name__ == "__main__":
    print("Starting MCP GET Server on http://0.0.0.0:8000", file=sys.stderr)
    print("MCP endpoint: http://0.0.0.0:8000/mcp", file=sys.stderr) 
    print("Health check: http://0.0.0.0:8000/health", file=sys.stderr)
    uvicorn.run(app, host="0.0.0.0", port=8000)
#!/bin/bash

echo "=== Testing Streamable HTTP MCP Server ==="
echo "Server endpoint: http://127.0.0.1:8000/mcp"
echo ""

BASE_URL="http://127.0.0.1:8000/mcp"

echo "Test 1: Initialize MCP Session"
echo "============================="
INIT_RESPONSE=$(curl -s -D - -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": "1",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "curl-test-client",
        "version": "1.0.0"
      }
    }
  }')

SESSION_ID=$(echo "$INIT_RESPONSE" | grep -i "mcp-session-id:" | cut -d' ' -f2 | tr -d '\r')
INIT_DATA=$(echo "$INIT_RESPONSE" | grep "data:" | head -1)

echo "Session ID: $SESSION_ID"
echo "Initialize Response: $INIT_DATA"

if [ -n "$SESSION_ID" ]; then
    echo "✅ Initialization successful"
else
    echo "❌ Initialization failed"
    exit 1
fi

echo ""
echo "Test 2: List Available Tools"
echo "============================"
TOOLS_RESPONSE=$(curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0", 
    "method": "tools/list",
    "id": "2"
  }')

echo "Tools Response: $TOOLS_RESPONSE"

if echo "$TOOLS_RESPONSE" | grep -q '"tools"'; then
    echo "✅ Tools list successful"
else
    echo "❌ Tools list failed"
fi

echo ""
echo "Test 3: List Tools with Parameters (cursor: null)"
echo "================================================"
TOOLS_PARAMS_RESPONSE=$(curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list", 
    "id": "3",
    "params": {
      "cursor": null
    }
  }')

echo "Tools with Params Response: $TOOLS_PARAMS_RESPONSE"

if echo "$TOOLS_PARAMS_RESPONSE" | grep -q '"tools"'; then
    echo "✅ Tools list with parameters successful"
else
    echo "❌ Tools list with parameters failed"
fi

echo ""
echo "Test 4: Call list_gateways_tool"
echo "==============================="
CALL_RESPONSE=$(curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": "4",
    "params": {
      "name": "list_gateways_tool",
      "arguments": {
        "compartment_id": "ocid1.compartment.oc1..aaaaaaaaXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
      }
    }
  }')

echo "Tool Call Response: $CALL_RESPONSE"

if echo "$CALL_RESPONSE" | grep -q '"content"'; then
    echo "✅ Tool call successful"
else
    echo "❌ Tool call failed"
fi

echo ""
echo "Test 5: Health Check"
echo "==================="
HEALTH_RESPONSE=$(curl -s http://127.0.0.1:8000/health)
echo "Health Response: $HEALTH_RESPONSE"

echo ""
echo "=== Streaming HTTP Server Test Complete ==="
echo "Replace XXXXXXX placeholders with actual OCI resource IDs for real testing."
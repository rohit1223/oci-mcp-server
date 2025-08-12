#!/usr/bin/env python3
"""
Debug script to test MCP protocol directly
"""
import json
import logging
from mcp.types import ListToolsRequest, PaginatedRequestParams

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def test_validation():
    print("=== Testing MCP ListToolsRequest Validation ===")
    
    # Test 1: Valid request with null params
    try:
        request1 = ListToolsRequest(
            jsonrpc="2.0",
            id=1,
            method="tools/list",
            params=None
        )
        print("✅ Test 1 PASSED: ListToolsRequest with params=None")
        print(f"   Serialized: {request1.model_dump(by_alias=True, mode='json', exclude_none=True)}")
    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}")
    
    # Test 2: Valid request with empty PaginatedRequestParams
    try:
        request2 = ListToolsRequest(
            jsonrpc="2.0",
            id=2,
            method="tools/list",
            params=PaginatedRequestParams()
        )
        print("✅ Test 2 PASSED: ListToolsRequest with empty PaginatedRequestParams")
        print(f"   Serialized: {request2.model_dump(by_alias=True, mode='json', exclude_none=True)}")
    except Exception as e:
        print(f"❌ Test 2 FAILED: {e}")
    
    # Test 3: Valid request with cursor
    try:
        request3 = ListToolsRequest(
            jsonrpc="2.0",
            id=3,
            method="tools/list",
            params=PaginatedRequestParams(cursor="test-cursor")
        )
        print("✅ Test 3 PASSED: ListToolsRequest with cursor")
        print(f"   Serialized: {request3.model_dump(by_alias=True, mode='json', exclude_none=True)}")
    except Exception as e:
        print(f"❌ Test 3 FAILED: {e}")
    
    # Test 4: Invalid request with empty dict params
    try:
        # This should fail validation
        raw_data = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/list",
            "params": {}
        }
        request4 = ListToolsRequest.model_validate(raw_data)
        print("✅ Test 4 PASSED: ListToolsRequest with empty dict params")
        print(f"   Serialized: {request4.model_dump(by_alias=True, mode='json', exclude_none=True)}")
    except Exception as e:
        print(f"❌ Test 4 FAILED (expected): {e}")

if __name__ == "__main__":
    test_validation()
import sys
from typing import Any, Dict
from mcp.server.fastmcp import FastMCP
from gateway_services import list_gateways, get_gateway

mcp = FastMCP(name="oci_api_gateway")

@mcp.tool()
def list_gateways_tool(compartment_id: str) -> Dict[str, Any]:
    try:
        print(f"Listing gateways for compartment: {compartment_id}", file=sys.stderr)
        gateways = list_gateways(compartment_id)
        return {"gateways": gateways}
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return {"error": str(e)}

@mcp.tool()
def get_gateway_tool(gateway_id: str) -> Dict[str, Any]:
    try:
        print(f"Getting gateway details for ID: {gateway_id}", file=sys.stderr)
        gateway = get_gateway(gateway_id)
        return {"gateway": gateway}
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return {"error": str(e)}

if __name__ == "__main__":
    print("Running server with stdio transport", file=sys.stderr)
    mcp.run(transport="stdio")

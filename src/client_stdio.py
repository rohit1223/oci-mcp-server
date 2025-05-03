import asyncio
import nest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from config import COMPARTMENT_ID

nest_asyncio.apply()  # For interactive environments

async def main():
    # Define server parameters
    server_params = StdioServerParameters(
        command="python",  # The command to run your server
        args=["server.py"],  # Arguments to the command
    )

    # Connect to the server
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection
            await session.initialize()

            # List available tools
            tools_result = await session.list_tools()
            print("Available tools:")
            for tool in tools_result.tools:
                print(f"  - {tool.name}: {tool.description}")

            # Call our List Gateways tool
            result = await session.call_tool("list_gateways_tool", arguments={"compartment_id": COMPARTMENT_ID})
            print(result)

            result = await session.call_tool("get_gateway_tool", arguments={"gateway_id": 'ocid1.apigatewaydev.oc1.ap-mumbai-1.amaaaaaatwlbihya3vdi2kewe3ohwmza6paoosl3iwx3rjvup7ssso6arsfa'})
            print(result)

if __name__ == "__main__":
    asyncio.run(main())
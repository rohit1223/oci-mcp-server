import asyncio
import nest_asyncio
import json

from llama_index.core.agent import ReActAgent
from llama_index.llms.ollama import Ollama
from llama_index.core.tools import FunctionTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from config import COMPARTMENT_ID, GATEWAY_ID
from llama_index.core.memory import SimpleComposableMemory, ChatMemoryBuffer

nest_asyncio.apply()

async def main():
    server_params = StdioServerParameters(
        command="/Users/kukuro/personal/oci_mcp_with_client/.venv/bin/python",
        args=["server.py"],
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Define MCP-wrapped tools for LlamaIndex
            async def list_gateways_tool(compartment_id: str = None, properties: dict = None, value: str = None, **kwargs) -> str:
                # Try to extract compartment_id from all possible places
                if properties:
                    if isinstance(properties, dict):
                        compartment_id = properties.get("compartment_id", compartment_id)
                    elif hasattr(properties, "get"):
                        compartment_id = properties.get("compartment_id", compartment_id)
                if not compartment_id and value:
                    compartment_id = value
                if not compartment_id and kwargs.get("compartment_id"):
                    compartment_id = kwargs["compartment_id"]
                if not compartment_id:
                    print("No compartment_id provided to list_gateways_tool")
                    return "Error: No compartment_id provided"
                result = await session.call_tool(
                    "list_gateways_tool",
                    arguments={"compartment_id": compartment_id}
                )
                print("list_gateways_tool result:", result)
                print("list_gateways_tool result dir:", dir(result))
                output = getattr(result, 'return_value', result)
                if isinstance(output, (dict, list)):
                    return json.dumps(output)
                return str(output)

            async def get_gateway_tool(gateway_id: str) -> str:
                result = await session.call_tool(
                    "get_gateway_tool",
                    arguments={"gateway_id": gateway_id}
                )
                print("get_gateway_tool result:", result)
                print("get_gateway_tool result dir:", dir(result))
                # Try to return the most likely output attribute, adjust as needed
                return str(getattr(result, 'return_value', result))

            # Wrap tools in LlamaIndex FunctionTool
            tools = [
                FunctionTool.from_defaults(
                    fn=list_gateways_tool,
                    name="list_gateways_tool",
                    description="List OCI API gateways given a compartment OCID."
                ),
                FunctionTool.from_defaults(
                    fn=get_gateway_tool,
                    name="get_gateway_tool",
                    description="Get details for an OCI API gateway given a gateway OCID."
                )
            ]

            # Connect Ollama Llama 3.2 locally
            llm = Ollama(
                model="llama3.2:latest",
                api_url="http://localhost:11434/api/generate",
                temperature=0.4
                )

            # Create memory for the agent
            primary_memory = ChatMemoryBuffer(token_limit=2000)
            memory = SimpleComposableMemory(primary_memory=primary_memory)

            # Create ReAct Agent from tools
            agent = ReActAgent(tools=tools, llm=llm, memory=memory, verbose=True)

    for tool in tools:
        print(f"Tool: {tool.metadata.name}")
        print(f"  Description: {tool.metadata.description}")
        print(f"  Parameters: {tool.metadata.get_parameters_dict()}")

    # Query Example
    # query = f"List all API gateways for compartment_id {COMPARTMENT_ID}."
    # response = await agent.aquery(query)

    # Query Example
    query2 = f"Describe the gateways for {GATEWAY_ID}."
    response2 = await agent.aquery(query2)

    print("\nFinal Response:", response2)

if __name__ == "__main__":
    asyncio.run(main())

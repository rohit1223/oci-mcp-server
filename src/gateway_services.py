# service.py
# ----------
import logging
from oci.apigateway import GatewayClient
from authentication import get_session_token_signer
from config import SERVICE_ENDPOINT, COMPARTMENT_ID
from oci.util import to_dict


def list_gateways(compartment_id: str) -> list:
    """
    Lists all API Gateways in the specified compartment using session-token auth.

    Args:
        compartment_id (str): The OCID of the compartment to list gateways from.
    
    Returns:
        list: A list of dictionaries containing gateway information.
    """
    try:
        config, signer = get_session_token_signer()
        client = GatewayClient(
            config=config,
            signer=signer,
            service_endpoint=SERVICE_ENDPOINT
        )

        response = client.list_gateways(compartment_id=compartment_id)
        gateways_as_dict = {gw.id: to_dict(gw) for gw in response.data.items}
        return gateways_as_dict

    except Exception as e:
        logging.error("Failed to list gateways", exc_info=True)
        raise e

def get_gateway(gateway_id: str) -> dict:
    """
    Gets details of a specific API Gateway using session-token auth.

    Args:
        gateway_id (str): The OCID of the gateway to retrieve.
    
    Returns:
        dict: A dictionary containing the gateway details.
    
    Raises:
        ValueError: If the gateway_id is not in the correct format
        ServiceError: If there's an error from the OCI service
    """
    if not gateway_id or not gateway_id.startswith('ocid1.apigateway'):
        raise ValueError("Invalid gateway ID format. Gateway ID should start with 'ocid1.apigateway'")

    try:
        config, signer = get_session_token_signer()
        client = GatewayClient(
            config=config,
            signer=signer,
            service_endpoint=SERVICE_ENDPOINT
        )

        response = client.get_gateway(gateway_id=gateway_id)
        return response.data

    except Exception as e:
        logging.error(f"Failed to get gateway with ID: {gateway_id}", exc_info=True)
        raise e

if __name__ == "__main__":
    # Example usage with a valid gateway ID
    try:
        gateways = list_gateways(COMPARTMENT_ID)
        print(gateways)
        gateway_id = "ocid1.apigatewaydev.oc1.ap-mumbai-1.amaaaaaatwlbihyayo3rpsvgoitzs6peajdbgiwnc2t6bhu6c2htnimvfdeq"
        gateway_details = get_gateway(gateway_id)
        print("Gateway Details:")
        for key, value in gateway_details.items():
            print(f"{key}: {value}")
    except Exception as e:
        print(f"Error: {str(e)}")
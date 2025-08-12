from gateway_services import list_gateways, get_gateway
from config import COMPARTMENT_ID, GATEWAY_ID

def main():
    print("Hello from oci-gateway-mcp-server!")
    # gateway_list = list_gateways(compartment_id='ocid1.compartment.oc1..aaaaaaaai2zzsgf34nal6yvihyep7ojdiyv6bpcalodwoziulu6wq7wm4pjq')

    # print(gateway_list)

    # # gateway_detail = get_gateway(gateway_id='ocid1.apigatewaydev.oc1.iad.amaaaaaatwlbihyav5q6fn6ci4axot73oy6dqjfy5yogagzo5ltbxb3dn5dq')
    # # print(gateway_detail)


if __name__ == "__main__":
    main()

"""
OAuth Configuration Template for MCP Server

Instructions:
1. Copy this file to oauth_config.py
2. Fill in your actual OAuth credentials from Oracle IDCS
3. Update URLs to match your environment
4. Never commit oauth_config.py to version control

For the scope parameter:
- Use the fully qualified scope format: "openid <your-api-gateway-url><scope-name>"
- Example: "openid https://your-gateway.apigateway.region.oci.customer-oci.com/api_gateway_access"
- Or just "openid api_gateway_access" if you have only one resource server
"""

OAUTH_CONFIG = {
    # OAuth Client Credentials from IDCS
    "client_id": "YOUR_CLIENT_ID_HERE",
    "client_secret": "YOUR_CLIENT_SECRET_HERE",
    
    # IDCS OAuth Endpoints
    # Format: https://idcs-<tenant-id>.identity.oraclecloud.com/oauth2/v1/authorize
    "authorization_endpoint": "https://idcs-EXAMPLE123.identity.oraclecloud.com/oauth2/v1/authorize",
    "token_endpoint": "https://idcs-EXAMPLE123.identity.oraclecloud.com/oauth2/v1/token",
    
    # Redirect URI - must match exactly what's configured in IDCS
    # Should point to your API Gateway's no-auth deployment path
    "redirect_uri": "https://mygateway.apigateway.us-ashburn-1.oci.customer-oci.com/mcp_no_auth/auth/callback",
    
    # Scope - request the API Gateway resource scope
    # Format: "openid <fully-qualified-scope>" or "openid <scope-name>"
    "scope": "openid https://mygateway.apigateway.us-ashburn-1.oci.customer-oci.com/api_gateway_access",
    
    # Audience - your API Gateway base URL
    # This should match the Primary Audience configured in IDCS
    "audience": "https://mygateway.apigateway.us-ashburn-1.oci.customer-oci.com"
}

# Example filled configuration with dummy data:
"""
OAUTH_CONFIG = {
    "client_id": "abc123def456ghi789jkl012mno345pqr",
    "client_secret": "idcscs-12345678-abcd-efgh-ijkl-mnopqrstuvwx",
    "authorization_endpoint": "https://idcs-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.identity.oraclecloud.com/oauth2/v1/authorize",
    "token_endpoint": "https://idcs-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.identity.oraclecloud.com/oauth2/v1/token",
    "redirect_uri": "https://examplegateway.apigateway.us-ashburn-1.oci.customer-oci.com/mcp_no_auth/auth/callback",
    "scope": "openid https://examplegateway.apigateway.us-ashburn-1.oci.customer-oci.com/api_gateway_access",
    "audience": "https://examplegateway.apigateway.us-ashburn-1.oci.customer-oci.com"
}
"""
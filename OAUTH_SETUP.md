# OAuth Setup for MCP Server

## Overview

The MCP server (`src/streaming_server.py`) now includes built-in OAuth 2.0 authentication with backend token exchange. This ensures secure access when deployed behind OCI API Gateway with OAuth protection.

## Architecture

```
Browser → API Gateway → MCP Server
   ↓                        ↓
   └──────→ IDCS OAuth ←────┘
```

The OAuth flow works as follows:

1. **Browser** accesses protected MCP endpoint
2. **MCP Server** checks for valid session cookie
3. If no valid session, redirects to `/auth/start`
4. **Server** initiates OAuth flow with PKCE
5. **IDCS** authenticates user and redirects back
6. **Server** exchanges code for token (backend-side)
7. **Server** stores token in secure session
8. **Browser** can now access protected endpoints

## Configuration

1. Update the OAuth configuration in `src/streaming_server.py`:

```python
OAUTH_CONFIG = {
    "client_id": "YOUR_API_GATEWAY_AUDIENCE",
    "client_secret": "YOUR_CLIENT_SECRET",  # Store securely!
    "authorization_endpoint": "YOUR_IDCS_AUTH_ENDPOINT",
    "token_endpoint": "YOUR_IDCS_TOKEN_ENDPOINT",
    "redirect_uri": "http://localhost:8000/auth/callback",
    "scope": "YOUR_SCOPE",
    "audience": "YOUR_AUDIENCE"
}
```

2. For production, store the client secret in environment variables:

```python
import os
OAUTH_CONFIG = {
    "client_secret": os.environ.get("OAUTH_CLIENT_SECRET"),
    # ... other config
}
```

## API Gateway Configuration

### 1. Create OAuth Application in IDCS

- Application Type: Confidential Application
- Grant Types: Authorization Code
- Redirect URI: `http://your-server:8000/auth/callback`
- Note the Client ID and Client Secret

### 2. Configure API Gateway Deployment

```yaml
authentication:
  type: OAUTH2
  tokenHeader: Authorization
  tokenAuthScheme: Bearer
  isAnonymousAccessAllowed: false
  validationPolicy:
    type: REMOTE_DISCOVERY
    sourceUriDetails:
      type: DISCOVERY_URI
      uri: https://YOUR_IDCS.identity.oraclecloud.com/.well-known/openid-configuration
    validationFailurePolicy: OAUTH2
    audiences:
      - YOUR_API_GATEWAY_AUDIENCE
```

### 3. Route Configuration

The API Gateway should proxy requests to the backend MCP server:

```yaml
routes:
  - path: /mcp
    methods: [GET, POST, OPTIONS]
    backend:
      type: HTTP_BACKEND
      url: http://your-backend:8000/mcp
  - path: /auth/*
    methods: [GET, POST, OPTIONS]
    backend:
      type: HTTP_BACKEND  
      url: http://your-backend:8000/auth/
```

## Testing

### Local Testing

1. Start the server:
```bash
python src/streaming_server.py
```

2. Open browser to http://localhost:8000/

3. Click "Login with OAuth" to start authentication

4. After successful auth, test MCP endpoints

### Production Testing

1. Access through API Gateway:
```
https://your-gateway.apigateway.region.oci.customer-oci.com/
```

2. The OAuth flow will use the API Gateway's configured IDCS

## Security Considerations

1. **Never expose client secret to browser** - Token exchange happens server-side
2. **Use HTTPS in production** - Set `secure=True` for cookies
3. **PKCE Protection** - Prevents authorization code interception
4. **CSRF Protection** - State parameter validates OAuth responses
5. **Session Management** - HTTP-only cookies prevent XSS attacks
6. **Token Storage** - Tokens stored server-side only

## Endpoints

### Authentication Endpoints

- `GET /auth/start` - Initiate OAuth flow
- `GET /auth/callback` - Handle OAuth callback
- `GET /auth/status` - Check authentication status
- `POST /auth/logout` - Clear session and logout

### Protected MCP Endpoints

- `GET /mcp` - Main MCP endpoint (requires auth)
- `GET /r1` - Alternative MCP endpoint (requires auth)

### Public Endpoints

- `GET /` - OAuth test client interface
- `GET /health` - Health check endpoint

## Troubleshooting

### Invalid redirect URI
- Ensure redirect URI in IDCS matches server configuration
- Check API Gateway is correctly proxying `/auth/*` routes

### Token exchange fails
- Verify client secret is correct
- Check IDCS token endpoint is accessible from server
- Ensure PKCE is properly configured

### Session not persisting
- Check cookie settings match deployment domain
- Verify `samesite` and `secure` settings
- Ensure browser accepts third-party cookies if needed

### CORS issues
- API Gateway should pass through CORS headers
- Server includes CORS middleware for browser access

## Dependencies

Install required packages:

```bash
pip install httpx
```

The server uses:
- `httpx` for OAuth token exchange
- `secrets` for secure token generation
- `hashlib` for PKCE challenge
- HTTP-only cookies for session management
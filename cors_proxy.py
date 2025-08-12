#!/usr/bin/env python3
"""
CORS Proxy Server for MCP API Gateway Testing

This proxy server forwards requests to the API Gateway and adds CORS headers
to allow browser-based testing.
"""

from flask import Flask, request, Response
import requests
import json

app = Flask(__name__)

# Target API Gateway URL
TARGET_URL = "https://irlxwomijighis2rzx3aj7n2c4.apigateway.us-ashburn-1.oci.oc-test.com/rdb/r1"

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'OPTIONS'])
def proxy(path):
    # Handle preflight OPTIONS requests
    if request.method == 'OPTIONS':
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept, mcp-session-id'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    # Forward the request to the target API
    try:
        # Prepare headers
        headers = {key: value for key, value in request.headers if key.lower() not in ['host', 'origin']}
        
        # Forward cookies
        cookies = request.cookies
        
        # Make the request to the target API
        if request.method == 'POST':
            resp = requests.post(
                TARGET_URL,
                data=request.get_data(),
                headers=headers,
                cookies=cookies,
                allow_redirects=False,
                verify=True
            )
        else:
            resp = requests.get(
                TARGET_URL,
                headers=headers,
                cookies=cookies,
                allow_redirects=False,
                verify=True
            )
        
        # Create response
        response = Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get('content-type')
        )
        
        # Copy relevant headers from the target response
        for key, value in resp.headers.items():
            if key.lower() not in ['content-encoding', 'content-length', 'connection']:
                response.headers[key] = value
        
        # Add CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Expose-Headers'] = 'mcp-session-id'
        
        # Forward cookies
        for cookie in resp.cookies:
            response.set_cookie(
                cookie.name,
                cookie.value,
                domain=None,  # Let browser handle domain
                path=cookie.path,
                secure=False,  # Set to False for localhost testing
                httponly=cookie.get('httponly', False)
            )
        
        return response
        
    except Exception as e:
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            content_type='application/json',
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': 'true'
            }
        )

if __name__ == '__main__':
    print(f"Starting CORS proxy server on http://localhost:5000")
    print(f"Proxying to: {TARGET_URL}")
    print(f"\nUse http://localhost:5000 instead of the direct API Gateway URL in your browser tests")
    app.run(port=5000, debug=True)
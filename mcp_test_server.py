#!/usr/bin/env python3
"""
MCP Test Server with Built-in CORS Proxy

This server:
1. Serves the HTML test interface at http://localhost:5000
2. Proxies API requests to the API Gateway with CORS headers
3. Handles OIDC authentication flow
"""

from flask import Flask, request, Response, render_template_string
import requests
import json

app = Flask(__name__)

# Target API Gateway URL
TARGET_URL = "https://irlxwomijighis2rzx3aj7n2c4.apigateway.us-ashburn-1.oci.oc-test.com/rdb/r1"

# HTML Template for the test interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>MCP API Gateway Test Interface</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 900px;
            width: 100%;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        .header p {
            opacity: 0.9;
            font-size: 14px;
        }
        .content {
            padding: 30px;
        }
        .status-bar {
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
        }
        .status-item {
            flex: 1;
        }
        .status-label {
            font-size: 12px;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }
        .status-value {
            font-size: 14px;
            font-weight: 600;
            color: #333;
        }
        .status-value.connected {
            color: #28a745;
        }
        .status-value.disconnected {
            color: #dc3545;
        }
        .auth-section {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
        }
        .auth-section h3 {
            color: #856404;
            margin-bottom: 15px;
            font-size: 16px;
        }
        .auth-steps {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .auth-step {
            flex: 1;
            padding: 10px;
            text-align: center;
            background: white;
            border-radius: 5px;
            border: 2px solid #ffeaa7;
            position: relative;
        }
        .auth-step.completed {
            background: #d4edda;
            border-color: #28a745;
        }
        .auth-step.active {
            border-color: #007bff;
            background: #cfe2ff;
        }
        .button-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        button {
            padding: 15px 20px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        button:before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: rgba(255,255,255,0.5);
            transform: translate(-50%, -50%);
            transition: width 0.6s, height 0.6s;
        }
        button:hover:before {
            width: 300px;
            height: 300px;
        }
        button.primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        button.secondary {
            background: #6c757d;
            color: white;
        }
        button.success {
            background: #28a745;
            color: white;
        }
        button:disabled {
            background: #e9ecef;
            color: #6c757d;
            cursor: not-allowed;
        }
        button:disabled:before {
            display: none;
        }
        .response-section {
            background: #1e1e1e;
            border-radius: 10px;
            overflow: hidden;
        }
        .response-header {
            background: #2d2d2d;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .response-title {
            color: #d4d4d4;
            font-weight: 600;
        }
        .response-actions {
            display: flex;
            gap: 10px;
        }
        .response-action {
            padding: 5px 10px;
            background: #007acc;
            color: white;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
        }
        .response-body {
            padding: 20px;
            color: #d4d4d4;
            font-family: 'Cascadia Code', 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.6;
            max-height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .response-body::-webkit-scrollbar {
            width: 8px;
        }
        .response-body::-webkit-scrollbar-track {
            background: #2d2d2d;
        }
        .response-body::-webkit-scrollbar-thumb {
            background: #555;
            border-radius: 4px;
        }
        .spinner {
            border: 2px solid #f3f3f3;
            border-top: 2px solid #667eea;
            border-radius: 50%;
            width: 16px;
            height: 16px;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin-left: 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .input-group {
            margin-bottom: 20px;
        }
        .input-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #333;
        }
        .input-group input {
            width: 100%;
            padding: 10px;
            border: 2px solid #e9ecef;
            border-radius: 5px;
            font-size: 14px;
            font-family: monospace;
        }
        .input-group input:focus {
            outline: none;
            border-color: #667eea;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 MCP API Gateway Test Interface</h1>
            <p>Running on http://localhost:5000 with built-in CORS proxy</p>
        </div>
        
        <div class="content">
            <div class="status-bar">
                <div class="status-item">
                    <div class="status-label">Server Status</div>
                    <div class="status-value connected">● Connected</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Session ID</div>
                    <div class="status-value" id="sessionId">Not initialized</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Auth Status</div>
                    <div class="status-value" id="authStatus">Unknown</div>
                </div>
            </div>

            <div class="auth-section">
                <h3>🔐 Authentication Steps</h3>
                <div class="auth-steps">
                    <div class="auth-step" id="step1">
                        1. Click Authenticate
                    </div>
                    <div class="auth-step" id="step2">
                        2. Complete OIDC Login
                    </div>
                    <div class="auth-step" id="step3">
                        3. Initialize Session
                    </div>
                    <div class="auth-step" id="step4">
                        4. Use MCP Tools
                    </div>
                </div>
            </div>

            <div class="button-grid">
                <button class="primary" onclick="authenticate()">
                    🔐 Authenticate with OIDC
                </button>
                <button class="primary" onclick="testInitialize()" id="initBtn">
                    1️⃣ Initialize MCP Session
                </button>
                <button class="secondary" onclick="listTools()" id="listBtn" disabled>
                    2️⃣ List Available Tools
                </button>
                <button class="success" onclick="callDummyTool()" id="dummyBtn" disabled>
                    3️⃣ Call Dummy Gateway
                </button>
            </div>

            <div class="input-group">
                <label for="compartmentId">Compartment ID (for list_gateways_tool)</label>
                <input type="text" id="compartmentId" 
                       placeholder="ocid1.compartment.oc1..aaaaaaaai2zzsg..." 
                       value="">
                <button class="secondary" onclick="callListGateways()" 
                        id="listGatewaysBtn" disabled style="margin-top: 10px;">
                    Call list_gateways_tool
                </button>
            </div>

            <div class="response-section">
                <div class="response-header">
                    <div class="response-title">Response Output</div>
                    <div class="response-actions">
                        <button class="response-action" onclick="clearResponse()">Clear</button>
                        <button class="response-action" onclick="copyResponse()">Copy</button>
                    </div>
                </div>
                <div class="response-body" id="response">Ready for commands...</div>
            </div>
        </div>
    </div>

    <script>
        let SESSION_ID = null;
        let requestCounter = 1;

        // Check auth status on load
        window.onload = function() {
            checkAuthStatus();
        };

        function checkAuthStatus() {
            if (document.cookie.includes('OCI_APIGW')) {
                document.getElementById('authStatus').textContent = 'Authenticated';
                document.getElementById('authStatus').className = 'status-value connected';
                document.getElementById('step1').className = 'auth-step completed';
                document.getElementById('step2').className = 'auth-step completed';
            } else {
                document.getElementById('authStatus').textContent = 'Not authenticated';
                document.getElementById('authStatus').className = 'status-value disconnected';
            }
        }

        function authenticate() {
            document.getElementById('step1').className = 'auth-step active';
            window.open('/api/proxy', '_blank');
            setTimeout(() => {
                checkAuthStatus();
                alert('Complete the OIDC login in the new window. You may see "Method Not Allowed" - that is OK! Then click Initialize MCP Session.');
            }, 1000);
        }

        async function makeRequest(method, params = null) {
            const requestId = requestCounter++;
            const requestData = {
                jsonrpc: "2.0",
                method: method,
                id: requestId
            };
            
            if (params) {
                requestData.params = params;
            }

            addToResponse(`→ Request #${requestId}: ${method}`, 'request');
            addToResponse(JSON.stringify(requestData, null, 2), 'request-body');
            
            try {
                const response = await fetch('/api/proxy', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'text/event-stream',
                        ...(SESSION_ID ? {'mcp-session-id': SESSION_ID} : {})
                    },
                    body: JSON.stringify(requestData),
                    credentials: 'include'
                });
                
                const responseText = await response.text();
                
                // Extract session ID from headers
                const sessionHeader = response.headers.get('mcp-session-id');
                if (sessionHeader && !SESSION_ID) {
                    SESSION_ID = sessionHeader;
                    document.getElementById('sessionId').textContent = SESSION_ID.substring(0, 20) + '...';
                    document.getElementById('step3').className = 'auth-step completed';
                }
                
                // Parse SSE response
                if (responseText.includes('event: message')) {
                    const lines = responseText.split('\\n');
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const jsonData = JSON.parse(line.substring(6));
                            addToResponse(`← Response #${requestId}:`, 'response');
                            addToResponse(JSON.stringify(jsonData, null, 2), 'response-body');
                            
                            if (jsonData.result && method === 'initialize') {
                                enableButtons();
                                document.getElementById('step4').className = 'auth-step completed';
                            }
                            
                            return jsonData;
                        }
                    }
                } else {
                    addToResponse(`← Raw Response #${requestId}:`, 'response');
                    addToResponse(responseText, 'response-body');
                }
                
            } catch (error) {
                addToResponse(`✗ Error #${requestId}: ${error.message}`, 'error');
                throw error;
            }
        }

        function addToResponse(text, type = '') {
            const response = document.getElementById('response');
            const timestamp = new Date().toLocaleTimeString();
            
            let prefix = '';
            if (type === 'request') prefix = '🔵 ';
            else if (type === 'response') prefix = '🟢 ';
            else if (type === 'error') prefix = '🔴 ';
            
            response.textContent += `\\n[${timestamp}] ${prefix}${text}\\n`;
            response.scrollTop = response.scrollHeight;
        }

        function clearResponse() {
            document.getElementById('response').textContent = 'Ready for commands...';
        }

        function copyResponse() {
            const text = document.getElementById('response').textContent;
            navigator.clipboard.writeText(text);
            alert('Response copied to clipboard!');
        }

        function enableButtons() {
            document.getElementById('listBtn').disabled = false;
            document.getElementById('dummyBtn').disabled = false;
            document.getElementById('listGatewaysBtn').disabled = false;
        }

        async function testInitialize() {
            document.getElementById('step3').className = 'auth-step active';
            await makeRequest('initialize', {
                protocolVersion: "2024-11-05",
                capabilities: {},
                clientInfo: {
                    name: "localhost-test",
                    version: "1.0"
                }
            });
        }

        async function listTools() {
            await makeRequest('tools/list');
        }

        async function callDummyTool() {
            await makeRequest('tools/call', {
                name: "get_dummy_gateways_tool",
                arguments: {}
            });
        }

        async function callListGateways() {
            const compartmentId = document.getElementById('compartmentId').value;
            if (!compartmentId) {
                alert('Please enter a compartment ID');
                return;
            }
            
            await makeRequest('tools/call', {
                name: "list_gateways_tool",
                arguments: {
                    compartment_id: compartmentId
                }
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serve the HTML test interface"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/proxy', methods=['GET', 'POST', 'OPTIONS'])
def proxy():
    """Proxy requests to the API Gateway with CORS headers"""
    
    # Handle preflight OPTIONS requests
    if request.method == 'OPTIONS':
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept, mcp-session-id'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    try:
        # Prepare headers for the target request
        headers = {}
        for key, value in request.headers:
            if key.lower() not in ['host', 'origin', 'referer']:
                headers[key] = value
        
        # Make the request to the target API
        if request.method == 'POST':
            resp = requests.post(
                TARGET_URL,
                data=request.get_data(),
                headers=headers,
                cookies=request.cookies,
                allow_redirects=False,
                verify=True,
                timeout=30
            )
        else:
            resp = requests.get(
                TARGET_URL,
                headers=headers,
                cookies=request.cookies,
                allow_redirects=False,
                verify=True,
                timeout=30
            )
        
        # Create response
        response = Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get('content-type', 'text/plain')
        )
        
        # Copy relevant headers from the target response
        for key, value in resp.headers.items():
            if key.lower() not in ['content-encoding', 'content-length', 'connection', 'transfer-encoding']:
                response.headers[key] = value
        
        # Add CORS headers
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Expose-Headers'] = 'mcp-session-id, location, set-cookie'
        
        # Handle cookies from the response - simplified
        # The cookies will be forwarded automatically via the browser's handling of Set-Cookie headers
        
        return response
        
    except requests.exceptions.Timeout:
        return Response(
            json.dumps({"error": "Request timeout"}),
            status=504,
            content_type='application/json',
            headers={
                'Access-Control-Allow-Origin': request.headers.get('Origin', '*'),
                'Access-Control-Allow-Credentials': 'true'
            }
        )
    except Exception as e:
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            content_type='application/json',
            headers={
                'Access-Control-Allow-Origin': request.headers.get('Origin', '*'),
                'Access-Control-Allow-Credentials': 'true'
            }
        )

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 MCP Test Server with CORS Proxy")
    print("="*60)
    print(f"✅ Server running at: http://localhost:5000")
    print(f"📡 Proxying to: {TARGET_URL}")
    print("\n📝 Instructions:")
    print("1. Open http://localhost:5000 in your browser")
    print("2. Click 'Authenticate with OIDC' to login")
    print("3. After login, click 'Initialize MCP Session'")
    print("4. Test the MCP tools!")
    print("="*60 + "\n")
    
    app.run(port=5000, debug=True)
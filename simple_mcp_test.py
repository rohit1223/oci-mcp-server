#!/usr/bin/env python3
"""
Simple MCP Test Server - Minimal version without authentication complexity
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.request
import urllib.parse
import ssl

class MCPTestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Serve the HTML interface"""
        if self.path == '/':
            html = """
<!DOCTYPE html>
<html>
<head>
    <title>MCP Test Interface</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 40px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }
        .info {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            border-left: 4px solid #2196F3;
        }
        .endpoint-info {
            background: #fff3cd;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            font-family: monospace;
            font-size: 14px;
        }
        button {
            background: #007bff;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            margin: 5px;
            font-size: 16px;
        }
        button:hover {
            background: #0056b3;
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        textarea {
            width: 100%;
            height: 150px;
            font-family: monospace;
            font-size: 14px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            margin: 10px 0;
        }
        .response {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 15px;
            border-radius: 5px;
            font-family: monospace;
            white-space: pre-wrap;
            max-height: 400px;
            overflow-y: auto;
            margin-top: 20px;
        }
        .error { color: #ff6b6b; }
        .success { color: #51cf66; }
        .warning { color: #ffd93d; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 MCP Direct Test Interface</h1>
        
        <div class="info">
            <strong>Direct Testing Mode:</strong> This interface sends requests directly to your API Gateway.
            <br><br>
            <strong>Note:</strong> You need to handle authentication separately. If your API requires OIDC:
            <ol>
                <li>First authenticate in another browser tab by visiting the API Gateway URL</li>
                <li>Then use this interface to test MCP commands</li>
            </ol>
        </div>

        <div class="endpoint-info">
            <strong>Target Endpoint:</strong>
            <input type="text" id="endpoint" style="width: 100%; padding: 5px; margin-top: 5px;"
                   value="https://irlxwomijighis2rzx3aj7n2c4.apigateway.us-ashburn-1.oci.oc-test.com/rdb/r1">
        </div>

        <h3>Quick Tests:</h3>
        <button onclick="testInitialize()">Initialize Session</button>
        <button onclick="testListTools()">List Tools</button>
        <button onclick="testDummyTool()">Call Dummy Tool</button>
        
        <h3>Custom Request:</h3>
        <textarea id="customRequest">{
  "jsonrpc": "2.0",
  "method": "initialize",
  "id": 1,
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "test", "version": "1.0"}
  }
}</textarea>
        <br>
        <button onclick="sendCustomRequest()">Send Custom Request</button>

        <h3>Response:</h3>
        <div class="response" id="response">Ready to send requests...</div>
    </div>

    <script>
        let sessionId = null;

        async function sendRequest(data) {
            const endpoint = document.getElementById('endpoint').value;
            const response = document.getElementById('response');
            
            response.innerHTML = '<span class="warning">Sending request...</span>\\n\\n';
            response.innerHTML += JSON.stringify(data, null, 2) + '\\n\\n';
            
            try {
                // Try via proxy first
                const proxyResponse = await fetch('/proxy', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Target-URL': endpoint,
                        ...(sessionId && {'X-Session-ID': sessionId})
                    },
                    body: JSON.stringify(data)
                });
                
                const result = await proxyResponse.text();
                
                // Extract session ID if present
                const sessionMatch = result.match(/mcp-session-id: ([^\\s]+)/);
                if (sessionMatch) {
                    sessionId = sessionMatch[1];
                    response.innerHTML += '<span class="success">Session ID: ' + sessionId + '</span>\\n\\n';
                }
                
                response.innerHTML += '<span class="success">Response:</span>\\n' + result;
                
            } catch (error) {
                response.innerHTML += '<span class="error">Error: ' + error.message + '</span>\\n\\n';
                response.innerHTML += 'If you see CORS errors, you need to:\\n';
                response.innerHTML += '1. Authenticate in another tab first\\n';
                response.innerHTML += '2. Or use a browser with disabled security for testing\\n';
                response.innerHTML += '3. Or configure your API Gateway to allow CORS';
            }
        }

        function testInitialize() {
            sendRequest({
                jsonrpc: "2.0",
                method: "initialize",
                id: 1,
                params: {
                    protocolVersion: "2024-11-05",
                    capabilities: {},
                    clientInfo: {name: "test-client", version: "1.0"}
                }
            });
        }

        function testListTools() {
            sendRequest({
                jsonrpc: "2.0",
                method: "tools/list",
                id: 2
            });
        }

        function testDummyTool() {
            sendRequest({
                jsonrpc: "2.0",
                method: "tools/call",
                id: 3,
                params: {
                    name: "get_dummy_gateways_tool",
                    arguments: {}
                }
            });
        }

        function sendCustomRequest() {
            try {
                const customData = JSON.parse(document.getElementById('customRequest').value);
                sendRequest(customData);
            } catch (error) {
                document.getElementById('response').innerHTML = 
                    '<span class="error">Invalid JSON: ' + error.message + '</span>';
            }
        }
    </script>
</body>
</html>
"""
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Proxy POST requests to the API Gateway"""
        if self.path == '/proxy':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            target_url = self.headers.get('X-Target-URL')
            session_id = self.headers.get('X-Session-ID')
            
            if not target_url:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Missing X-Target-URL header')
                return
            
            # Create request with proper headers
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream'
            }
            if session_id:
                headers['mcp-session-id'] = session_id
            
            # Create SSL context that doesn't verify certificates (for testing)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            try:
                req = urllib.request.Request(
                    target_url,
                    data=post_data,
                    headers=headers,
                    method='POST'
                )
                
                # Make the request
                with urllib.request.urlopen(req, context=ctx) as response:
                    result = response.read()
                    
                    # Send response back
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    
                    # Forward session ID if present
                    if 'mcp-session-id' in response.headers:
                        self.send_header('X-Session-ID', response.headers['mcp-session-id'])
                    
                    self.end_headers()
                    
                    # Include headers in response for debugging
                    header_info = f"Status: {response.status}\n"
                    for key, value in response.headers.items():
                        header_info += f"{key}: {value}\n"
                    header_info += "\n"
                    
                    self.wfile.write(header_info.encode() + result)
                    
            except urllib.error.HTTPError as e:
                # Handle HTTP errors (like redirects)
                self.send_response(e.code)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                error_info = f"HTTP Error {e.code}: {e.reason}\n"
                error_info += f"URL: {e.url}\n\n"
                if e.code == 302:
                    error_info += "Redirect detected - you need to authenticate first!\n"
                    error_info += f"Location: {e.headers.get('Location', 'Unknown')}\n"
                
                self.wfile.write(error_info.encode())
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(f"Error: {str(e)}".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        """Handle preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Target-URL, X-Session-ID')
        self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Simple MCP Test Server")
    print("="*60)
    print("✅ Server running at: http://localhost:8080")
    print("\n📝 Instructions:")
    print("1. Open http://localhost:8080 in your browser")
    print("2. If authentication is needed:")
    print("   - First visit your API Gateway URL in another tab")
    print("   - Complete the OIDC login")
    print("   - Then use this interface to test")
    print("="*60 + "\n")
    
    server = HTTPServer(('localhost', 8080), MCPTestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
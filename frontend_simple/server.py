#!/usr/bin/env python3
"""
Simple HTTP server for serving the Clinical De-ID frontend
"""
import http.server
import socketserver
import os
import sys
from pathlib import Path

# Configuration
PORT = 3001
DIRECTORY = Path(__file__).parent

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler with CORS support for API calls"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()
    
    def do_OPTIONS(self):
        # Handle preflight CORS requests
        self.send_response(200)
        self.end_headers()
    
    def log_message(self, format, *args):
        # Custom logging format
        print(f"[{self.log_date_time_string()}] {format % args}")

def main():
    """Start the frontend server"""
    
    # Change to the frontend directory
    os.chdir(DIRECTORY)
    
    print("🌐 Clinical Text De-Identification Frontend Server")
    print("=" * 50)
    print(f"📁 Serving directory: {DIRECTORY}")
    print(f"🚀 Starting server on port {PORT}...")
    
    try:
        with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
            print(f"✅ Server started successfully!")
            print(f"🌐 Local URL: http://localhost:{PORT}")
            print(f"📱 Frontend Interface: http://localhost:{PORT}/index.html")
            print("\n🔧 Features:")
            print("   • Interactive text input/output interface")
            print("   • Authentication with demo accounts")
            print("   • Entity detection and de-identification")
            print("   • Thai/English/Mixed language support")
            print("   • Real-time API communication")
            print("\n📋 Demo Accounts:")
            print("   • admin / admin123 (Full access)")
            print("   • reviewer / reviewer123 (Review access)")
            print("   • operator / operator123 (Basic access)")
            print(f"\n🔗 Backend API: https://8000-igoy3cr883cnchk200st0-6532622b.e2b.dev")
            print("\n⏹️  Press Ctrl+C to stop the server")
            print("=" * 50)
            
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"❌ Port {PORT} is already in use")
            print(f"💡 Try a different port or stop the existing service")
        else:
            print(f"❌ Server error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
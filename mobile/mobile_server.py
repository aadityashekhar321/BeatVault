#!/usr/bin/env python3
"""
BeatVault Mobile Server
Binds to 0.0.0.0:8080 and surfaces local Wi-Fi IP and ASCII QR Code
for instant mobile testing on budget Android devices and smartphones.
"""

import os
import sys
import socket
import http.server
import socketserver

PORT = 8080

def get_local_ip():
    """Detect the local machine's primary LAN / Wi-Fi IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Route lookup towards a public IP (doesn't send actual packet)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = '127.0.0.1'
    finally:
        s.close()
    return ip

class BeatVaultHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler with PWA, range request, and CORS support."""

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range, Content-Type')
        self.send_header('Cache-Control', 'no-cache, must-revalidate')
        super().end_headers()

    def guess_type(self, path):
        if path.endswith('.webmanifest') or path.endswith('manifest.json'):
            return 'application/manifest+json'
        if path.endswith('.lrc'):
            return 'text/plain; charset=utf-8'
        return super().guess_type(path)

def print_banner(local_ip, port):
    url = f"http://{local_ip}:{port}"
    localhost_url = f"http://localhost:{port}"

    print("=" * 64)
    print("  BEATVAULT MOBILE — OBSIDIAN SONIC STUDIO WORKSTATION")
    print("=" * 64)
    print(f"\n[+] Local PC Link:   {localhost_url}")
    print(f"[+] Mobile Wi-Fi:    {url}")
    print("\nScan the QR Code below with your mobile phone camera:")
    print("-" * 64)

    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception as e:
        print(f"[!] (QR rendering fallback: {e})")
        print(f"Open your mobile browser and enter: {url}")

    print("-" * 64)
    print("Serving from:", os.path.dirname(os.path.abspath(__file__)))
    print("Press Ctrl+C to stop the server.\n")

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    local_ip = get_local_ip()

    try:
        with ReusableTCPServer(("0.0.0.0", PORT), BeatVaultHTTPRequestHandler) as httpd:
            print_banner(local_ip, PORT)
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[+] BeatVault Mobile server stopped.")
        sys.exit(0)
    except OSError as e:
        print(f"\n[!] Error binding to port {PORT}: {e}")
        print("    Try closing any application using port 8080, or specify a different port.")
        sys.exit(1)

if __name__ == '__main__':
    main()

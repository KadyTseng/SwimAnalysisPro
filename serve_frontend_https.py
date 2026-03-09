import http.server
import ssl
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "frontend", "build", "web")
CERT_FILE = os.path.join(BASE_DIR, "certs", "cert.pem")
KEY_FILE = os.path.join(BASE_DIR, "certs", "key.pem")

if not os.path.exists(WEB_DIR):
    print(f"Error: {WEB_DIR} does not exist.")
    sys.exit(1)
if not os.path.exists(CERT_FILE):
    print(f"Error: {CERT_FILE} does not exist.")
    sys.exit(1)

os.chdir(WEB_DIR)
server_address = ('0.0.0.0', 19191)
httpd = http.server.ThreadingHTTPServer(server_address, http.server.SimpleHTTPRequestHandler)

context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

print(f"Serving HTTPS on port 19191 from {WEB_DIR}")
httpd.serve_forever()

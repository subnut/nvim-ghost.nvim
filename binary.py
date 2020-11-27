import os
import sys
import random
import socket
import http.server
import urllib.parse
import threading
from simple_websocket_server import WebSocketServer, WebSocket

BUILD_VERSION = "0.1.0.02"


def _port_occupied(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_checker:
        return socket_checker.connect_ex(("localhost", port)) == 0


class GhostHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        _path = parsed_url.path
        if _path == "/":
            self._ghost_responder()
        elif _path == "/version":
            self._version_responder()
        elif _path == "/exit":
            self._exit_responder()

    def _ghost_responder(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        _writestr = f"""{{
  "ProtocolVersion": 1,
  "WebSocketPort": {servers.websocket_server.port}
}}"""
        print(_writestr)
        self.wfile.write(_writestr.encode("utf-8"))

    def _version_responder(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(BUILD_VERSION.encode("utf-8"))

    def _exit_responder(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write("Exiting...".encode("utf-8"))
        global running
        running = False


class GhostWebSocketHandler(WebSocket):
    def handle(self):
        print(self.data)

    def connected(self):
        print(self.address, "connected")

    def handle_close(self):
        print(self.address, "closed")


class GhostWebSocketServer(WebSocketServer):
    def __init__(self, host, port, websocketclass, **kwargs):
        self.port = port
        return super().__init__(host, port, websocketclass, **kwargs)


class Server:
    def __init__(self):
        self.http_server = self._http_server()
        self.websocket_server = self._websocket_server()
        self.http_server_thread = threading.Thread(
            target=self.http_server.serve_forever, daemon=True
        )
        self.websocket_server_thread = threading.Thread(
            target=self.websocket_server.serve_forever, daemon=True
        )

    def _http_server(self):
        if not _port_occupied(ghost_port):
            return http.server.HTTPServer(
                ("localhost", ghost_port), GhostHTTPRequestHandler
            )
        else:
            sys.exit("Port Occupied")

    def _websocket_server(self):
        while True:
            random_port = random.randint(9000, 65535)
            if not _port_occupied(random_port):
                return GhostWebSocketServer(
                    "localhost", random_port, GhostWebSocketHandler
                )


ghost_port = os.environ.get("GHOSTTEXT_SERVER_PORT")
ghost_port = ghost_port and ghost_port.isdigit() and int(ghost_port) or 4001

servers = Server()
servers.http_server_thread.start()
servers.websocket_server_thread.start()
running = True
while running:
    continue
sys.exit()

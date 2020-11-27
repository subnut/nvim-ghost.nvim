import os
import sys
import random
import socket
import http.server
import urllib.parse
import threading
import pynvim
from simple_websocket_server import WebSocketServer, WebSocket

BUILD_VERSION = "0.1.0.02"


def _port_occupied(port):
    """
    If port is occupied, returns True. Else returns False

    :param port int: port number to check
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_checker:
        return socket_checker.connect_ex(("localhost", port)) == 0


def _check_nvim_socket(socket):
    if socket is None:
        sys.exit("NVIM_LISTEN_ADDRESS environment variable not set")
    if not os.path.exists(socket):
        sys.exit("Specified socket does not exist.")


class GhostHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        responses = {
            "/": self._ghost_responder,
            "/version": self._version_responder,
            "/exit": self._exit_responder,
        }
        if path in responses:
            responses[path]()

    def _ghost_responder(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        _str = f"""{{
  "ProtocolVersion": 1,
  "WebSocketPort": {servers.websocket_server.port}
}}"""
        self.wfile.write(_str.encode("utf-8"))

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
        global RUNNING
        RUNNING = False


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


class Neovim:
    def __init__(self, address):
        self.address = address
        self.handle = pynvim.attach("socket", path=address)


ghost_port = os.environ.get("GHOSTTEXT_SERVER_PORT", 4001)
neovim_socket = os.environ.get("NVIM_LISTEN_ADDRESS")

_check_nvim_socket(neovim_socket)
neovim = Neovim(neovim_socket)


servers = Server()
servers.http_server_thread.start()
servers.websocket_server_thread.start()
RUNNING = True
while RUNNING:
    continue
sys.exit()

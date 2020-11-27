import http.server
import random
import socket
import os

# Get config from environment variables
ghost_port: int = (
    os.environ.get("GHOSTTEXT_SERVER_PORT")  # i.e is not None
    and os.environ.get("GHOSTTEXT_SERVER_PORT").isdigit()
    and int(os.environ.get("GHOSTTEXT_SERVER_PORT"))
    or 4001
)

# Global objects to get replaced
ghost_websocket = None


class GhostGETRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global ghost_websocket
        ghost_websocket = self.create_ghost_websocket()
        self._ghost_responder()

    def _ghost_responder(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            f"""{{  "ProtocolVersion": 1,
  "WebSocketPort": {self.ghost_websocket.port}
}}"""
        )

    def _port_occupied(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_checker:
            return socket_checker.connect_ex(("localhost", port)) == 0

    def create_ghost_websocket(self):
        while True:
            random_port = random.randint(9000, 65535)
            if not self._port_occupied(random_port):
                return GhostCreateWebSocket(random_port)


class GhostCreateWebSocket:  # replace name with GhostWebSocket?
    def __init__(self, port):
        self.port = port
        return GhostWebSocket


class GhostWebSocket(SimpleWebSocket):
    pass

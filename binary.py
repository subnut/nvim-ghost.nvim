import os
import sys
import random
import socket
import requests
import tempfile
import http.server
import urllib.parse
import threading
import pynvim
from typing import Dict, List
from simple_websocket_server import WebSocketServer, WebSocket

BUILD_VERSION = "0.1.0.02"
TEMP_FILEPATH = os.path.join(tempfile.gettempdir(), "nvim-ghost.nvim.port")
neovim_focused_address = None  # Need to be defined before Neovim class, else NameError


def _port_occupied(port):
    """
    If port is occupied, returns True. Else returns False

    :param port int: port number to check
    """
    port = int(port)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_checker:
        return socket_checker.connect_ex(("localhost", port)) == 0


def _detect_running_port():
    if os.path.exists(TEMP_FILEPATH):
        with open(TEMP_FILEPATH) as file:
            old_port = file.read()
        try:
            response = requests.get(f"http://localhost:{old_port}")
            if response.ok:
                return old_port
        except requests.exceptions.ConnectionError:
            return False
    return False


def _get_running_version():
    if _detect_running_port():
        response = requests.get(f"http://localhost:{_detect_running_port()}/version")
        if response.ok:
            return response.text


def _stop_running(port):
    port = int(port)
    response = requests.get(f"http://localhost:{port}/exit")
    return response.status_code


def _store_port():
    with open(TEMP_FILEPATH, "w+") as file:
        file.write(str(servers.http_server.server_port))


def _stop_if_already_running():
    if _detect_running_port():
        running_port = _detect_running_port()
        if running_port == str(ghost_port):
            if _get_running_version() == str(BUILD_VERSION):
                print("Server already running")
                sys.exit()
        _stop_running(running_port)
        while True:
            if not _port_occupied(running_port):
                break


class ArgParser:
    def __init__(self):
        self.argument_handlers = {
            "--focus": self._focus,
            "--closed": self._closed,
            "--port": self._port,
        }

    def parse_args(self, args=sys.argv[1:]):
        for index, argument in enumerate(args):
            if argument == "--version":
                self._version()
            if argument.startswith("--"):
                if index + 1 >= len(args):
                    sys.exit(f"Argument {argument} needs a value.")
                self.argument_handlers[argument](args[index + 1])

    def _version(self):
        print(BUILD_VERSION)
        sys.exit()

    def _focus(self, address: str):
        global neovim_focused_address
        neovim_focused_address = address

    def _closed(self, address):
        for item in NEOVIM_OBJECTS[address]:
            item.close()

    def _port(self, port: str):
        if not port.isdigit():
            sys.exit("Invalid port")
        global ghost_port
        ghost_port = int(port)


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
        self.address = neovim_focused_address
        global NEOVIM_OBJECTS
        if not NEOVIM_OBJECTS.__contains__(neovim_focused_address):
            NEOVIM_OBJECTS[neovim_focused_address] = []
        if NEOVIM_OBJECTS[neovim_focused_address].count(self) == 0:
            NEOVIM_OBJECTS[neovim_focused_address].append(self)
        print(NEOVIM_OBJECTS)

    def handle_close(self):
        global NEOVIM_OBJECTS
        NEOVIM_OBJECTS[self.address].remove(self)
        print(NEOVIM_OBJECTS)


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
    def __init__(self, address=neovim_focused_address):
        self.address = address
        self._check_nvim_socket()
        self.handle = pynvim.attach("socket", path=address)

    def _check_nvim_socket(self):
        if not os.path.exists(self.address):
            sys.exit("Specified neovim socket does not exist")


NEOVIM_OBJECTS: Dict[str, List[GhostWebSocketHandler]] = {}

ghost_port = os.environ.get("GHOSTTEXT_SERVER_PORT", 4001)
neovim_focused_address = os.environ.get("NVIM_LISTEN_ADDRESS", None)

argparser = ArgParser()
argparser.parse_args()

if neovim_focused_address is None:
    sys.exit("NVIM_LISTEN_ADDRESS environment variable not set.")

_stop_if_already_running()
servers = Server()
servers.http_server_thread.start()
servers.websocket_server_thread.start()
_store_port()
RUNNING = True
while RUNNING:
    continue
os.remove(TEMP_FILEPATH)  # Remove port
sys.exit()

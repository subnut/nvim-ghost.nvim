import http.server
import json
import os
import random
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
from typing import Dict, List, Optional, Union

import pynvim
import requests
from simple_websocket_server import WebSocket, WebSocketServer

BUILD_VERSION: str = "v0.0.16"
# TEMP_FILEPATH is used to store the port of the currently running server
TEMP_FILEPATH: str = os.path.join(tempfile.gettempdir(), "nvim-ghost.nvim.port")
WINDOWS: bool = os.name == "nt"
LOCALHOST: str = "127.0.0.1" if WINDOWS else "localhost"

POLL_INTERVAL: float = 5  # Server poll interval in seconds
PERSIST: bool = False  # Permanent daemon mode (aka. forking) not implemented yet.
START_SERVER: bool = False

neovim_focused_address: Optional[str] = os.environ.get("NVIM_LISTEN_ADDRESS", None)
_ghost_port: Optional[str] = os.environ.get("GHOSTTEXT_SERVER_PORT", None)


def _port_occupied(port) -> bool:
    """
    If port is occupied, returns True. Else returns False

    :param port int: port number to check
    """
    port = int(port)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_checker:
        return socket_checker.connect_ex((LOCALHOST, port)) == 0


def _detect_running_port() -> Union[int, bool]:
    if os.path.exists(TEMP_FILEPATH):
        with open(TEMP_FILEPATH) as file:
            old_port = file.read()
        try:
            response = requests.get(f"http://{LOCALHOST}:{old_port}/is_ghost_binary")
            if response.ok and response.text == "True":
                return int(old_port)
        except requests.exceptions.ConnectionError:
            return False
    return False


def _get_running_version() -> Optional[str]:
    port = _detect_running_port()
    if port:
        response = requests.get(f"http://{LOCALHOST}:{port}/version")
        if response.ok:
            return response.text


def _stop_running(port):
    port = int(port)
    response = requests.get(f"http://{LOCALHOST}:{port}/exit")
    return response.status_code


def _store_port():
    with open(TEMP_FILEPATH, "w+") as file:
        file.write(str(servers.http_server.server_port))


def _exit_script_if_server_already_running():
    if _detect_running_port():
        running_port = _detect_running_port()
        if running_port == ghost_port:
            if _get_running_version() == str(BUILD_VERSION):
                print("Server already running")
                sys.exit()
        _stop_running(running_port)
        while True:
            if not _port_occupied(running_port):
                break


def _check_if_socket(filepath) -> bool:
    if WINDOWS:
        _dir = os.path.dirname(filepath)
        _filename = filepath.split(_dir)[1]
        return os.listdir(_dir).__contains__(_filename)
    else:
        if os.path.exists(filepath):
            if os.path.stat.S_ISSOCK(os.stat(filepath).st_mode):
                return True
    return False


class ArgParser:
    def __init__(self):

        # arguments that take a value
        self.argument_handlers_data = {
            "--port": self._port,
            "--focus": self._focus,
            "--buffer-closed": self._buffer_closed,
            "--session-closed": self._session_closed,
            "--update-buffer-text": self._update_buffer_text,
        }

        # arguments that don't take a value
        self.argument_handlers_nodata = {
            "--session-closed": self._session_closed,
            "--start-server": self._start,
            "--nopersist": self._nopersist,
            "--persist": self._persist,
            "--version": self._version,
            "--focus": self._focus,
            "--help": self._help,
            "--kill": self._kill,
            "--exit": self._kill,
        }

        # GET requests to make to the running server
        self.server_requests = []

    def parse_args(self, args=sys.argv[1:]):
        for index, argument in enumerate(args):
            if argument.startswith("--"):
                # First parse data_args
                # Then parse nodata_args
                # Because some data_args may also work as nodata_args
                # i.e. they have some default value
                # e.g. --focus
                if argument in self.argument_handlers_data:
                    if index + 1 >= len(args):
                        # i.e. there is no argument after this argument
                        if argument not in self.argument_handlers_nodata:
                            # i.e. the argument MUST get a value
                            sys.exit(f"Argument {argument} needs a value.")
                    else:
                        self.argument_handlers_data[argument](args[index + 1])
                if argument in self.argument_handlers_nodata:
                    self.argument_handlers_nodata[argument]()

    def _version(self):
        print(BUILD_VERSION)
        sys.exit()

    def _help(self):
        # print out the arguments allowed
        # for reference purposes only
        for item in self.argument_handlers_nodata:
            print(item)
        for item in self.argument_handlers_data:
            print(item, "<data>")
        sys.exit()

    def _start(self):
        global START_SERVER
        START_SERVER = True

    def _persist(self):
        global PERSIST
        PERSIST = True
        self.server_requests.append("/persist")

    def _nopersist(self):
        global PERSIST
        PERSIST = False
        self.server_requests.append("/nopersist")

    def _port(self, port: str):
        global _ghost_port
        _ghost_port = port

    def _focus(self, address=os.environ.get("NVIM_LISTEN_ADDRESS")):
        if address is not None:
            global neovim_focused_address
            neovim_focused_address = address
            self.server_requests.append(f"/focus?focus={address}")

    def _buffer_closed(self, buffer):
        self.server_requests.append(f"/buffer-closed?{buffer}")

    def _session_closed(self, address=os.environ.get("NVIM_LISTEN_ADDRESS")):
        if address is not None:
            self.server_requests.append(f"/session-closed?session={address}")

    def _update_buffer_text(self, buffer):
        with sys.stdin as stdin:
            data = stdin.read()
        self.server_requests.append(f"/update-buffer-text?{buffer}={data}")

    def _kill(self):
        self.server_requests.append("/exit")


class GhostHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = parsed_url.query

        responses_nodata = {
            "/": self._ghost_responder,
            "/version": self._version_responder,
            "/exit": self._exit_responder,
            "/kill": self._exit_responder,
            "/persist": self._persist_responder,
            "/nopersist": self._nopersist_responder,
            "/is_ghost_binary": self._sanityCheck_responder,
        }

        responses_data = {
            "/focus": self._focus_responder,
            "/buffer-closed": self._buffer_closed_responder,
            "/session-closed": self._session_closed_responder,
            "/update-buffer-text": self._update_buffer_text_responder,
        }

        if path in responses_nodata:
            responses_nodata[path]()

        if path in responses_data:
            responses_data[path](query)

    def _ghost_responder(self):
        if neovim_focused_address is not None:
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

    def _persist_responder(self):
        global PERSIST
        PERSIST = True
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(f"PERSIST={PERSIST}".encode("utf-8"))

    def _nopersist_responder(self):
        global PERSIST
        PERSIST = False
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(f"PERSIST={PERSIST}".encode("utf-8"))

    def _sanityCheck_responder(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write("True".encode("utf-8"))

    def _focus_responder(self, query_string):
        _, address = urllib.parse.parse_qsl(query_string)[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(address.encode("utf-8"))
        global neovim_focused_address
        neovim_focused_address = address

    def _buffer_closed_responder(self, buffer):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(buffer.encode("utf-8"))
        global WEBSOCKET_PER_BUFFER_PER_NEOVIM_ADDRESS
        WEBSOCKET_PER_BUFFER_PER_NEOVIM_ADDRESS[neovim_focused_address][buffer].close()
        del WEBSOCKET_PER_BUFFER_PER_NEOVIM_ADDRESS[neovim_focused_address][buffer]

    def _session_closed_responder(self, query_string):
        _, address = urllib.parse.parse_qsl(query_string)[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(address.encode("utf-8"))
        global WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS
        if WEBSOCKET_PER_BUFFER_PER_NEOVIM_ADDRESS.__contains__(address):
            for item in WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS[address]:
                item.close()
            del WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS[address]
        if not PERSIST and len(WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS) == 0:
            global RUNNING
            RUNNING = False
        global neovim_focused_address
        neovim_focused_address = None

    # fmt: off
    def _update_buffer_text_responder(self, query_string):
        buffer, text = urllib.parse.parse_qsl(query_string)[0]
        text = json.dumps({"text": str(text), "selections": []})
        WEBSOCKET_PER_BUFFER_PER_NEOVIM_ADDRESS[neovim_focused_address][buffer].send_text(text)  # noqa
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))
    # fmt: on


class GhostWebSocket(WebSocket):
    # fmt: off
    def handle(self):
        print(json.loads(self.data))
        data = json.loads(self.data)
        data_syntax = data["syntax"]
        data_text: str = data["text"]
        data_text_split = data_text.split("\n")
        handle = self.neovim_handle
        buffer = self.buffer
        self.neovim_handle.command(f"call nvim_ghost#delete_buffer_autocmds({self.buffer})")  # noqa
        handle.command(f"call nvim_buf_set_lines({buffer},0,-1,0,{data_text_split})")  # noqa
        handle.command(f"call nvim_buf_set_option({buffer},'filetype','{data_syntax}')")  # noqa
        self.neovim_handle.command(f"call nvim_ghost#setup_buffer_autocmds({self.buffer})")  # noqa

    def connected(self):
        self.address = neovim_focused_address
        self.neovim_handle = pynvim.attach("socket", path=neovim_focused_address)
        self.buffer = self.neovim_handle.command_output("echo nvim_create_buf(1,1)")
        self.neovim_handle.command(f"call nvim_buf_set_var({self.buffer}, 'nvim_ghost_timer', 0)")  # noqa
        self.neovim_handle.command(f"call nvim_ghost#setup_buffer_autocmds({self.buffer})")  # noqa
        self.neovim_handle.command(f"tabe | {self.buffer}buffer")
        global WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS
        if not WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS.__contains__(self.address):
            WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS[self.address] = []
        if WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS[self.address].count(self) == 0:
            WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS[self.address].append(self)
        print(WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS)
        global WEBSOCKET_PER_BUFFER_PER_NEOVIM_ADDRESS
        if not WEBSOCKET_PER_BUFFER_PER_NEOVIM_ADDRESS.__contains__(self.address):
            WEBSOCKET_PER_BUFFER_PER_NEOVIM_ADDRESS[self.address] = {}
        WEBSOCKET_PER_BUFFER_PER_NEOVIM_ADDRESS[self.address][self.buffer] = self
    # fmt: on

    def handle_close(self):
        global WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS
        WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS[self.address].remove(self)
        self.neovim_handle.command(f"bdelete {self.buffer}")
        self.neovim_handle.close()
        print(WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS)
        del WEBSOCKET_PER_BUFFER_PER_NEOVIM_ADDRESS[self.address][self.buffer]

    def send_text(self, text):
        self.send_message(text)


class GhostWebSocketServer(WebSocketServer):
    def __init__(self, host, port, websocketclass, **kwargs):
        self.port = port
        super().__init__(host, port, websocketclass, **kwargs)


class Server:
    # fmt: off
    def __init__(self):
        self.http_server = self._http_server()
        self.websocket_server = self._websocket_server()
        self.http_server_thread = threading.Thread(
            target=self.http_server.serve_forever,
            args=(POLL_INTERVAL,),
            daemon=True
        )
        self.websocket_server_thread = threading.Thread(
            target=self.websocket_server.serve_forever,
            daemon=True,
        )
    # fmt: on

    def _http_server(self):
        if not _port_occupied(ghost_port):
            return http.server.HTTPServer(
                (LOCALHOST, ghost_port), GhostHTTPRequestHandler
            )
        else:
            sys.exit("Port Occupied")

    def _websocket_server(self):
        while True:
            random_port = random.randint(9000, 65535)
            if not _port_occupied(random_port):
                return GhostWebSocketServer(LOCALHOST, random_port, GhostWebSocket)


class Neovim:
    def __init__(self, address=neovim_focused_address):
        self.address = address

    def get_handle(self):
        return pynvim.attach("socket", path=self.address)


WEBSOCKETS_PER_NEOVIM_SOCKET_ADDRESS: Dict[str, List[GhostWebSocket]] = {}
WEBSOCKET_PER_BUFFER_PER_NEOVIM_ADDRESS: Dict[str, Dict[str, GhostWebSocket]] = {}

argparser = ArgParser()
argparser.parse_args()

# fmt: off
if _ghost_port is None:
    _ghost_port = "4001"
if not _ghost_port.isdigit():
    if neovim_focused_address is not None:
        Neovim().get_handle().command("echom '[nvim-ghost] Invalid port. Please set $GHOSTTEXT_SERVER_PORT to a valid port.'")  # noqa
    sys.exit("Port must be a number")
ghost_port: int = int(_ghost_port)
# fmt: on

if START_SERVER and not PERSIST and neovim_focused_address is None:
    sys.exit("NVIM_LISTEN_ADDRESS environment variable not set.")

if START_SERVER:
    _exit_script_if_server_already_running()
    servers = Server()
    servers.http_server_thread.start()
    servers.websocket_server_thread.start()
    print("Servers started")
    if neovim_focused_address is not None:
        Neovim().get_handle().command("echom '[nvim-ghost] Servers started'")
    _store_port()
    RUNNING = True
    while RUNNING:
        time.sleep(POLL_INTERVAL)
        continue
    os.remove(TEMP_FILEPATH)  # Remove port
    sys.exit()

elif not _detect_running_port():
    sys.exit("Server not running and --start-server not specified")

# Send the GET requests wanted by ArgParser() to the running server
ghost_port: int = _detect_running_port()
if len(argparser.server_requests) > 0:
    for url in argparser.server_requests:
        request = requests.get(f"http://{LOCALHOST}:{ghost_port}{url}")
        if request.ok:
            print("Sent", url)

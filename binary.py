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

BUILD_VERSION: str = "v0.0.26"
# TEMP_FILEPATH is used to store the port of the currently running server
TEMP_FILEPATH: str = os.path.join(tempfile.gettempdir(), "nvim-ghost.nvim.port")
WINDOWS: bool = os.name == "nt"
LOCALHOST: str = "127.0.0.1" if WINDOWS else "localhost"

POLL_INTERVAL: float = 5  # Server poll interval in seconds
START_SERVER: bool = False
LOGGING_ENABLED: bool = bool(os.environ.get("NVIM_GHOST_LOGGING_ENABLED", False))

neovim_focused_address: Optional[str] = os.environ.get("NVIM_LISTEN_ADDRESS", None)
_ghost_port: Optional[str] = os.environ.get("GHOSTTEXT_SERVER_PORT", None)

# chdir to folder containing binary
# otherwise the logs are generated whereever the server was started from (i.e curdir)
# which..... isn't good. You'd have stdout.log and stderr.log files everywhere!
os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
# we use sys.argv[0] because __file__ doesn't give proper results with pyinstaller
# See: https://stackoverflow.com/a/53511380


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
                if neovim_focused_address is not None:
                    Neovim().get_handle().command(
                        "echom '[nvim-ghost] Server running'"
                    )  # noqa
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
            "--session-closed": self._session_closed,
        }

        # arguments that don't take a value
        self.argument_handlers_nodata = {
            "--log-to-file": self._log_to_file,
            "--session-closed": self._session_closed,
            "--start-server": self._start,
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
                elif argument in self.argument_handlers_nodata:
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

    def _port(self, port: str):
        global _ghost_port
        _ghost_port = port

    def _focus(self, address=os.environ.get("NVIM_LISTEN_ADDRESS")):
        if address is not None:
            global neovim_focused_address
            neovim_focused_address = address
            self.server_requests.append(f"/focus?focus={address}")

    def _session_closed(self, address=os.environ.get("NVIM_LISTEN_ADDRESS")):
        if address is not None:
            self.server_requests.append(f"/session-closed?session={address}")

    def _kill(self):
        self.server_requests.append("/exit")

    def _log_to_file(self):
        global LOGGING_ENABLED
        LOGGING_ENABLED = True


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
            "/is_ghost_binary": self._sanityCheck_responder,
        }

        responses_data = {
            "/focus": self._focus_responder,
            "/session-closed": self._session_closed_responder,
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
        print(time.strftime("[%H:%M:%S]:"), "Received /exit")
        global RUNNING
        RUNNING = False

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
        if neovim_focused_address != address:
            neovim_focused_address = address
            print(time.strftime("[%H:%M:%S]:"), f"Focus {address}")

    def _session_closed_responder(self, query_string):
        _, address = urllib.parse.parse_qsl(query_string)[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(address.encode("utf-8"))
        print(time.strftime("[%H:%M:%S]:"), f"{address} session closed")
        global WEBSOCKET_PER_NEOVIM_ADDRESS
        if WEBSOCKET_PER_NEOVIM_ADDRESS.__contains__(address):
            for websocket in WEBSOCKET_PER_NEOVIM_ADDRESS[address]:
                websocket.close()
            WEBSOCKET_PER_NEOVIM_ADDRESS.__delitem__(address)
        global neovim_focused_address
        if address == neovim_focused_address:
            neovim_focused_address = None


class GhostWebSocket(WebSocket):
    def handle(self):
        print(time.strftime("[%H:%M:%S]:"), f"{self.address[1]} got", self.data)
        self._handle_neovim_notifications = False
        neovim_handle = self.neovim_handle
        data = json.loads(self.data)
        _syntax = data["syntax"]
        _url = data["url"]
        _text: str = data["text"]
        _text_split = _text.split("\n")
        buffer_handle = self.buffer_handle
        neovim_handle.api.buf_set_lines(buffer_handle, 0, -1, 0, _text_split)
        neovim_handle.api.buf_set_option(buffer_handle, "filetype", _syntax)
        self._handle_neovim_notifications = True
        if self.trigger_autocmd:
            self.trigger_autocmd = False
            self._trigger_autocmds(_url)

    def connected(self):
        self.neovim_address = neovim_focused_address
        self.neovim_handle = pynvim.attach("socket", path=self.neovim_address)
        print(
            time.strftime("[%H:%M:%S]:"),
            "Connected",
            ":".join([str(_) for _ in self.address]),
            "to",
            self.neovim_address,
        )
        self.buffer_handle = self.neovim_handle.api.create_buf(False, True)
        self.neovim_handle.api.buf_set_option(self.buffer_handle, "bufhidden", "wipe")
        self.neovim_handle.command(f"tabe | {self.buffer_handle.number}buffer")
        self._handle_neovim_notifications = True
        self._start_neovim_listener()
        global WEBSOCKET_PER_NEOVIM_ADDRESS
        if not WEBSOCKET_PER_NEOVIM_ADDRESS.__contains__(self.neovim_address):
            WEBSOCKET_PER_NEOVIM_ADDRESS[self.neovim_address] = []
        WEBSOCKET_PER_NEOVIM_ADDRESS[self.neovim_address].append(self)
        self.trigger_autocmd = True

    def handle_close(self):
        print(
            time.strftime("[%H:%M:%S]:"),
            ":".join([str(_) for _ in self.address]),
            "websocket closed",
        )
        self.neovim_handle.command(f"bdelete {self.buffer_handle.number}")
        self.neovim_handle.close()
        self.loop_neovim_handle.stop_loop()
        self.loop_neovim_handle.close()
        global WEBSOCKET_PER_NEOVIM_ADDRESS
        WEBSOCKET_PER_NEOVIM_ADDRESS[self.neovim_address].remove(self)
        if len(WEBSOCKET_PER_NEOVIM_ADDRESS[self.neovim_address]) == 0:
            WEBSOCKET_PER_NEOVIM_ADDRESS.__delitem__(self.neovim_address)

    def _start_neovim_listener(self):
        threading.Thread(target=self._neovim_listener, daemon=True).start()

    def _neovim_listener(self):
        self.loop_neovim_handle = pynvim.attach("socket", path=self.neovim_address)
        self.loop_neovim_handle.subscribe("nvim_buf_lines_event")
        self.loop_neovim_handle.subscribe("nvim_buf_detach_event")
        self.loop_neovim_handle.api.buf_attach(self.buffer_handle, False, {})
        self.loop_neovim_handle.run_loop(None, self._neovim_handler)

    def _neovim_handler(self, *args):
        if not self._handle_neovim_notifications:
            return
        event = args[0]
        if event == "nvim_buf_detach_event":
            self.close()
        if event == "nvim_buf_lines_event":
            handle = self.loop_neovim_handle
            text = handle.api.buf_get_lines(self.buffer_handle, 0, -1, False)
            text = "\n".join(text)
            self._send_text(text)

    def _send_text(self, text):
        text = json.dumps({"text": str(text), "selections": []})
        self.send_message(text)
        print(time.strftime("[%H:%M:%S]:"), f"{self.address[1]} sent", text)

    def _trigger_autocmds(self, url):
        self.neovim_handle.command(f"doau nvim_ghost_user_autocommands User {url}")
        pass


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


WEBSOCKET_PER_NEOVIM_ADDRESS: Dict[str, List[GhostWebSocket]] = {}

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

if START_SERVER:
    _exit_script_if_server_already_running()
    servers = Server()
    servers.http_server_thread.start()
    servers.websocket_server_thread.start()
    if LOGGING_ENABLED:
        sys.stdout = open("stdout.log", "w", buffering=1)
        sys.stderr = open("stderr.log", "w", buffering=1)
        print(time.strftime("%A, %d %B %Y, %H:%M:%S"))
        print(f"$NVIM_LISTEN_ADDRESS: {neovim_focused_address}")
        print(f"binary {BUILD_VERSION}")
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

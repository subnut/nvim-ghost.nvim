import http.server
import json
import os
import random
import signal
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

import pynvim
import requests
from simple_websocket_server import WebSocket
from simple_websocket_server import WebSocketServer

BUILD_VERSION: str = "v0.0.37"

# TEMP_FILEPATH is used to store the port of the currently running server
TEMP_FILEPATH: str = os.path.join(tempfile.gettempdir(), "nvim-ghost.nvim.port")
WINDOWS: bool = os.name == "nt"
LOCALHOST: str = "127.0.0.1" if WINDOWS else "localhost"
LOGGING_ENABLED: bool = bool(os.environ.get("NVIM_GHOST_LOGGING_ENABLED", False))

neovim_focused_address: Optional[str] = os.environ.get("NVIM_LISTEN_ADDRESS", None)
_ghost_port: str = os.environ.get("GHOSTTEXT_SERVER_PORT", "4001")


if not _ghost_port.isdigit():
    if neovim_focused_address is not None:
        with pynvim.attach("socket", path=neovim_focused_address) as _handle:
            # fmt: off
            _handle.command("echom '[nvim-ghost] Invalid port. Please set $GHOSTTEXT_SERVER_PORT to a valid port.'")  # noqa
            # fmt: on
    sys.exit("Port must be a number")
GHOST_PORT: int = int(_ghost_port)


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


def _get_running_version(port) -> Optional[str]:
    response = requests.get(f"http://{LOCALHOST}:{port}/version")
    if response.ok:
        return response.text


def _stop_running_server(port) -> None:
    response = requests.get(f"http://{LOCALHOST}:{port}/exit")
    return response.status_code


def _store_port() -> None:
    with open(TEMP_FILEPATH, "w+") as file:
        file.write(str(servers.http_server.server_port))


def _exit_script_if_server_already_running() -> None:
    running_port = _detect_running_port()
    if running_port:
        if running_port == GHOST_PORT:
            if _get_running_version(running_port) == BUILD_VERSION:
                print("Server already running")
                if neovim_focused_address is not None:
                    _handle = pynvim.attach("socket", path=neovim_focused_address)
                    _handle.command("echom '[nvim-ghost] Server running'")
                    _handle.close()
                sys.exit()
        # Server is outdated. Stop it.
        _stop_running_server(running_port)
        # Wait till the server has stopped
        while True:
            if not _port_occupied(running_port):
                break


class ArgParser:
    """
    Parser for cli arguments.

    """

    def __init__(self):
        self.argument_handlers = {
            "--enable-logging": self._enable_logging,
            "--version": self._version,
            "--help": self._help,
        }

        # GET requests to make to the running server
        self.server_requests = []

    def parse_args(self, args=sys.argv[1:]):
        for index, argument in enumerate(args):
            if argument.startswith("--"):
                if argument in self.argument_handlers:
                    self.argument_handlers[argument]()

    def _version(self):
        print(BUILD_VERSION)
        sys.exit()

    def _help(self):
        for item in self.argument_handlers:
            print(item)
        sys.exit()

    def _enable_logging(self):
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
            "/is_ghost_binary": self._sanity_check_responder,
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
        """
        The actual part. The browser extension is calling us.

        """

        if neovim_focused_address is None:
            # There's no neovim instance to handle our request
            return
        payload = (
            """\
{
  "ProtocolVersion": 1,
  "WebSocketPort": {%s}
}"""
            % servers.websocket_server.port
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload.encode("utf-8"))
        # NOTE: We didn't use _respond because it sets Content-Type to
        # text/plain, but the protocol mentions that the Content-Type should be
        # application/json

    def _version_responder(self):
        """
        Somebody wants to check the version of the running server

        """
        self._respond(BUILD_VERSION)

    def _exit_responder(self):
        """
        We have been told to exit

        """
        self._respond("Exiting...")
        print(time.strftime("[%H:%M:%S]:"), "Received /exit")
        global stop_servers
        stop_servers()

    def _sanity_check_responder(self):
        """
        Somebody wants to check if this is _actually_ the correct server

        """
        self._respond("True")

    def _focus_responder(self, query_string):
        """
        A neovim instance is reporting that it has gained focus

        :param query_string str: The query part of the URL
        """
        _, address = urllib.parse.parse_qsl(query_string)[0]
        self._respond(address)
        global neovim_focused_address
        if neovim_focused_address != address:
            neovim_focused_address = address
            print(time.strftime("[%H:%M:%S]:"), f"Focus {address}")

    def _session_closed_responder(self, query_string):
        """
        A neovim instance is reporting that it has been closed

        :param query_string str: The query part of the URL
        """
        _, address = urllib.parse.parse_qsl(query_string)[0]
        self._respond(address)
        print(time.strftime("[%H:%M:%S]:"), f"{address} session closed")
        global WEBSOCKET_PER_NEOVIM_ADDRESS
        if WEBSOCKET_PER_NEOVIM_ADDRESS.__contains__(address):
            for websocket in WEBSOCKET_PER_NEOVIM_ADDRESS[address]:
                websocket.close()
            WEBSOCKET_PER_NEOVIM_ADDRESS.__delitem__(address)
        global neovim_focused_address
        if address == neovim_focused_address:
            neovim_focused_address = None

    def _respond(self, text):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))


class GhostWebSocket(WebSocket):
    def handle(self):
        print(time.strftime("[%H:%M:%S]:"), f"{self.address[1]} got", self.data)

        # Stop handling notifications caused by us. Mitigates race condition.
        self._handle_neovim_notifications = False

        neovim_handle = self.neovim_handle
        data = json.loads(self.data)
        _filetype = data["syntax"]
        _url = data["url"]
        _text: str = data["text"]
        _text_split = _text.split("\n")
        buffer_handle = self.buffer_handle
        neovim_handle.api.buf_set_lines(buffer_handle, 0, -1, 0, _text_split)

        # Resume handling notifications. We're done changing the buffer text.
        self._handle_neovim_notifications = True

        # Save the text that we just set. So that, if a nvim_buf_lines_event
        # wants to sent the exact same text, we can stop it.  i.e. mitigate
        # race condition even more
        self._last_set_text = _text

        if not self.handled_first_message:
            # We hadn't handled the first message yet.
            # i.e. this is the first message, and we have already handled it.
            # So we _have_ handled the first message, you buffoon.
            self.handled_first_message = True
            # Since this is the first message, it means we haven't set the
            # filetype yet. So, let's set the filetype now.
            neovim_handle.api.buf_set_option(buffer_handle, "filetype", _filetype)
            self._trigger_autocmds(_url)
            self._last_set_filetype = _filetype

        if not _filetype == self._last_set_filetype:
            # The filetype has changed in the browser
            handle = neovim_handle
            buffer = buffer_handle
            currently_set_filetype = handle.api.buf_get_option(buffer, "filetype")
            if self._last_set_filetype == currently_set_filetype:
                # user hasn't set a custom filetype
                neovim_handle.api.buf_set_option(buffer_handle, "filetype", _filetype)
                self._last_set_filetype = _filetype
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
        self.handled_first_message = False

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
            if self._last_set_text is not None:
                if text == self._last_set_text:
                    # Avoid sending the text we just set. Race conditioon
                    # mitigation
                    return
                # Text has been changed by user. _last_set_text is now outdated
                # and invalid.
                self._last_set_text = None
            self._send_text(text)

    def _send_text(self, text):
        text = json.dumps({"text": str(text), "selections": []})
        self.send_message(text)
        print(time.strftime("[%H:%M:%S]:"), f"{self.address[1]} sent", text)

    def _trigger_autocmds(self, url):
        self.neovim_handle.command(f"doau nvim_ghost_user_autocommands User {url}")


class GhostWebSocketServer(WebSocketServer):
    # This is nessecary because the imported WebSocketServer does not store
    # it's port number.   Yes, I have seen the source code. It doesn't.
    def __init__(self, host, port, websocketclass, **kwargs):
        self.port = port
        super().__init__(host, port, websocketclass, **kwargs)


class Server:
    # fmt: off
    def __init__(self):
        self.http_server = self._http_server()
        self.websocket_server = self._websocket_server()
        # Do not daemonize one of the threads. It will keep the binary running
        # after the main thread has finished executing everything.
        self.http_server_thread = threading.Thread(
            target=self.http_server.serve_forever,
            args=(None,),
        )
        self.websocket_server_thread = threading.Thread(
            target=self.websocket_server.serve_forever,
            daemon=True,
        )
    # fmt: on

    def _http_server(self):
        if not _port_occupied(GHOST_PORT):
            return http.server.HTTPServer(
                (LOCALHOST, GHOST_PORT), GhostHTTPRequestHandler
            )
        else:
            sys.exit("Port Occupied")

    def _websocket_server(self):
        while True:
            random_port = random.randint(9000, 65535)
            if not _port_occupied(random_port):
                return GhostWebSocketServer(LOCALHOST, random_port, GhostWebSocket)


WEBSOCKET_PER_NEOVIM_ADDRESS: Dict[str, List[GhostWebSocket]] = {}

argparser = ArgParser()
argparser.parse_args()

# Start servers
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
    with pynvim.attach("socket", path=neovim_focused_address) as _handle:
        _handle.command("echom '[nvim-ghost] Servers started'")
_store_port()


def stop_servers():
    os.remove(TEMP_FILEPATH)  # Remove port
    print("Exiting...")
    sys.exit()


def signal_handler(_signal, _):
    _signal_name = signal.Signals(_signal).name
    print(time.strftime("[%H:%M:%S]:"), f"Caught: {_signal_name}")
    if _signal in (signal.SIGINT, signal.SIGTERM):
        stop_servers()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

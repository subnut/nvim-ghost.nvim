import json
import os
import platform
import random
import signal
import socket
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from typing import Dict
from typing import List
from typing import Optional

import pynvim
import requests
from simple_websocket_server import WebSocket
from simple_websocket_server import WebSocketServer

BUILD_VERSION: str = "v0.4.1"

WINDOWS: bool = os.name == "nt"
LOCALHOST: str = "127.0.0.1" if WINDOWS else "localhost"
SUPER_QUIET: bool = bool(os.environ.get("NVIM_GHOST_SUPER_QUIET", False))
SERVER_PORT: str = os.environ.get("GHOSTTEXT_SERVER_PORT", "4001")
FOCUSED_NVIM_ADDRESS = os.environ.get("NVIM_LISTEN_ADDRESS", None)
LOGGING_ENABLED: bool = False
VERBOSE_LOGGING: bool = bool(os.environ.get("NVIM_GHOST_VERBOSE_LOGGING"))
if os.environ.get("NVIM_GHOST_LOGGING_ENABLED") is not None:
    if os.environ.get("NVIM_GHOST_LOGGING_ENABLED").isdigit():
        LOGGING_ENABLED = bool(int(os.environ.get("NVIM_GHOST_LOGGING_ENABLED")))
    else:
        sys.exit("Invalid value of $NVIM_GHOST_LOGGING_ENABLED")


if not SERVER_PORT.isdigit():
    if FOCUSED_NVIM_ADDRESS is not None:
        with pynvim.attach("socket", path=FOCUSED_NVIM_ADDRESS) as nvim_handle:
            if not SUPER_QUIET:
                nvim_handle.command(
                    "echom '[nvim-ghost] Invalid port. "
                    "Please set $GHOSTTEXT_SERVER_PORT to a valid port.'"
                )
    sys.exit("Port must be a number")
GHOST_PORT: int = int(SERVER_PORT)


# chdir to folder containing binary
# otherwise the logs are generated whereever the server was started from (i.e curdir)
# which..... isn't good. You'd have stdout.log and stderr.log files everywhere!
os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
# we use sys.argv[0] because __file__ doesn't give proper results with pyinstaller
# See: https://stackoverflow.com/a/53511380


def log(*args, **kwargs):
    print(time.strftime("[%H:%M:%S]:"), *args, **kwargs)


if VERBOSE_LOGGING:
    logv = log
else:
    logv = lambda *args, **kwargs: None


def _port_occupied(port) -> bool:
    """
    If port is occupied, returns True. Else returns False

    :param port int: port number to check
    """
    port = int(port)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_checker:
        return socket_checker.connect_ex((LOCALHOST, port)) == 0


def _is_running() -> Optional[int]:
    """
    Checks whether the server is already running. If yes, returns the port it
    is running on.

    :rtype Optional[int]: Port number of server (if running), else None
    """
    try:
        response = requests.get(f"http://{LOCALHOST}:{SERVER_PORT}/is_ghost_binary")
        if response.ok and response.text == "True":
            return True
    except requests.exceptions.ConnectionError:
        return False


def _get_running_version(port) -> Optional[str]:
    """
    Fetch the version of the currently running server

    :param port int: The port number the server is running on
    :rtype Optional[str]: Version of the running server
    """
    response = requests.get(f"http://{LOCALHOST}:{port}/version")
    if response.ok:
        return response.text


def exit_if_server_already_running():
    if _is_running():
        if _get_running_version(SERVER_PORT) == BUILD_VERSION:
            print("Server already running")
            sys.exit()
        # Server is outdated. Stop it.
        requests.get(f"http://{LOCALHOST}:{SERVER_PORT}/exit")
        # Wait till the server has stopped
        while True:
            if not _port_occupied(SERVER_PORT):
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

    def parse_args(self, args: List[str] = sys.argv[1:]):
        for index, argument in enumerate(args):
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


class GhostHTTPServer(HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = False


class GhostHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = parsed_url.query

        responses_nodata = {
            "/": self._ghost_responder,
            "/version": self._version_responder,
            "/exit": self._exit_responder,
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

        global FOCUSED_NVIM_ADDRESS
        if FOCUSED_NVIM_ADDRESS is None:
            # There's no neovim instance to handle our request
            return
        # In f-strings, to insert literal {, we need to escape it using another {
        # So {{ translates to a single literal {
        payload = f"""\
{{
  "ProtocolVersion": 1,
  "WebSocketPort": {servers.websocket_server.port}
}}"""
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
        log("Received /exit")
        self._respond("Exiting...")
        self.server.running = False

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

        global FOCUSED_NVIM_ADDRESS
        if FOCUSED_NVIM_ADDRESS != address:
            FOCUSED_NVIM_ADDRESS = address
            log(f"Focus {address}")

    def _session_closed_responder(self, query_string):
        """
        A neovim instance is reporting that it has been closed

        :param query_string str: The query part of the URL
        """
        _, address = urllib.parse.parse_qsl(query_string)[0]
        self._respond(address)
        log(f"{address} session closed")

        global FOCUSED_NVIM_ADDRESS
        if address == FOCUSED_NVIM_ADDRESS:
            FOCUSED_NVIM_ADDRESS = None

    def _respond(self, text):
        """
        Send text response with Content-Type text/plain

        :param text str: Text to send
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))


class GhostWebSocket(WebSocket):
    # New message received
    def handle(self):
        logv(f"From {self.address[1]} got", self.data)

        # Extract the data
        data = json.loads(self.data)
        filetype = data["syntax"]
        url = data["url"]
        text = data["text"]
        text_split = text.split("\n")

        # Set the buffer text
        neovim_handle = self.neovim_handle
        buffer_handle = self.buffer_handle
        neovim_handle.api.buf_set_lines(buffer_handle, 0, -1, 0, text_split)

        # Don't handle the next nvim_buf_lines_event until we're done
        self.handle_neovim_notifications = False

        # Save the text that we just set. So that, if a nvim_buf_lines_event
        # wants to sent the exact same text, we can stop it.
        self.last_set_text = text

        if not self.handled_first_message:
            # We hadn't handled the first message yet.
            # i.e. this is the first message, and we have already handled it.
            # So we _have_ handled the first message, you idiot.
            self.handled_first_message = True
            # Since this is the first message, it means we haven't set the
            # filetype yet. So, let's set the filetype now.
            neovim_handle.api.buf_set_option(buffer_handle, "filetype", filetype)
            self._trigger_autocmds(url)
            self.last_set_filetype = filetype

        if not filetype == self.last_set_filetype:
            # i.e. the filetype has changed in the browser
            handle = neovim_handle
            buffer = buffer_handle
            currently_set_filetype = handle.api.buf_get_option(buffer, "filetype")
            if self.last_set_filetype == currently_set_filetype:
                # user hasn't set a custom filetype
                neovim_handle.api.buf_set_option(buffer_handle, "filetype", filetype)
                self.last_set_filetype = filetype
                self._trigger_autocmds(url)

    # New connection
    def connected(self):
        # Create and setup the buffer
        global FOCUSED_NVIM_ADDRESS
        self.neovim_address = FOCUSED_NVIM_ADDRESS
        self.neovim_handle = pynvim.attach("socket", path=self.neovim_address)
        self.buffer_handle = self.neovim_handle.api.create_buf(False, True)
        self.neovim_handle.api.buf_set_option(self.buffer_handle, "bufhidden", "wipe")
        self.neovim_handle.command(f"tabe | {self.buffer_handle.number}buffer")
        self.handle_neovim_notifications = True
        self._start_neovim_listener()

        log(
            "Websocket",
            ":".join([str(_) for _ in self.address]),
            "connected to",
            self.neovim_address,
        )

        # Add it to the records
        if self.neovim_address not in self.nvim_addr_vs_websocket.keys():
            self.nvim_addr_vs_websocket.setdefault(self.neovim_address, self)

        # Since it's a new connection, we haven't handled the first message yet
        self.handled_first_message = False

    # Connection closed
    def handle_close(self):
        log(
            "Websocket",
            ":".join([str(_) for _ in self.address]),
            "closed by browser",
        )

        # Delete buffer and stop event loop
        self.neovim_handle.command(f"bdelete {self.buffer_handle.number}")
        self.neovim_handle.close()
        self.loop_neovim_handle.stop_loop()
        self.loop_neovim_handle.close()

        # Check and delete the associated records
        self.nvim_addr_vs_websocket[self.neovim_address].remove(self)
        if len(self.nvim_addr_vs_websocket[self.neovim_address]) == 0:
            self.nvim_addr_vs_websocket.pop(self.neovim_address)

    def _start_neovim_listener(self):
        # We need to use threading because a daemonized process cannot have a child
        threading.Thread(target=self._neovim_listener, daemon=True).start()

    def _neovim_listener(self):
        self.loop_neovim_handle = pynvim.attach("socket", path=self.neovim_address)
        self.loop_neovim_handle.subscribe("nvim_buf_lines_event")
        self.loop_neovim_handle.subscribe("nvim_buf_detach_event")
        self.loop_neovim_handle.subscribe("nvim_ghost_exit_event")  # neovim is exiting
        self.loop_neovim_handle.api.buf_attach(self.buffer_handle, False, {})
        self.loop_neovim_handle.run_loop(None, self._neovim_handler)

    def _neovim_handler(self, *args):
        logv(f"nvim_event  handle={self.handle_neovim_notifications}  {args}")
        if not self.handle_neovim_notifications:
            # Resume handling notifications, because this notification has been
            # triggered by the buffer changes we have done above.
            self.handle_neovim_notifications = True
            # Because this notification was caused by our changes, we are not
            # interested in handling it. It is of zero significance to us.
            return

        # Fetch the event name
        event = args[0]

        if event in ("nvim_buf_detach_event", "nvim_ghost_exit_event"):
            # Buffer has been closed by user. Close the connection.
            self._do_close()

        if event == "nvim_buf_lines_event":
            # Buffer text has been changed by user.
            # Get the buffer contents
            handle = self.loop_neovim_handle
            buffer_contents = handle.api.buf_get_lines(self.buffer_handle, 0, -1, False)
            _, lnum, col, _, _ = handle.call("getcurpos")
            lnum -= 1  # indexing mismatch (nvim starts from 1, python starts from 0)
            col -= 1  # indexing mismatch (nvim starts from 1  python starts from 0)

            # Calculate curpos
            curpos = 0
            for line in buffer_contents[:lnum]:
                curpos += len(line) + 1
            curpos += col

            # Turn buffer_contents (a List) to a string
            text = "\n".join(buffer_contents)

            # Check if this is the same text we just set!
            if self.last_set_text is not None:
                if text == self.last_set_text:
                    # We are trying to send the text that we just set! Stop!
                    return
                # Text has been changed by user.
                # last_set_text is now outdated and invalid.
                self.last_set_text = None

            # Send the text
            message = {"text": text, "selections": [{"start": curpos, "end": curpos}]}
            message = json.dumps(message)
            self.send_message(message)
            logv(f"To {self.address[1]} sent", message)

    def _trigger_autocmds(self, url: str):
        self.neovim_handle.command(f"doau nvim_ghost_user_autocommands User {url}")

    def _do_close(self):
        log(
            "Closing websocket",
            ":".join([str(_) for _ in self.address]),
        )
        self.close()
        log(
            "Websocket",
            ":".join([str(_) for _ in self.address]),
            "closed by us",
        )

    def __init__(self, *args, **kwargs):
        self.nvim_addr_vs_websocket: Dict[str, List[GhostWebSocket]] = {}
        super().__init__(*args, **kwargs)


class GhostWebSocketServer(WebSocketServer):
    # This is nessecary because the imported WebSocketServer does not store
    # it's port number.   Yes, I have seen the source code. It doesn't.
    def __init__(self, host, port, websocketclass, **kwargs):
        self.port = port
        super().__init__(host, port, websocketclass, **kwargs)


class Server:
    def __init__(self):
        self.http_server = self._http_server()
        self.websocket_server = self._websocket_server()
        self.http_server_thread = threading.Thread(
            target=self._http_server_serve_forever,
            daemon=True,
        )
        self.websocket_server_thread = threading.Thread(
            target=self.websocket_server.serve_forever,
            daemon=True,
        )

    def _http_server(self):
        if not _port_occupied(GHOST_PORT):
            return GhostHTTPServer((LOCALHOST, GHOST_PORT), GhostHTTPRequestHandler)
        else:
            sys.exit("Port Occupied")

    def _http_server_serve_forever(self):
        self.http_server.running = True
        while self.http_server.running:
            self.http_server.handle_request()

    def _websocket_server(self):
        while True:
            random_port = random.randint(9000, 65535)
            if not _port_occupied(random_port):
                return GhostWebSocketServer(LOCALHOST, random_port, GhostWebSocket)


argparser = ArgParser()
argparser.parse_args()

# Start servers
exit_if_server_already_running()
servers = Server()
if LOGGING_ENABLED:
    sys.stdout = open("stdout.log", "w", buffering=1)
    sys.stderr = open("stderr.log", "w", buffering=1)
    print(time.strftime("%A, %d %B %Y, %H:%M:%S"))
    print(f"$NVIM_LISTEN_ADDRESS: {FOCUSED_NVIM_ADDRESS}")
    print(f"binary {BUILD_VERSION}")
servers.http_server_thread.start()
servers.websocket_server_thread.start()
print("Servers started")
if FOCUSED_NVIM_ADDRESS is not None:
    with pynvim.attach("socket", path=FOCUSED_NVIM_ADDRESS) as nvim_handle:
        if not SUPER_QUIET:
            nvim_handle.command("echom '[nvim-ghost] Servers started'")


def _signal_handler(_signal, _):
    _signal_name = signal.Signals(_signal).name
    log(f"Caught: {_signal_name}")
    if _signal in (signal.SIGINT, signal.SIGTERM):
        print("Exiting...")
        sys.exit()


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# wait for HTTPServer thread to exit
servers.http_server_thread.join()

# vim: et ts=4 sw=4 sts=4

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
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from typing import Dict
from typing import List
from typing import Optional

import pynvim
import requests
from simple_websocket_server import WebSocket
from simple_websocket_server import WebSocketServer

BUILD_VERSION: str = "v0.1.4"

# TEMP_FILEPATH is used to store the port of the currently running server
TEMP_FILEPATH: str = os.path.join(tempfile.gettempdir(), "nvim-ghost.nvim.port")
WINDOWS: bool = os.name == "nt"
LOCALHOST: str = "127.0.0.1" if WINDOWS else "localhost"
LOGGING_ENABLED: bool = bool(os.environ.get("NVIM_GHOST_LOGGING_ENABLED", False))
SUPER_QUIET: bool = bool(os.environ.get("NVIM_GHOST_SUPER_QUIET", False))

neovim_focused_address: Optional[str] = os.environ.get("NVIM_LISTEN_ADDRESS", None)
_ghost_port: str = os.environ.get("GHOSTTEXT_SERVER_PORT", "4001")


if not _ghost_port.isdigit():
    if neovim_focused_address is not None:
        with pynvim.attach("socket", path=neovim_focused_address) as nvim_handle:
            if not SUPER_QUIET:
                nvim_handle.command(
                    "echom '[nvim-ghost] Invalid port. "
                    "Please set $GHOSTTEXT_SERVER_PORT to a valid port.'"
                )
    sys.exit("Port must be a number")
GHOST_PORT: int = int(_ghost_port)


# chdir to folder containing binary
# otherwise the logs are generated whereever the server was started from (i.e curdir)
# which..... isn't good. You'd have stdout.log and stderr.log files everywhere!
os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
# we use sys.argv[0] because __file__ doesn't give proper results with pyinstaller
# See: https://stackoverflow.com/a/53511380


def get_neovim_handle() -> pynvim.Nvim:
    return pynvim.attach("socket", path=neovim_focused_address)


def _port_occupied(port) -> bool:
    """
    If port is occupied, returns True. Else returns False

    :param port int: port number to check
    """
    port = int(port)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_checker:
        return socket_checker.connect_ex((LOCALHOST, port)) == 0


def _detect_running_port() -> Optional[int]:
    """
    Checks whether the server is already running. If yes, returns the port it
    is running on.

    :rtype Optional[int]: Port number of server (if running), else None
    """
    if os.path.exists(TEMP_FILEPATH):
        with open(TEMP_FILEPATH) as file:
            old_port = file.read()
        try:
            response = requests.get(f"http://{LOCALHOST}:{old_port}/is_ghost_binary")
            if response.ok and response.text == "True":
                return int(old_port)
        except requests.exceptions.ConnectionError:
            return


def _get_running_version(port) -> Optional[str]:
    """
    Fetch the version of the currently running server

    :param port int: The port number the server is running on
    :rtype Optional[str]: Version of the running server
    """
    response = requests.get(f"http://{LOCALHOST}:{port}/version")
    if response.ok:
        return response.text


def store_port():
    """
    Store the port number of Server in TEMP_FILEPATH

    """
    with open(TEMP_FILEPATH, "w+") as file:
        file.write(str(servers.http_server.server_port))


def exit_if_server_already_running():
    running_port = _detect_running_port()
    if running_port is not None:
        if running_port == GHOST_PORT:
            if _get_running_version(running_port) == BUILD_VERSION:
                print("Server already running")
                if neovim_focused_address is not None:
                    with get_neovim_handle() as handle:
                        if not SUPER_QUIET:
                            handle.command("echom '[nvim-ghost] Server running'")
                sys.exit()
        # Server is outdated. Stop it.
        requests.get(f"http://{LOCALHOST}:{running_port}/exit")
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

        if neovim_focused_address is None:
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
        # Log
        print(time.strftime("[%H:%M:%S]:"), f"{self.address[1]} got", self.data)

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
        self.neovim_address = neovim_focused_address
        self.neovim_handle = get_neovim_handle()
        self.buffer_handle = self.neovim_handle.api.create_buf(False, True)
        self.neovim_handle.api.buf_set_option(self.buffer_handle, "bufhidden", "wipe")
        self.neovim_handle.command(f"tabe | {self.buffer_handle.number}buffer")
        self.handle_neovim_notifications = True
        self._start_neovim_listener()

        # Log
        print(
            time.strftime("[%H:%M:%S]:"),
            "Connected",
            ":".join([str(_) for _ in self.address]),
            "to",
            self.neovim_address,
        )

        # Add it to the records
        global WEBSOCKET_PER_NEOVIM_ADDRESS
        if not WEBSOCKET_PER_NEOVIM_ADDRESS.__contains__(self.neovim_address):
            WEBSOCKET_PER_NEOVIM_ADDRESS[self.neovim_address] = []
        WEBSOCKET_PER_NEOVIM_ADDRESS[self.neovim_address].append(self)

        # Since it's a new connection, we haven't handled the first message yet
        self.handled_first_message = False

    # Connection closed
    def handle_close(self):
        # Log
        print(
            time.strftime("[%H:%M:%S]:"),
            ":".join([str(_) for _ in self.address]),
            "websocket closed",
        )

        # Delete buffer and stop event loop
        self.neovim_handle.command(f"bdelete {self.buffer_handle.number}")
        self.neovim_handle.close()
        self.loop_neovim_handle.stop_loop()
        self.loop_neovim_handle.close()

        # Check and delete the associated records
        global WEBSOCKET_PER_NEOVIM_ADDRESS
        WEBSOCKET_PER_NEOVIM_ADDRESS[self.neovim_address].remove(self)
        if len(WEBSOCKET_PER_NEOVIM_ADDRESS[self.neovim_address]) == 0:
            WEBSOCKET_PER_NEOVIM_ADDRESS.__delitem__(self.neovim_address)

    def _start_neovim_listener(self):
        threading.Thread(target=self._neovim_listener, daemon=True).start()

    def _neovim_listener(self):
        self.loop_neovim_handle = get_neovim_handle()
        self.loop_neovim_handle.subscribe("nvim_buf_lines_event")
        self.loop_neovim_handle.subscribe("nvim_buf_detach_event")
        self.loop_neovim_handle.api.buf_attach(self.buffer_handle, False, {})
        self.loop_neovim_handle.run_loop(None, self._neovim_handler)

    def _neovim_handler(self, *args):
        if not self.handle_neovim_notifications:
            # Resume handling notifications, because this notification has been
            # triggered by the buffer changes we have done above.
            self.handle_neovim_notifications = True
            # Because this notification was caused by our changes, we are not
            # interested in handling it. It is of zero significance to us.
            return

        # Fetch the event name
        event = args[0]

        if event == "nvim_buf_detach_event":
            # Buffer has been closed by user. Close the connection.
            self.close()

        if event == "nvim_buf_lines_event":
            # Buffer text has been changed by user.
            # Get the buffer contents
            handle = self.loop_neovim_handle
            buffer_contents = handle.api.buf_get_lines(self.buffer_handle, 0, -1, False)

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
            self._send_text(text)

    def _send_text(self, text: str):
        # NOTE: Just satisfying the protocol for now.
        # I still don't know how to extract 'selections' from neovim
        # Heck, I don't even know what this thing is supposed to do!
        selections: List[Dict[str:int]] = []
        selections.append({"start": 0, "end": 0})

        # Construct and send the message
        message = json.dumps({"text": text, "selections": selections})
        self.send_message(message)

        # Log
        print(time.strftime("[%H:%M:%S]:"), f"{self.address[1]} sent", message)

    def _trigger_autocmds(self, url: str):
        self.neovim_handle.command(f"doau nvim_ghost_user_autocommands User {url}")


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
        # Do not daemonize one of the threads. It will keep the binary running
        # after the main thread has finished executing everything.
        self.http_server_thread = threading.Thread(
            target=self._http_server_serve_forever
        )
        self.websocket_server_thread = threading.Thread(
            target=self.websocket_server.serve_forever,
            daemon=True,
        )

    def _http_server(self):
        if not _port_occupied(GHOST_PORT):
            return HTTPServer((LOCALHOST, GHOST_PORT), GhostHTTPRequestHandler)
        else:
            sys.exit("Port Occupied")

    def _http_server_serve_forever(self):
        while True:
            self.http_server.handle_request()

    def _websocket_server(self):
        while True:
            random_port = random.randint(9000, 65535)
            if not _port_occupied(random_port):
                return GhostWebSocketServer(LOCALHOST, random_port, GhostWebSocket)


WEBSOCKET_PER_NEOVIM_ADDRESS: Dict[str, List[GhostWebSocket]] = {}

argparser = ArgParser()
argparser.parse_args()

# Start servers
exit_if_server_already_running()
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
    with pynvim.attach("socket", path=neovim_focused_address) as nvim_handle:
        if not SUPER_QUIET:
            nvim_handle.command("echom '[nvim-ghost] Servers started'")
store_port()


def stop_servers():
    os.remove(TEMP_FILEPATH)  # Remove port
    print("Exiting...")
    sys.exit()


def _signal_handler(_signal, _):
    _signal_name = signal.Signals(_signal).name
    print(time.strftime("[%H:%M:%S]:"), f"Caught: {_signal_name}")
    if _signal in (signal.SIGINT, signal.SIGTERM):
        stop_servers()


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# vim: et ts=4 sw=4 sts=4

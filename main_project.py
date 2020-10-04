import http.server
import time
import random
import socket
import os
import sys
import multiprocessing
from simple_websocket_server import WebSocketServer, WebSocket
import pynvim

# Working variables
ghost_is_running = False
ghost_websocket_connection_stack = []
ghost_GET_server = None
ghost_GET_server_process = None
ghost_websocket_server = None
ghost_websocket_server_process = None

# Config taken from environment variables
ghost_port = os.environ.get("GHOSTTEXT_SERVER_PORT") or 4001
nvim_socket = os.environ.get("NVIM_LISTEN_ADDRESS")


class GhostGETRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global ghost_websocket_server
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            f"""{{  "ProtocolVersion": 1,
  "WebSocketPort": {ghost_websocket_server.port}
}}"""
        )


class GhostWebSocket(WebSocket):
    def handle(self):
        # What to do with received message
        # Probably send it to the Handler class (yet to be created)
        pass

    def connected(self):
        global ghost_websocket_connection_stack
        for _ in range(len(ghost_websocket_connection_stack)):
            ghost_websocket_connection_stack.pop().close()
        ghost_websocket_connection_stack.append(self)

    def handle_close(self):
        global ghost_websocket_connection_stack
        ghost_websocket_connection_stack.pop(
            ghost_websocket_connection_stack.index(self)
        )


class GhostWebSocketServer(WebSocketServer):
    def __init__(self, *args, **kwargs):
        self.port = args[1]
        super().__init__(*args, **kwargs)


class MainClass:
    """Class of the main functions

    Just a class of all the miscellaneous functions used in main().
    This class is never expected to be objectified.

    Functions to be called like: MainClass.function()
    """

    def create_ghost_GET_server(*args):
        global ghost_GET_server
        global ghost_port
        ghost_GET_server = http.server.ThreadingHTTPServer(
            ("localhost", ghost_port), GhostGETRequestHandler
        )

    def create_ghost_websocket_server(*args):
        def port_occupied(port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_checker:
                return socket_checker.connect_ex(("localhost", port)) == 0

        global ghost_websocket_server
        while True:
            random_port = random.randint(9000, 65535)
            if not port_occupied(random_port):
                ghost_websocket_server = GhostWebSocketServer(
                    "localhost", random_port, GhostWebSocket
                )

    def start_ghost_GET_server(*args):
        global ghost_GET_server
        global ghost_GET_server_process
        ghost_GET_server_process = multiprocessing.Process(
            target=ghost_GET_server.serve_forever(), daemon=True
        )
        ghost_GET_server_process.start()

    def stop_ghost_GET_server(*args):
        global ghost_GET_server
        global ghost_GET_server_process
        terminator_process = multiprocessing.Process(
            target=ghost_GET_server.shutdown()
        ).start()
        time.sleep(0.5)
        ghost_GET_server_process.terminate()
        ghost_GET_server_process.close()
        terminator_process.terminate()
        terminator_process.close()

    def start_ghost_websocket_server(*args):
        global ghost_websocket_server
        global ghost_websocket_server_process
        ghost_websocket_server_process = multiprocessing.Process(
            target=ghost_websocket_server.serve_forever(), daemon=True
        )
        ghost_websocket_server_process.start()

    def stop_ghost_websocket_server(*args):
        global ghost_websocket_server
        global ghost_websocket_server_process
        ghost_websocket_server_process.terminate()
        ghost_websocket_server_process.close()


def stdin_interpreter(stdin):
    pass


def stdin_loop():
    global ghost_is_running
    while ghost_is_running:
        stdin = input()
        stdin_interpreter(stdin)


def main():
    global ghost_is_running
    MainClass.create_ghost_GET_server()
    MainClass.create_ghost_websocket_server()
    MainClass.start_ghost_GET_server()
    MainClass.start_ghost_websocket_server()
    ghost_is_running = True
    stdin_loop()
    MainClass.stop_ghost_GET_server()
    MainClass.start_ghost_websocket_server()
    ghost_is_running = False


if __name__ == "__main__":
    if nvim_socket is not None:
        main()
    else:
        print("This script must be executed from a neovim instance")
        sys.exit(1)

# Echo Server Example

from simple_websocket_server import WebSocketServer, WebSocket
import time
import multiprocessing

ghost_websocket_connection_stack = []


class SimpleEcho(WebSocket):
    def __init__(self, *args, **kwargs):
        self.handled_once = False
        super().__init__(*args, **kwargs)

    def handle(self):
        print(self.data)
        if len(self.data) != 0:
            self.handled_once = True

    def connected(self):
        global ghost_websocket_connection_stack
        print(ghost_websocket_connection_stack)
        print(self.address, "connected")
        ghost_websocket_connection_stack.append(self)
        print(ghost_websocket_connection_stack)
        multiprocessing.Process(target=start_timer, args=(self)).start()

    def handle_close(self):
        global ghost_websocket_connection_stack
        print(ghost_websocket_connection_stack)
        print(self.address, "closed")
        ghost_websocket_connection_stack.pop(
            ghost_websocket_connection_stack.index(self)
        )
        # for _ in range(len(ghost_websocket_connection_stack)):
        #     ghost_websocket_connection_stack.pop().close()
        #     print(ghost_websocket_connection_stack)
        # ghost_websocket_connection_stack.pop(
        #     ghost_websocket_connection_stack.index(self)
        # )
        print(ghost_websocket_connection_stack)


def start_timer(self):
    while time.sleep(5) or True:
        if not self.handled_once:
            self.close()


server = WebSocketServer("", 60000, SimpleEcho)
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.close()

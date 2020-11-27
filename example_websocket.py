# Echo Server Example

from simple_websocket_server import WebSocketServer, WebSocket

ghost_websocket_connection_stack = []


class SimpleEcho(WebSocket):
    def handle(self):
        print(self.data)

    def connected(self):
        global ghost_websocket_connection_stack
        print(ghost_websocket_connection_stack)
        print(self.address, "connected")
        ghost_websocket_connection_stack.append(self)
        print(ghost_websocket_connection_stack)

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


class GhostWebSocketServer(WebSocketServer):
    def __init__(self, host, port, websocketclass, **kwargs):
        self.port = port
        return super().__init__(host, port, websocketclass, **kwargs)


server = GhostWebSocketServer("", 60000, SimpleEcho)
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.close()

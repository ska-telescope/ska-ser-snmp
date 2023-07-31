import socketserver
from collections.abc import Callable
from socketserver import BaseRequestHandler
from typing import Iterator, Optional
from ska_ser_devices.client_server.tcp import _TcpBytestringIterator


class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        while True:
            data = self.request.recv(1024)
            print(f"DATA FROM HANDLER: {data}")
            if not data:
                break
            response = self.server.application_callback(data)
            self.request.sendall(response)


class ProXRServer(socketserver.TCPServer):
    def __init__(
        self,
        application_callback: Callable[[Iterator[bytes]], Optional[bytes]],
        server_address: tuple[str, int],
        bind_and_activate: bool = True,
    ) -> None:
        self.application_callback = application_callback
        super().__init__(server_address, TCPHandler, bind_and_activate)

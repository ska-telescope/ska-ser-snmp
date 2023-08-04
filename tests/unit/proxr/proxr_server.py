import socketserver
from collections.abc import Callable
from typing import Optional


class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        """Handle multiple client requests."""
        while True:
            data = self.request.recv(1024)
            if not data:
                break
            response = self.server.application_callback(  # type:ignore[attr-defined]
                data
            )
            self.request.sendall(response)


class ProXRServer(socketserver.TCPServer):
    def __init__(
        self,
        application_callback: Callable[[bytes], Optional[bytes]],
        server_address: tuple[str, int],
    ) -> None:
        """
        Initialise the server.

        :param application_callback: backend callback.
        :param server_address: host and port values.

        """
        self.application_callback = application_callback
        super().__init__(server_address, TCPHandler)

import socket
from contextlib import contextmanager
from enum import IntEnum
from typing import Any, Generator


class ProXRClient:
    """Client for sending/receiving ProXR byte payloads to from a server."""

    class _CommandStartingHex(IntEnum):
        """
        Mapping to help obtain the hex value of commands.

        The commands on the ProXR relay board are associated with specific
        hex values. These hex values determine the nature of the request (read,
        turn on/off) and the corresponding relay it relates to.

        As there are 8 relay banks, we can partition ranges of hex
        values for types of request. For example, the StartingHex.READ is mapped
        to 0x73 and is associated with R1.

        """

        READ = 0x73
        ON = 0x6B
        OFF = 0x63

    def __init__(self, host: str, port: int):
        """
        Initialise a ProXRClient.

        :param host: the host address.
        :param port: the port number.
        """
        self._host = host
        self._port = port

    @contextmanager
    def socket_context(
        self, *args: Any, **kw: Any
    ) -> Generator[socket.socket, None, None]:
        """
        Socket context manager to communicate with the component.

        :yield: The socket used for communicating with the component.
        """
        sock = socket.socket(*args, **kw)
        sock.connect((self._host, self._port))
        try:
            yield sock
        finally:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()

    def marshall(self, bytes_request: list[int]) -> bytes:
        """
        Marshall the payload by adding the header and checksum bytes.

        :param bytes_request: the request portion of the payload in bytes.
        :return: the full payload with header and checksum types.
        """
        header = [0xAA, len(bytes_request)]
        checksum = sum(header + bytes_request) & 255

        return bytes(header + bytes_request + [checksum])

    def bytes_request(
        self, write_command: bool | None, relay_attribute: str, bank: int = 1
    ) -> bytes:
        """
        Return the payload for an input command.
        """
        relay_number = int(relay_attribute.replace("R", ""))

        if write_command is not None:
            hex_value = (
                self._CommandStartingHex.ON
                if write_command is True
                else self._CommandStartingHex.OFF
            )
        else:
            hex_value = self._CommandStartingHex.READ

        bytes_request = [0xFE, hex_value + relay_number, bank]
        return self.marshall(bytes_request)

    def send_request(
        self,
        sock: socket.socket,
        request: bytes,
        buffer_size: int = 1024,
    ) -> bytes:
        """
        Send the bytes to the component through a socket.

        :param sock: a socket for communicating with the component.
        :param request: the request bytes payload.
        :param buffer_size: defaults to 1024.
        :return: response from the component.
        """

        sock.sendall(request)
        return sock.recv(buffer_size)

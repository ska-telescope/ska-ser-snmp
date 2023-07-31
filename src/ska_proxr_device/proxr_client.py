import re
import socket
from contextlib import contextmanager
from enum import IntEnum
from typing import Any, Generator


class ProXRClient:
    class _CommandStartingHex(IntEnum):
        """
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

    def __init__(self, host, port):
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
        A socket context manager for sending/receiving data packets to/from the component.

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
        Marshall the payload by prepending the header bytes and appending checksum byte to
        the bytes_request.

        :return: the marshalled payload to be sent to the component.
        """
        header = [0xAA, len(bytes_request)]
        checksum = sum(header + bytes_request) & 255

        return bytes(header + bytes_request + [checksum])

    def unmarshall(self, bytes_response: bytes) -> bytes:
        """
        Validate the format of the received data packet from component.

        :param data_packet: received data packet
        :raises ValueError: invalid format
        :return: None
        """

        # Validate the format of the response bytes
        header = bytes_response[0] == 0xAA
        bytes_length = bytes_response[1] == len(bytes_response) - 3
        checksum = bytes_response[-1] == sum(bytes_response[:-1]) & 255

        if header and bytes_length and checksum:
            return bytes_response[len(bytes_response) - 2]
        else:
            raise ValueError("Invalid return bytes packet")

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
        sock,
        request: bytes,
        max_send_attempts: int = 3,
        buffer_size: int = 1024,
    ) -> bytes:
        """
        Send the bytes to the component through a socket.

        :param request: the request payload in bytes.
        :param max_send_attempts: the maximum number of times the component manager
            will attempt to connect to the component through the socket, defaults to 3.
        :return: the response payload from the component in bytes.
        """

        sock.sendall(request)
        return sock.recv(buffer_size)
        # attempts = 0
        # while attempts < max_send_attempts:
        #     try:
        #         with self.socket_context(socket.AF_INET, socket.SOCK_STREAM) as sock:
        #             sock.sendall(request)
        #             response = sock.recv(buffer_size)
        #             break
        #     except:
        #         attempts += 1
        # return self.unmarshall(response)

import logging
import socket
from enum import IntEnum

from ska_ser_devices.client_server import ApplicationServer

from ska_proxr_device.proxr_server import ProXRServer


class ProXRSimulator(ApplicationServer[bytes, bytes]):
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

    def __init__(
        self,
        host: str = socket.gethostname(),
        port: int = 5025,
        logger: logging.Logger = logging.getLogger(),
        number_of_relays: int = 8,
    ):
        """
        Initialise a ProXR simulator.

        :param host: the host address, defaults to socket.gethostname()
        :param port: the port number, defaults to 5025
        :param logger: a logger for debugging purposes, defaults to logging.getLogger()
        :param number_of_relays: the number of relays on the relay board, defaults to 8
        """
        self._attributes: dict[str, bool] = {}

        self._host = host
        self._port = port
        self._logger = logger

        # Set up relay attributes
        for i in range(1, number_of_relays + 1):
            relay = "R" + str(i)
            self._attributes[relay] = False

        super().__init__(
            self.unmarshall,  # type:ignore[arg-type]
            self.marshall,
            self.receive_send,
        )

    def unmarshall(self, payload: bytes) -> bytes:
        """
        Unmarshall the incoming payload.

        :param bytes_iterator: an iterator of bytestrings received by the
            by the server
        :return: the request packet in bytes
        """

        starting_idx = payload.index(0xAA)
        length_of_packet = int(payload[starting_idx + 1])

        request_idx = payload.index(0xFE)
        # Add three to include the header, length of packet and checksum bytes
        request = payload[request_idx : request_idx + length_of_packet]

        return request

    def marshall(self, response: bytes) -> bytes:
        """
        Prepend the header bytes and prepend the checksum byte.

        :param response_byte: a response byte to be sent back to the client.
        :return: full response bytes packet to be sent back to the client.
        """
        header = [0xAA, 0x01]

        checksum = sum(header + list(response)) & 255
        return bytes(header + list(response) + [checksum])

    def receive_send(self, request: bytes) -> bytes:
        """
        Update the simulator based on the unmarshalled request.

        :param request: the request packet in bytes.
        :raises ValueError: invalid command.
        :return: the response byte to be sent back to the client.
        """

        relay, command = self.decode_command(request)
        relay_attribute_name = f"R{relay}"
        print(f"REQUEST ON RELAY: {relay_attribute_name}, {command}")

        if command == ("READ"):
            status = self._attributes[relay_attribute_name]
            response = [int(status)]
        elif command == ("ON"):
            self._attributes[relay_attribute_name] = True
            response = [0x55]
        elif command == ("OFF"):
            self._attributes[relay_attribute_name] = False
            response = [0x55]
        else:
            raise ValueError

        return self.marshall(bytes(response))

    def decode_command(self, request_bytes: bytes) -> tuple[int, str]:
        """
        Decode the request bytes to obtain the command (READ, ON, OFF) and relay.

        :param request_bytes: full request packet in bytes.
        :return: tuple containing the relay attribute and command to be executed.
        """
        print(f"THE REQUEST BYTES: {list(request_bytes)}")
        cmd_idx = request_bytes.index(0xFE) + 1
        cmd_code = request_bytes[cmd_idx]

        # Loop through to find the command associated with the command code.
        for enum in self._CommandStartingHex:
            starting_hex_value = enum.value
            if cmd_code > starting_hex_value:
                relay = cmd_code - starting_hex_value
                command = enum.name
                break
        return (relay, command)


def main() -> None:
    """Run socketserver."""
    proxr_simulator = ProXRSimulator()
    server = ProXRServer(proxr_simulator.receive_send, ("localhost", 5025))
    with server:
        server.serve_forever()


if __name__ == "__main__":
    main()

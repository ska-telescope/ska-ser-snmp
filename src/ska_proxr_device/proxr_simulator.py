import logging
import socket
import threading
from enum import IntEnum
from typing import Iterator

from ska_ser_devices.client_server import (
    ApplicationServer,
    SentinelBytesMarshaller,
    TcpServer,
)

from ska_proxr_device.proxr_component_manager import (
    ProXRAttrInfo,
    ProXRComponentManager,
)


class ProXRSimulator(ApplicationServer[bytes, bytes]):
    class _CommandStartingHex(IntEnum):
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
        Initialise the simulator with the number of relays.

        :param number_of_relays: number of relays on the relay board
        """
        self._lock = threading.Lock()
        self._attributes: dict[str, bool] = {}

        self._host = host
        self._port = port
        self._logger = logger
        self._received_count = 0

        for i in range(1, number_of_relays + 1):
            relay = "R" + str(i)
            self._attributes[relay] = False

        super().__init__(
            self.unmarshall,
            self.marshall,
            self.receive_send,
        )

    def unmarshall(self, bytes_iterator: Iterator[bytes]) -> bytes:
        payload = b""
        more_bytes = next(bytes_iterator)
        payload = payload + more_bytes

        self._received_count += 1
        print(
            f"THE AMOUNT OF A TIMES A PACKET HAS BEEN RECEIVED: {self._received_count}"
        )

        header = 0xAA
        # Look for header byte in the packet
        while bytes([header]) not in payload:
            self._logger.debug(
                f"Unmarshaller received payload bytes {repr(more_bytes)}, "
                f"has not yet encountered header byte {repr(header)}"
            )
            more_bytes = next(bytes_iterator)
            payload = payload + more_bytes
        else:
            starting_idx = payload.index(0xAA)
            length_of_packet = int(payload[starting_idx + 1])

            # Add three to include the header, length of packet and checksum bytes
            payload = payload[starting_idx : starting_idx + length_of_packet + 3]

        self._logger.debug(
            f"Unmarshaller received payload bytes {repr(more_bytes)}, "
            f"encountered header {repr(header)}, "
            f"returning {repr(payload)}"
        )
        return payload

    def marshall(self, request: bytes) -> bytes:
        return request

    def receive_send(self, request: bytes) -> bytes:
        """
        Receive, process and respond to a bytes packet sent from the controller.

        :return: bytes to be sent back to the controller
        """
        relay, command = self.decode_command(request)
        relay_attribute_name = "R" + str(relay)
        print(f"COMMAND: {command}, RELAY: {relay_attribute_name}")

        if command == ("READ"):
            status = self._attributes[relay_attribute_name]
            payload = int(status)
        elif command == ("ON"):
            self._attributes[relay_attribute_name] = True
            payload = 0x55
        elif command == ("OFF"):
            self._attributes[relay_attribute_name] = False
            payload = 0x55
        else:
            raise ValueError
        return self.prepare_payload([payload])

    def decode_command(self, request: bytes) -> tuple[int, str]:
        """
        Decode the bytes packet request.

        :param request: incoming bytes packet request.
        :return: tuple containing the corresponding relay and command.
        """
        data_packet = self.validate_format(list(request))
        command_code = data_packet[3]

        # Loop through to find the command associated with
        # the command code
        for enum in self._CommandStartingHex:
            starting_hex_value = enum.value
            if command_code > starting_hex_value:
                relay = command_code - starting_hex_value
                command = enum.name
                break
        return (relay, command)

    def prepare_payload(self, data_packet: list[int]) -> bytes:
        """
        Prepend the header bytes and prepend the checksum byte.

        :param data_packet: data packet containing command information
        :return: full data packet to be sent back.
        """
        header = [0xAA, len(data_packet)]
        data_packet = header + data_packet

        checksum = sum(data_packet) & 255
        payload = bytes(data_packet + [checksum])
        return payload

    def validate_format(self, data_packet: list[int]) -> list[int]:
        """
        .

        :param data_packet: _description_
        :raises ValueError: _description_
        :return: _description_
        """
        length_of_packet = len(data_packet)
        calculated_checksum = (
            sum(data_packet[:-1]) & 255
        )  # Exclude checksum in calculation

        header = data_packet[0] == 0xAA
        bytes_length = data_packet[1] == length_of_packet - 3
        checksum = data_packet[-1] == calculated_checksum
        if header and bytes_length and checksum:
            pass
        else:
            raise ValueError("Invalid return bytes packet")

        return data_packet


def main() -> None:
    proxr_simulator = ProXRSimulator()
    server = TcpServer("localhost", 5025, proxr_simulator)
    with server as s:
        print("oh we serving")
        s.serve_forever()


if __name__ == "__main__":
    # t = ProXRSimulator(number_of_relays=8)
    # incoming_on = bytes([0xAA, 0x03, 0xFE, 0x6C, 0x01, 0x18])
    # incoming_read = bytes([0xAA, 0x03, 0xFE, 118, 0x01, 0x22])
    # response = t.receive_send(incoming_read)
    # print(response)
    # print(t._attributes)
    main()

import logging
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Generator, Mapping, Sequence

from ska_tango_base.base import CommunicationStatusCallbackType
import tango

from ska_low_itf_devices.attribute_polling_component_manager import (
    AttributePollingComponentManager,
    AttrInfo,
    AttrPollRequest,
    AttrPollResponse,
)
from ska_proxr_device.proxr_device import ProXRDevice


@dataclass(frozen=True)
class ProXRAttrInfo(AttrInfo):
    pass


class ProXRComponentManager(AttributePollingComponentManager):
    _attributes: Mapping[str, ProXRAttrInfo]

    class _StartingHex(IntEnum):
        READ = 0x73
        ON = 0x6B
        OFF = 0x63

    def __init__(  # noqa: D107
        self,
        host: str,
        port: int,
        logger: logging.Logger,
        communication_state_callback: CommunicationStatusCallbackType,
        component_state_callback: Callable[..., None],
        attributes: Sequence[ProXRAttrInfo],
        poll_rate: float,
    ):
        # pylint: disable=too-many-arguments
        super().__init__(
            logger,
            communication_state_callback,
            component_state_callback,
            poll_rate=poll_rate,
            attributes=attributes,
        )

        self._host = host
        self._port = port

    @contextmanager
    def socket_context(
        self, *args: Any, **kw: Any
    ) -> Generator[socket.socket, None, None]:
        """
        Context manager for socket process when sending/receiving data.

        """
        sock = socket.socket(*args, **kw)
        sock.connect((self._host, self._port))
        sock.settimeout(0.5)
        try:
            yield sock
        finally:
            sock.close()

    def poll(self, poll_request: AttrPollRequest) -> AttrPollResponse:
        """
        Group by writes and reads, chunk, and run the appropriate SNMP command.

        Aggregate any returned ObjectTypes from GET commands as the poll response.
        """

        # with self.socket_context(socket.AF_INET, socket.SOCK_STREAM) as sock:
        state_updates: AttrPollResponse = {}

        for relay, command in poll_request.writes.items():
            relay_number = int(relay.replace("R", ""))
            command = self.get_command_by_bank(
                command=self._StartingHex.ON, relay=relay_number, bank=1
            )
            payload = bytes(self.prepare_payload(data_packet=command))
            self.send_command(
                # socket_context=sock,
                payload=payload,
            )

        # ... do some stuff with the poll_request.writes and poll_request.reads ...
        for relay in poll_request.reads:
            relay_number = int(relay.replace("R", ""))
            command = self.get_command_by_bank(
                command=self._StartingHex.READ, relay=relay_number, bank=1
            )
            payload = bytes(self.prepare_payload(data_packet=command))
            read_response = self.process_read_status(
                self.send_command(
                    # socket_context=sock,
                    payload=payload,
                )
            )
            state_updates[relay] = read_response

        return state_updates

    def prepare_payload(self, data_packet: list[int]) -> bytes:
        """
        Prepend header bytes and append checksum.

        """
        header = [0xAA, len(data_packet)]
        data_packet = header + data_packet

        checksum = sum(data_packet) & 255
        print(data_packet + [checksum])
        payload = bytes(data_packet + [checksum])
        return payload

    def get_command_by_bank(
        self, command: _StartingHex, relay: int, bank: int = 1
    ) -> bytes:
        """
        Return the payload for an input command.
        """
        return self.prepare_payload([0xFE, relay + command, bank])

    def send_command(
        self,
        # socket_context: socket.socket,
        payload: bytes,
        expected_return_bytes: int = 4,
    ) -> bytes:
        """
        Use the context manager to open a socket and send byte packets to the component.

        :param socket: socket object for communication
        :param payload: bytes packet containing the command
        :param expected_return_bytes: expected return bytes, defaults to 4
        :return: response packet from the packet
        """
        with self.socket_context(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.send(payload)
            return sock.recv(expected_return_bytes)

    def process_read_status(self, bytes_back: bytes) -> bool:
        """
        Process the bytes packet that is received from the component.

        :param bytes_back: bytes packet from component
        :return: relay state as boolean type
        """
        # The status of the relay is located after the the header
        # 0xAA and byte length 0x01.
        data_packet = list(bytes_back)
        self.validate_format(data_packet)

        # Status is the second to last item, just before the
        # checksum
        return bool(data_packet[-2])

    def validate_format(self, data_packet: list[int]) -> None:
        """
        Validate the format of the received data packet from component.

        :param data_packet: received data packet
        :raises ValueError: invalid format
        :return: None
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


def main():
    


if __name__ == "__main__":
    main()

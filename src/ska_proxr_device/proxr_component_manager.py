import logging
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Generator, Mapping, Sequence
from ska_ser_devices.client_server import ApplicationClient, TcpClient
from ska_tango_base.base import CommunicationStatusCallbackType

from ska_low_itf_devices.attribute_polling_component_manager import (
    AttributePollingComponentManager,
    AttrInfo,
    AttrPollRequest,
    AttrPollResponse,
)

from ska_proxr_device.utils import get_payload_by_command, process_read_status


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
        self._poll_count = 0

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

    def send_command(
        self,
        sock,
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
        print(f"Sending the following payload through the socket: {payload}")
        sock.sendall(payload)
        response = sock.recv(expected_return_bytes)
        return response

    def poll(self, poll_request: AttrPollRequest) -> AttrPollResponse:
        """
        Group by writes and reads, chunk, and run the appropriate SNMP command.

        Aggregate any returned ObjectTypes from GET commands as the poll response.
        """

        state_updates: AttrPollResponse = {}

        with self.socket_context(socket.AF_INET, socket.SOCK_STREAM) as sock:
            for relay, command in poll_request.writes.items():
                relay_number = int(relay.replace("R", ""))
                command = (
                    self._StartingHex.ON if command is True else self._StartingHex.OFF
                )
                payload = get_payload_by_command(
                    command=command, relay=relay_number, bank=1
                )
                self.logger.info(
                    f"The following write payload is being sent to the component: {list(payload)}"
                )
                write_response = self.send_command(
                    sock,
                    payload=payload,
                )
                self.logger.info(
                    f"The component sent the following response: {list(write_response)}"
                )
                # ... do some stuff with the poll_request.writes and poll_request.reads ...
            for relay in poll_request.reads:
                self._poll_count += 1
                print(f"THE POLL COUNT IS: {self._poll_count}")
                relay_number = int(relay.replace("R", ""))
                payload = get_payload_by_command(
                    command=self._StartingHex.READ, relay=relay_number, bank=1
                )
                self.logger.info(
                    f"The following read payload is being sent to the component: {list(payload)}"
                )
                read_response = process_read_status(
                    self.send_command(
                        sock,
                        payload=payload,
                    )
                )
                self.logger.info(
                    f"The component sent the following response: {read_response}"
                )
                state_updates[relay] = read_response

        return state_updates

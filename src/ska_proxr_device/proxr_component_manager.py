import logging
import socket
from typing import Callable, Sequence

from ska_tango_base.base import CommunicationStatusCallbackType

from ska_low_itf_devices.attribute_polling_component_manager import (
    AttributePollingComponentManager,
    AttrInfo,
    AttrPollRequest,
    AttrPollResponse,
)
from ska_proxr_device.proxr_client import ProXRClient


class ProXRComponentManager(AttributePollingComponentManager):
    def __init__(  # noqa: D107
        self,
        host: str,
        port: int,
        logger: logging.Logger,
        communication_state_callback: CommunicationStatusCallbackType,
        component_state_callback: Callable[..., None],
        attributes: Sequence[AttrInfo],
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
        self._proxr_client = ProXRClient(self._host, self._port)

    def poll(self, poll_request: AttrPollRequest) -> AttrPollResponse:
        """
        Execute the poll based on the poll request. These are split into reads and writes.

        :param poll_request: A list of reads and dictionary of writes to be sent to the component.
        :return: A dictionary with the results of the poll.
        """

        with self._proxr_client.socket_context(
            socket.AF_INET, socket.SOCK_STREAM
        ) as sock:
            # Write requests
            for relay, command in poll_request.writes.items():
                bytes_request = self._proxr_client.bytes_request(
                    write_command=command,
                    relay_attribute=relay,
                )
                self.logger.info(
                    f"The following write payload is being sent to the component: {list(bytes_request)}"
                )
                response = self._proxr_client.send_request(sock, request=bytes_request)
                self.logger.info(
                    f"The component sent the following response: {list(response)}"
                )

            # Read requests
            state_updates: AttrPollResponse = {}
            for relay in poll_request.reads:
                bytes_request = self._proxr_client.bytes_request(
                    write_command=None,
                    relay_attribute=relay,
                )
                self.logger.info(
                    f"The following read payload is being sent to the component: {list(bytes_request)}"
                )
                response = self._proxr_client.send_request(sock, request=bytes_request)
                self.logger.info(
                    f"The component sent the following response: {list(response)}"
                )
                status_byte = response[-2]
                state_updates[relay] = bool(status_byte)

        return state_updates

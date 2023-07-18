import logging
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from ska_tango_base.base import CommunicationStatusCallbackType

from ska_low_itf_devices.attribute_polling_component_manager import (
    AttributePollingComponentManager,
    AttrInfo,
    AttrPollRequest,
    AttrPollResponse,
)


@dataclass(frozen=True)
class ProXRAttrInfo(AttrInfo):
    pass


class ProXRComponentManager(AttributePollingComponentManager):
    _attributes: Mapping[str, ProXRAttrInfo]

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

    def poll(self, poll_request: AttrPollRequest) -> AttrPollResponse:
        """
        Group by writes and reads, chunk, and run the appropriate SNMP command.

        Aggregate any returned ObjectTypes from GET commands as the poll response.
        """
        state_updates: AttrPollResponse = {}

        # ... do some stuff with the poll_request.writes and poll_request.reads ...

        return state_updates

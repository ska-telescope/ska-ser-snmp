import logging
import time
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, Mapping, Sequence, cast

from more_itertools import iter_except
from ska_control_model import PowerState, TaskStatus
from ska_tango_base.base import CommunicationStatusCallbackType, TaskCallbackType
from ska_tango_base.poller import PollingComponentManager


@dataclass
class AttrPollRequest:
    writes: dict[str, Any]
    reads: list[str]


AttrPollResponse = dict[str, Any]


@dataclass(frozen=True)
class AttrInfo:
    """
    Base class for dynamic attribute metadata.

    :param attr_args: kwargs that will be passed to PyTango's
        tango.server.attribute() function.

    :param polling_period: the minimum time in seconds between
        successive hardware reads for this attribute.
    """

    # pylint: disable=missing-function-docstring
    attr_args: dict[str, Any]
    polling_period: float

    @cached_property
    def dtype(self) -> Any:  # noqa: D102
        return self.attr_args["dtype"]

    @cached_property
    def name(self) -> str:  # noqa: D102
        return cast(str, self.attr_args["name"])


class AttributePollingComponentManager(
    PollingComponentManager[AttrPollRequest, AttrPollResponse]
):
    def __init__(  # noqa: D107
        self,
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
            **{attr.name: None for attr in attributes},
        )

        # The same map, but mapping by Tango attribute name
        self._attributes: Mapping[str, AttrInfo] = {
            attr.name: attr for attr in attributes
        }

        # Writes accumulate here in between polls
        self._pending_writes: dict[str, Any] = {}

        # store the last time each attribute was successfully polled,
        # used to calculate when to poll again based on polling_period
        self._last_polled = {attr.name: float("-inf") for attr in attributes}

    def get_request(self) -> AttrPollRequest:
        """
        Assemble a list of ObjectTypes representing pending writes and reads.

        The writes appear first, and come from `self._pending_writes`. Reads
        are requested for each attribute whose last successful poll happened
        longer ago than its polling period, and each attribute being written.
        """
        # atomically drain the write queue
        writes = dict(iter_except(self._pending_writes.popitem, KeyError))

        now = time.time()
        reads = [
            attr_name
            for attr_name, attr in self._attributes.items()
            if now - self._last_polled[attr_name] >= attr.polling_period
            or attr_name in writes  # bonus poll after writing
        ]

        return AttrPollRequest(writes, reads)

    def poll(self, poll_request: AttrPollRequest) -> AttrPollResponse:
        """
        Group by writes and reads, chunk, and run the appropriate SNMP command.

        Aggregate any returned ObjectTypes from GET commands as the poll response.
        """
        raise NotImplementedError

    def poll_succeeded(self, poll_response: AttrPollResponse) -> None:
        """
        Notify the device of the return values of a successful poll.

        This involves type coercion from PySNMP- to PyTango-compatible types.
        """
        super().poll_succeeded(poll_response)

        now = time.time()
        self._last_polled.update((k, now) for k in poll_response)

        self._update_component_state(power=PowerState.ON, **poll_response)

    def enqueue_write(self, attr_name: str, val: Any) -> None:
        """
        Queue an attribute value to be written on the next poll.

        If there is already a write pending for the attribute, it will be superseded.
        """
        converted_value = self.from_python(attr_name, val)
        self._pending_writes[attr_name] = converted_value

    def from_python(self, attr_name: str, val: Any) -> Any:
        """
        Convert from raw Python type to a hardware-compatible type.

        This is called in enqueue_write() so that any conversion error happens
        early, when an attribute is set, rather than in the polling thread.
        """
        # pylint: disable=unused-argument
        return val

    def off(  # noqa: D102
        self, task_callback: TaskCallbackType | None = None
    ) -> tuple[TaskStatus, str]:
        if True:  # pylint: disable=using-constant-test
            raise NotImplementedError(
                "AttributePollingComponentManager doesn't implement on, off, standby or reset"
            )

    def standby(  # noqa: D102
        self, task_callback: TaskCallbackType | None = None
    ) -> tuple[TaskStatus, str]:
        if True:  # pylint: disable=using-constant-test
            raise NotImplementedError(
                "AttributePollingComponentManager doesn't implement on, off, standby or reset"
            )

    def on(  # noqa: D102
        self, task_callback: TaskCallbackType | None = None
    ) -> tuple[TaskStatus, str]:
        if True:  # pylint: disable=using-constant-test
            raise NotImplementedError(
                "AttributePollingComponentManager doesn't implement on, off, standby or reset"
            )

    def reset(  # noqa: D102
        self, task_callback: TaskCallbackType | None = None
    ) -> tuple[TaskStatus, str]:
        if True:  # pylint: disable=using-constant-test
            raise NotImplementedError(
                "AttributePollingComponentManager doesn't implement on, off, standby or reset"
            )

    def abort_commands(  # noqa: D102
        self, task_callback: TaskCallbackType | None = None
    ) -> tuple[TaskStatus, str]:
        if True:  # pylint: disable=using-constant-test
            raise NotImplementedError(
                "AttributePollingComponentManager doesn't implement on, off, standby or reset"
            )

    def poll_failed(self, exception: Exception) -> None:
        """
        Set PowerState.UNKNOWN when polling fails.

        This is a bug fix that should be upstreamed to ska-tango-base once we
        are confident it works.

        :param exception: the exception that was raised by a recent poll
            attempt.
        """
        super().poll_failed(exception)

        # Should this go before or after updating the communication state?
        self._update_component_state(power=PowerState.UNKNOWN)

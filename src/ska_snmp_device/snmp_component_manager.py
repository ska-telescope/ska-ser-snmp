import logging
import time
from itertools import groupby
from typing import Any, Callable, Generator, Iterable

from more_itertools import chunked, iter_except
from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi import ContextData, UdpTransportTarget, getCmd, setCmd
from pysnmp.hlapi.auth import CommunityData, UsmUserData
from pysnmp.proto.errind import ErrorIndication
from pysnmp.proto.rfc1905 import unSpecified
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType
from ska_control_model import PowerState, TaskStatus
from ska_tango_base.base import CommunicationStatusCallbackType, TaskCallbackType
from ska_tango_base.poller import PollingComponentManager

from ska_snmp_device.types import SNMPAttrInfo, python_to_snmp, snmp_to_python


class SNMPComponentManager(PollingComponentManager[list[ObjectType], list[ObjectType]]):
    # pylint: disable=too-many-instance-attributes
    SNMPCmdFn = Callable[
        [
            SnmpEngine,
            CommunityData | UsmUserData,
            UdpTransportTarget,
            ContextData,
            ObjectType,
        ],
        Iterable,
    ]

    def __init__(  # noqa: D107
        self,
        host: str,
        port: int,
        community: str,
        max_objects_per_pdu: int,
        logger: logging.Logger,
        communication_state_callback: CommunicationStatusCallbackType,
        component_state_callback: Callable[..., None],
        snmp_attributes: list[SNMPAttrInfo],
        poll_rate: float,
    ):
        # pylint: disable=too-many-arguments
        super().__init__(
            logger,
            communication_state_callback,
            component_state_callback,
            poll_rate=poll_rate,
            **{attr_info.name: None for attr_info in snmp_attributes},
        )

        # Map from SNMP symbolic ID (MIB, symbol name, *indexes) to a metadata
        # object describing the associated attribute
        self._snmp_attrs: dict[tuple[str | int, ...], SNMPAttrInfo] = {
            attr_info.identity: attr_info for attr_info in snmp_attributes
        }

        # The same map, but mapping by Tango attribute name
        self._snmp_attrs_by_name: dict[str, SNMPAttrInfo] = {
            attr_info.name: attr_info for attr_info in snmp_attributes
        }

        # Used to create our SNMP connection
        self._host = host
        self._port = port
        self._community = community

        # This determines how many OIDs will be stuffed into an SNMP
        # Protocol Data Unit, i.e. a single packet
        self._max_objects_per_pdu = max_objects_per_pdu

        # Writes accumulate here in between polls
        self._pending_writes: dict[tuple[str | int, ...], Any] = {}

        # store the last time each attribute was successfully polled,
        # used to calculate when to poll again based on polling_period
        self._last_polled = {attr.identity: float("-inf") for attr in snmp_attributes}

    def get_request(self) -> list[ObjectType]:
        """
        Assemble a list of ObjectTypes representing pending writes and reads.

        The writes appear first, and come from `self._pending_writes`. Reads
        are requested for each attribute whose last successful poll happened
        longer ago than its polling period, and each attribute being written.
        """
        # atomically drain the write queue
        pending_writes = dict(iter_except(self._pending_writes.popitem, KeyError))
        writes = [
            ObjectType(ObjectIdentity(*identity), value)
            for identity, value in pending_writes.items()
        ]

        now = time.time()
        reads = [
            ObjectType(ObjectIdentity(*identity))
            for identity, attr in self._snmp_attrs.items()
            if now - self._last_polled[identity] >= attr.polling_period
            or identity in pending_writes  # bonus poll after writing
        ]

        return [*writes, *reads]

    def poll(self, poll_request: list[ObjectType]) -> list[ObjectType]:
        """
        Group by writes and reads, chunk, and run the appropriate SNMP command.

        Aggregate any returned ObjectTypes from GET commands as the poll response.
        """
        poll_response: list[ObjectType] = []
        for cmd, group in groupby(poll_request, self._snmp_cmd_for_obj):
            for objs in chunked(group, self._max_objects_per_pdu):
                poll_response.extend(self._snmp_cmd(cmd, objs))
        return poll_response

    def poll_succeeded(self, poll_response: list[ObjectType]) -> None:
        """
        Notify the device of the return values of a successful poll.

        This involves type coercion from PySNMP- to PyTango-compatible types.
        """
        super().poll_succeeded(poll_response)
        state_updates = {}
        polled_oids = []
        for oid, val in poll_response:
            oid_symbolic = self._mib_symbolic(oid)
            attr_info = self._snmp_attrs[oid_symbolic]
            state_updates[attr_info.name] = snmp_to_python(attr=attr_info, value=val)
            polled_oids.append(oid_symbolic)

        now = time.time()
        self._last_polled.update((k, now) for k in polled_oids)

        self._update_component_state(power=PowerState.ON, **state_updates)

    def enqueue_write(self, attr_name: str, val: Any) -> None:
        """
        Queue an attribute value to be written on the next poll.

        If there is already a write pending for the attribute, it will be superseded.
        """
        # Tango DevEnums have to start at 0, but many SNMP enums start at 1.
        # So we add an "invalid" 0 value to the enum, and check for it here.
        attr = self._snmp_attrs_by_name[attr_name]
        converted_value = python_to_snmp(attr, val)
        self._pending_writes[attr.identity] = converted_value

    def _snmp_cmd(
        self, cmd_fn: SNMPCmdFn, objects: Iterable[ObjectType]
    ) -> Generator[ObjectType, None, None]:
        """
        Execute the given SNMP command with the given objects.

        Yields each valued ObjectType in the response in the case of GET, and
        nothing in the case of SET. No other commands are currently supported.
        """
        iterator = cmd_fn(
            SnmpEngine(),
            CommunityData(self._community),
            UdpTransportTarget((self._host, self._port)),
            ContextData(),
            *objects,
        )

        error_indication: ErrorIndication
        result: Iterable[ObjectType]
        for error_indication, _, _, result in iterator:
            # TODO error handling could be more sophisticated
            if error_indication:
                raise error_indication

            # The value returned from a SET will just be what we put in,
            # but the internal state of the device as returned by a GET
            # may not have changed yet. So instead of updating state after
            # setting, just wait for a poll to reflect the new reality.
            if cmd_fn is not setCmd:
                yield from result

    @staticmethod
    def _snmp_cmd_for_obj(obj: ObjectType) -> SNMPCmdFn:
        # pylint: disable=protected-access
        val = obj._ObjectType__args[1]  # noqa
        cmd: SNMPComponentManager.SNMPCmdFn = getCmd if val is unSpecified else setCmd
        return cmd

    @staticmethod
    def _mib_symbolic(oid: ObjectIdentity) -> tuple[str | int, ...]:
        """
        Construct a (mib_name, symbol_name, *indexes) tuple from an ObjectIdentity.

        This is nearly the same as ObjectIdentity.getMibSymbol(), but that returns
        the indexes as a nested tuple, which we need to flatten. The returned value
        is suitable to be unpacked as the arguments to ObjectIdentity.__init__().

        There's another complication when dealing with SNMP objects that aren't
        part of a table (i.e. OIDs whose last segment is "0"). PySNMP returns
        these indexes as ObjectName, rather than Integer32. ObjectName is an
        iterable, which adds another level of nesting that we need to unroll.
        """
        mib, name, indices = oid.getMibSymbol()
        indices = (y for x in indices for y in (x if isinstance(x, Iterable) else [x]))
        return mib, name, *indices

    def off(  # noqa: D102
        self, task_callback: TaskCallbackType | None = None
    ) -> tuple[TaskStatus, str]:
        raise NotImplementedError(
            "SNMPComponentManager doesn't implement on, off, standby or reset"
        )

    def standby(  # noqa: D102
        self, task_callback: TaskCallbackType | None = None
    ) -> tuple[TaskStatus, str]:
        raise NotImplementedError(
            "SNMPComponentManager doesn't implement on, off, standby or reset"
        )

    def on(  # noqa: D102
        self, task_callback: TaskCallbackType | None = None
    ) -> tuple[TaskStatus, str]:
        raise NotImplementedError(
            "SNMPComponentManager doesn't implement on, off, standby or reset"
        )

    def reset(  # noqa: D102
        self, task_callback: TaskCallbackType | None = None
    ) -> tuple[TaskStatus, str]:
        raise NotImplementedError(
            "SNMPComponentManager doesn't implement on, off, standby or reset"
        )

import logging
from typing import Any, Callable, Generator, Iterable, Mapping, Sequence

from more_itertools import chunked
from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi import ContextData, UdpTransportTarget, getCmd, setCmd
from pysnmp.hlapi.auth import CommunityData, UsmUserData
from pysnmp.proto.errind import ErrorIndication
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType
from ska_tango_base.base import CommunicationStatusCallbackType

from ska_low_itf_devices.attribute_polling_component_manager import (
    AttributePollingComponentManager,
    AttrPollRequest,
    AttrPollResponse,
)
from ska_snmp_device.types import SNMPAttrInfo, python_to_snmp, snmp_to_python


class SNMPComponentManager(AttributePollingComponentManager):
    _attributes: Mapping[str, SNMPAttrInfo]

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
        authority: str | dict[str, str],
        max_objects_per_pdu: int,
        logger: logging.Logger,
        communication_state_callback: CommunicationStatusCallbackType,
        component_state_callback: Callable[..., None],
        attributes: Sequence[SNMPAttrInfo],
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

        # Used to create our SNMP connection
        self._host = host
        self._port = port
        if isinstance(authority, str):
            self._access = CommunityData(authority)
        else:
            self._access = UsmUserData(
                str(authority["auth"]),
                authKey=str(authority["authKey"]),
                privKey=str(authority["privKey"]),
            )

        # This determines how many OIDs will be stuffed into an SNMP
        # Protocol Data Unit, i.e. a single packet
        self._max_objects_per_pdu = max_objects_per_pdu

    def poll(self, poll_request: AttrPollRequest) -> AttrPollResponse:
        """
        Group by writes and reads, chunk, and run the appropriate SNMP command.

        Aggregate any returned ObjectTypes from GET commands as the poll response.
        """

        for write_chunk in chunked(
            poll_request.writes.items(), self._max_objects_per_pdu
        ):
            objs = [
                ObjectType(ObjectIdentity(*self._attributes[attr_name].identity), value)
                for attr_name, value in write_chunk
            ]
            # The value returned from a SET will just be what we put in,
            # but the internal state of the device as returned by a GET
            # may not have changed yet. So instead of updating state after
            # setting, just wait for a poll to reflect the new reality.
            for _ in self._snmp_cmd(setCmd, objs):
                pass

        state_updates: AttrPollResponse = {}
        for read_chunk in chunked(poll_request.reads, self._max_objects_per_pdu):
            oid_attr_map = {
                attr.identity: attr
                for attr_name in read_chunk
                for attr in [self._attributes[attr_name]]
            }
            objs = [
                ObjectType(ObjectIdentity(*self._attributes[attr_name].identity))
                for attr_name in read_chunk
            ]
            for oid, val in self._snmp_cmd(getCmd, objs):
                attr = oid_attr_map[self._mib_symbolic(oid)]
                pyval = snmp_to_python(attr, val)
                value = self.override_snmp_type(attr, pyval)
                state_updates[attr.name] = value
        return state_updates

    def override_snmp_type(self, attr: SNMPAttrInfo, pyval: Any) -> str | int | float:
        """
        Override snmp data type if attr.dtype specified in config.

        If the smnp data value is located in a module table the snmp
        data type is usually a string. This may be problematic if you
        require setting the attribute value for e.g min/max value/alarm
        Override can be achieved by specifying the dtype in the configuration
        file. Basic implementation here but more types can be added
        """
        value = pyval
        if attr.dtype == "float" or attr.dtype == "double":
            value = float(pyval)
        if attr.dtype == "int":
            value = int(pyval)
        if attr.dtype == "boolean":
            value = bool(int(pyval))
        if attr.dtype == "enum":
            value = int(pyval)
        return value

    def from_python(self, attr_name: str, val: Any) -> Any:
        """
        Convert from raw Python type to a hardware-compatible type.

        This is called in enqueue_write() so that any conversion error happens
        early, when an attribute is set, rather than in the polling thread.
        """
        attr = self._attributes[attr_name]
        return python_to_snmp(attr, val)

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
            self._access,
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
            yield from result

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

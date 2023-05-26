"""
Functions to handle translation between PyTango- and PySNMP-compatible types.

It should be possible to add support for new types by only modifying
the functions in this module.
"""

from dataclasses import dataclass
from enum import Enum, EnumMeta, IntEnum
from functools import reduce
from math import ceil
from typing import Any

from pyasn1.type.base import Asn1Type
from pyasn1.type.constraint import ValueRangeConstraint
from pyasn1.type.namedval import NamedValues
from pyasn1.type.univ import Integer
from pysnmp.proto.rfc1902 import Bits, OctetString
from tango import AttrDataFormat

_SNMP_ENUM_INVALID = "_SNMPEnum__INVALID__"


class BitEnum(IntEnum):
    """This exists to let us dispatch on Enum subclass elsewhere."""


@dataclass(frozen=True)
class SNMPAttrInfo:
    name: str
    identity: tuple[str | int, ...]
    attr_args: dict[str, Any]
    polling_period: float
    dtype: type


def snmp_to_python(attr: SNMPAttrInfo, value: Asn1Type) -> Any:
    """Coerce a PySNMP value to a PyTango-compatible Python type."""
    if isinstance(value, Integer):
        value = int(value)
    if isinstance(value, Bits):
        return [
            attr.dtype((byte * 8) + bit)
            for byte, int_val in enumerate(bytes(value))
            for bit in range(8)
            if int_val & (0b10000000 >> bit)
        ]
    if isinstance(value, OctetString):
        return str(value)
    return value


def python_to_snmp(attr: SNMPAttrInfo, value: Any) -> Any:
    """
    Coerce a Python/PyTango value to a PySNMP-compatible type.

    This has less work to do than snmp_to_python(), as PySNMP does a pretty
    good job of type coercion. We don't actually have to create an Asn1Type
    object here; that happens deep in the bowels of PySNMP.
    """
    if issubclass(attr.dtype, BitEnum):
        n_bytes = ceil(len(attr.dtype) / 8)
        int_vals = [0] * n_bytes
        for bit in value:
            int_vals[bit // 8] |= 0b10000000 >> bit
        bytes_val = bytes(int_vals)
        return bytes_val
    if issubclass(attr.dtype, Enum):
        if value == 0:
            # I'd prefer to get enum labels directly from Tango, but I can't
            # figure it an easy way, so we refer back to our attr args.
            if attr.dtype(value).name == _SNMP_ENUM_INVALID:
                raise ValueError(f"Enum value 0 for {attr.name} is invalid.")
    return value


def attr_args_from_snmp_type(snmp_type: Asn1Type) -> dict[str, Any]:
    """
    Given an SNMP type, return kwargs to be passed to tango.server.attribute().

    Currently only strings, enums, bits, and various kinds of ints are implemented,
    but adding more types will be a matter of adding more cases to this if statement.
    """
    attr_args: dict[str, Any] = {}
    if isinstance(snmp_type, Bits):
        enum = _enum_from_named_values(snmp_type.namedValues, cls=BitEnum)
        attr_args.update(
            dtype=enum,
            dformat=AttrDataFormat.SPECTRUM,
            max_dim_x=len(enum),
        )
    elif isinstance(snmp_type, OctetString):
        attr_args.update(
            dtype=str,
        )
    elif isinstance(snmp_type, Integer):
        # Specific case where an integer field has an enum constraint.
        # I'm assuming here that if there are namedValues, there are no
        # other valid-but-unnamed values - true for the MIBs I've seen.
        if snmp_type.namedValues:
            try:
                attr_args.update(dtype=_enum_from_named_values(snmp_type.namedValues))
            except ValueError:
                pass
        else:
            attr_args.update(
                dtype=int,
                abs_change=1,
            )
            # In PySNMP, all integers' subtypeSpec should be a ConstraintsIntersection.
            # Different flavours of integer then add a ValueRangeConstraint, and SNMP
            # objects can then apply their own range constraints. If we calculate the
            # intersection of these ranges, we can pass min and max values to Tango.
            if all(isinstance(x, ValueRangeConstraint) for x in snmp_type.subtypeSpec):
                ranges = ((r.start, r.stop) for r in snmp_type.subtypeSpec)
                start, stop = reduce(_range_intersection, ranges)
                attr_args.update(
                    min_value=start,
                    max_value=stop,
                )

    return attr_args


def _enum_from_named_values(
    named_values: NamedValues, cls: EnumMeta = IntEnum
) -> EnumMeta:
    """
    Create an Enum subclass from a NamedValues object.

    NamedValues is the class PySNMP uses to represent the named values
    of an INTEGER or BITS object, if they are declared in the MIB.
    """
    enum_entries = {v: k for k, v in named_values.items()}

    # Tango DevEnum requires that values start at 0 and increment, but many
    # SNMP enum values start at 1, so we bung in an "invalid" zero value in
    # that case. A bit janky but it's an improvement on a bare int.
    if 0 not in enum_entries:
        enum_entries[0] = _SNMP_ENUM_INVALID

    # test that entries are sequential
    enum_sorted = [(v, k) for k, v in sorted(enum_entries.items())]
    if all(x == i for i, (_, x) in enumerate(enum_sorted)):
        return cls("SNMPEnum", enum_sorted)

    raise ValueError("named values incompatible with Tango DevEnum")


def _range_intersection(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
    """
    Return the intersection of ranges a and b, defined as (start, end) tuples.

    Ranges are inclusive of their bounds. If they don't intersect, raise ValueError.
    """
    # pylint: disable=invalid-name
    c = max(a[0], b[0]), min(a[1], b[1])
    if c[0] > c[1]:
        raise ValueError(f"Ranges {a} and {b} are disjoint")
    return c

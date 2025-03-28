#  -*- coding: utf-8 -*-
#
# This file is part of the SKA SER SNMP project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
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
from pyasn1.type.constraint import ConstraintsUnion, ValueRangeConstraint
from pyasn1.type.namedval import NamedValues
from pyasn1.type.univ import Integer
from pysnmp.proto.rfc1902 import Bits, OctetString
from tango import AttrDataFormat, DevEnum, DevULong64

from ska_attribute_polling.attribute_polling_component_manager import AttrInfo

_SNMP_ENUM_INVALID_PREFIX = "_SNMPEnum_INVALID_"


class BitEnum(IntEnum):
    """This exists to let us dispatch on Enum subclass elsewhere."""


def strbool(value: Asn1Type) -> bool:
    """
    Convert Asn1Type string representation to bool.

    :param value: string representation of bool

    :return: True or  False
    """
    return bool(int(value))


@dataclass(frozen=True)
class SNMPAttrInfo(AttrInfo):
    """Helper class to hold attribute information."""

    identity: tuple[str | int, ...]


def dtype_string_to_type(dtype: str) -> Any:
    """
    Convert a string as provided as an override to an attribute's type.

    Take the string dtype from the YAML configuration file, and returns a
    corresponding Python type or callable.

    :param dtype: string dtype from yaml

    :return: callable dtype
    """
    # TODO define the full set of valid string dtypes
    str_dtypes: dict[str, Any] = {
        "float": float,
        "double": float,
        "int": int,
        "enum": DevEnum,
        "bool": bool,
        "boolean": bool,  # it pays homage to tango.DevBoolean
    }
    return str_dtypes[dtype]


def snmp_to_python(attr: SNMPAttrInfo, value: Asn1Type) -> Any:
    """
    Coerce a PySNMP value to a PyTango-compatible Python type.

    :param attr: attribute information
    :param value: data type of the attribute

    :raises ValueError: conversion to Enum
    :return: the python value
    """
    try:
        if isinstance(value, Integer) or attr.dtype == int:
            value = int(value)
        elif isinstance(value, Bits):
            value = [
                attr.dtype((byte * 8) + bit)
                for byte, int_val in enumerate(bytes(value))
                for bit in range(8)
                if int_val & (0b10000000 >> bit)
            ]
        elif attr.dtype == bool:
            value = strbool(value)
        elif attr.dtype == float:
            value = float(value)
        elif attr.dtype == DevEnum and attr.attr_args.get("enum_labels"):
            value = int(value)
        elif isinstance(value, OctetString):
            value = str(value)
        else:
            raise ValueError(f"Cannot convert unsupported type {type(value)}")
        return value
    except ValueError as exc:
        raise ValueError(
            f"{attr.name} cannot convert to '{value}' to {attr.dtype}"
        ) from exc


def python_to_snmp(attr: SNMPAttrInfo, value: Any) -> Any:
    """
    Coerce a Python/PyTango value to a PySNMP-compatible type.

    This has less work to do than snmp_to_python(), as PySNMP does a pretty
    good job of type coercion. We don't actually have to create an Asn1Type
    object here; that happens deep in the bowels of PySNMP.

    :param attr: attribute information
    :param value: data type of the attribute

    :raises ValueError: If there is an invalid enum
    :return: the snmp value
    """
    if issubclass(attr.dtype, BitEnum):
        n_bytes = ceil(len(attr.dtype) / 8)
        int_vals = [0] * n_bytes
        for bit in value:
            int_vals[bit // 8] |= 0b10000000 >> bit
        bytes_val = bytes(int_vals)
        return bytes_val
    if issubclass(attr.dtype, Enum):
        # I'd prefer to get enum labels directly from Tango, but I can't
        # figure it an easy way, so we refer back to our attr args.
        if attr.dtype(value).name.startswith(_SNMP_ENUM_INVALID_PREFIX):
            raise ValueError(f"Enum value {value} for {attr.name} is invalid.")
    return value


# pylint: disable=too-many-nested-blocks, too-many-branches
def attr_args_from_snmp_type(snmp_type: Asn1Type) -> dict[str, Any]:
    """
    Given an SNMP type, return kwargs to be passed to tango.server.attribute().

    Currently only strings, enums, bits, and various kinds of ints are implemented,
    but adding more types will be a matter of adding more cases to this if statement.

    :param snmp_type: snmp data type of the attribute

    :return: tango server attribute info
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
                attr_args.update(
                    dtype=_enum_from_named_values(snmp_type.namedValues),
                )
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
            range_constraints = []
            for constraint in snmp_type.subtypeSpec:
                if isinstance(constraint, ValueRangeConstraint):
                    range_constraints.append(constraint)
                if isinstance(constraint, ConstraintsUnion):
                    for sub_constraint in constraint:
                        if isinstance(sub_constraint, ValueRangeConstraint):
                            range_constraints.append(sub_constraint)
            ranges = ((r.start, r.stop) for r in range_constraints)
            start, stop = reduce(_range_intersection, ranges)
            attr_args.update(
                min_value=start,
                max_value=stop,
            )
            # https://gitlab.com/tango-controls/cppTango/-/issues/1132
            # Stop-gap to support Counter64. Perhaps we should always
            # specify the smallest compatible Tango int type?
            if stop.bit_length() > 63:
                attr_args["dtype"] = DevULong64
                if (stop + 1).bit_length() == 65:
                    del attr_args["max_value"]
    return attr_args


def _enum_from_named_values(
    named_values: NamedValues, cls: EnumMeta = IntEnum
) -> EnumMeta:
    """
    Create an Enum subclass from a NamedValues object.

    :param named_values: is the class PySNMP uses to represent the named values
        of an INTEGER or BITS object, if they are declared in the MIB.
    :param cls: data type class

    :return: the tango enum
    """
    valued_names = {int_val: name for name, int_val in named_values.items()}

    # Tango DevEnum requires that values start at 0 and increment, but many
    # SNMP enum values start at 1, so we insert "invalid" entries in that
    # case, and check for them when attributes are written.
    enum_entries = [
        (valued_names.get(x, _SNMP_ENUM_INVALID_PREFIX + str(x)), x)
        for x in range(max(valued_names) + 1)
    ]
    return cls("SNMPEnum", enum_entries)


def _range_intersection(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
    """
    Return the intersection of ranges a and b, defined as (start, end) tuples.

    Ranges are inclusive of their bounds. If they don't intersect, raise ValueError.

    :param a: start,stop values of a range to be compared to b
    :param b: start,stop values of a range to be compared to a

    :raises ValueError: range do not intersect
    :return: the start,stop intersection values
    """
    c = max(a[0], b[0]), min(a[1], b[1])
    if c[0] > c[1]:
        raise ValueError(f"Ranges {a} and {b} are disjoint")
    return c

"""
Functions to handle parsing and validating device definition files.
"""

import itertools
import string
from typing import Any, Generator

import yaml
from pysnmp.smi.builder import MibBuilder
from pysnmp.smi.compiler import addMibCompiler
from tango import AttrWriteType

from ska_snmp_device.types import SNMPAttrInfo, attr_args_from_snmp_type


def load_device_definition(filename: str) -> Any:
    """
    Return the parsed contents of the YAML file at filename.
    """
    with open(filename, encoding="utf-8") as def_file:
        # TODO here would be a good place for some schema validation
        return yaml.safe_load(def_file)


def parse_device_definition(definition: dict[str, Any]) -> list[SNMPAttrInfo]:
    """Build attribute metadata from a deserialised device definition file."""

    # Keep this out of the loop so that we only create this thing once
    mib_builder = _create_mib_builder()
    return [
        _build_attr_info(mib_builder, attr_info)
        for attr_template in definition["attributes"]
        for attr_info in _expand_attribute(attr_template)
    ]


def _build_attr_info(mib_builder: MibBuilder, attr: dict[str, Any]) -> SNMPAttrInfo:
    """
    Build a SNMPAttrInfo describing the provided attribute.

    Using the relevant MIB files, we inspect the SNMP type and return
    useful metadata about the attribute in an SNMPAttrInfo, including
    suitable arguments to pass to tango.server.attribute().
    """

    # Pop off the values we're going to use in this function. The rest will
    # be used as overrides to the generated tango.server.attribute() args.
    mib_name, symbol_name, *_ = oid = tuple(attr.pop("oid"))
    polling_period = attr.pop("polling_period", 0) / 1000

    # get metadata about the SNMP object definition in the MIB
    (mib_info,) = mib_builder.importSymbols(mib_name, symbol_name)

    # Build args to be passed to tango.server.attribute()
    attr_args = {
        "access": {
            "readonly": AttrWriteType.READ,
            "writeonly": AttrWriteType.WRITE,
            "readwrite": AttrWriteType.READ_WRITE,
        }[mib_info.maxAccess],
        **attr_args_from_snmp_type(mib_info.syntax),
        **attr,  # allow user to override generated args
    }

    return SNMPAttrInfo(
        # named and dtype are duplicated here, but they're used a lot,
        # so I grant them the rank of class member
        name=attr_args["name"],
        dtype=attr_args["dtype"],
        identity=oid,
        attr_args=attr_args,
        polling_period=polling_period,
    )


def _create_mib_builder() -> MibBuilder:
    """Initialise a MibBuilder that knows where to look for MIBs."""
    mib_builder: MibBuilder = MibBuilder()
    mib_builder.loadTexts = True

    # Adding a compiler allows the builder to fetch and compile novel MIBs.
    # mibs.pysnmp.com is built from https://github.com/lextudio/mibs.pysnmp.com
    # and contains thousands of standard MIBs and vendor MIBs for COTS hardware.
    # Extra MIBs can be dropped in resources/mibs, which will be searched first.
    addMibCompiler(
        mib_builder, sources=["resources/mibs", "https://mibs.pysnmp.com/asn1/@mib@"]
    )

    return mib_builder


def _expand_attribute(attr: Any) -> Generator[Any, None, None]:
    """
    Yield templated copies of attr, based on the "indexes" key.

    "indexes" should be a list of N ranges [a, b], where a <= b. One
    attribute definition will be yielded for each element (i1, ..., iN)
    of the cartesian product of the provided ranges. The "name" field
    of each attribute will be formatted with name.format(i1, ..., iN).

    If "indexes" is not present, attr will be yielded unmodified. This
    function also performs some validation on the attribute definition.
    """
    suffix = attr["oid"][2:]
    indexes = attr.pop("indexes", [])
    name = attr["name"]

    # Be kind, provide useful error messages
    replacements = [x for _, x, _, _ in string.Formatter().parse(name) if x is not None]
    if indexes:
        if not replacements:
            raise ValueError(
                f'Attribute name "{name}" contains no format specifiers, but defines an index'
            )
    else:
        if replacements:
            raise ValueError(
                f'Attribute name "{name}" contains format specifiers, but no indexes were provided'
            )
        if not suffix:
            raise ValueError(
                f'OID for attribute "{name}" must have a suffix - use 0 for a scalar object'
            )

    index_ranges = (range(a, b + 1) for a, b in indexes)
    for element in itertools.product(*([i] for i in suffix), *index_ranges):
        index_vars = element[len(suffix) :]  # black wants this space T_T
        formatted_name = name.format(*index_vars)
        if not formatted_name.isidentifier():
            raise ValueError(
                f'Attribute name "{formatted_name}" is not a valid Python identifier'
            )
        yield {
            **attr,
            "name": formatted_name,
            "oid": [*attr["oid"], *index_vars],
        }

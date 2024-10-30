#  -*- coding: utf-8 -*-
#
# This file is part of the SKA SER SNMP project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Functions to handle parsing and validating device definition files."""

import itertools
import logging
import os
import string
from pathlib import Path
from typing import Any, Generator, Optional

import yaml
from pysnmp.smi.builder import MibBuilder
from pysnmp.smi.compiler import addMibCompiler
from ska_telmodel.data import TMData
from tango import AttrWriteType

from ska_snmp_device.types import (
    SNMPAttrInfo,
    attr_args_from_snmp_type,
    dtype_string_to_type,
)


def load_device_definition(filename: str, repo: Optional[str]) -> Any:
    """
    Return the parsed contents of the YAML file at filename.

    :param filename: configuration file yaml file
    :param repo: the telmodel repo that we're pulling from

    :raises Exception: no configuration file found
    :return: the configuration dictionary
    """
    if repo is not None:
        try:
            logging.info(f"attempting to load device definition from repo {repo}")
            tmdata = TMData(
                [repo]
            )
            return tmdata[filename].get_dict()
        except Exception:
            logging.warning(f"{repo} {filename} is not an SKA_TelModel configuration")
    try:
        logging.info(f"attempting to load device definition from {filename}")
        path = Path(filename).resolve()
        logging.info(f"directory {os.getcwd()}")
        logging.info(f"loading yaml file {path}")
        with open(path, encoding="utf-8") as def_file:
            logging.info(f"loading yaml file {path}")
            return yaml.safe_load(def_file)
    except Exception as ex:
        logging.error(f"No configuration file {filename} to load")
        raise ex
    # pylint: disable=broad-exception-caught




def parse_device_definition(definition: dict[str, Any]) -> list[SNMPAttrInfo]:
    """
    Build attribute metadata from a deserialised device definition file.

    :param definition: device definition file

    :return: list of deserialised attribute metadata
    """
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

    :param mib_builder: mib builder
    :param attr: attribute

    :raises TypeError: no associated Python type
    :return: SNMP attribute information
    """
    # Pop off the values we're going to use in this function. The rest will
    # be used as overrides to the generated tango.server.attribute() args.
    mib_name, symbol_name, *_ = oid = tuple(attr.pop("oid"))
    polling_period = attr.pop("polling_period", 0) / 1000

    # get metadata about the SNMP object definition in the MIB
    (mib_info,) = mib_builder.importSymbols(mib_name, symbol_name)

    if isinstance(attr.get("dtype"), str):
        try:
            attr["dtype"] = dtype_string_to_type(attr["dtype"])
        except KeyError as exc:
            raise TypeError(
                f"The string type \"{attr['dtype']}\" "
                f"provided for attribute \"{attr['name']}\" "
                "has no associated Python type"
            ) from exc

    # Build args to be passed to tango.server.attribute()
    attr_args = {
        "access": {
            "readonly": AttrWriteType.READ,
            "read-only": AttrWriteType.READ,
            "writeonly": AttrWriteType.WRITE,
            "write-only": AttrWriteType.WRITE,
            "readwrite": AttrWriteType.READ_WRITE,
            "read-write": AttrWriteType.READ_WRITE,
        }[mib_info.maxAccess],
        **attr_args_from_snmp_type(mib_info.syntax),
        **attr,  # allow user to override generated args
    }

    return SNMPAttrInfo(
        polling_period=polling_period,
        attr_args=attr_args,
        identity=oid,
    )


def _create_mib_builder() -> MibBuilder:
    """
    Initialise a MibBuilder that knows where to look for MIBs.

    :return: the mib builder
    """
    mib_builder: MibBuilder = MibBuilder()
    mib_builder.loadTexts = True

    # Adding a compiler allows the builder to fetch and compile novel MIBs.
    # mibs.pysnmp.com is built from https://github.com/lextudio/mibs.pysnmp.com
    # and contains thousands of standard MIBs and vendor MIBs for COTS hardware.
    # Extra MIBs can be dropped in ./mibs, which will be searched first.
    addMibCompiler(
        mib_builder,
        sources=[
            str(Path(__file__).parent / "mib_library"),
            "https://mibs.pysnmp.com/asn1/@mib@",
        ],
    )

    return mib_builder


def _expand_attribute(attr: Any) -> Generator[Any, None, None]:
    """
    Yield templated copies of attr, based on the "indexes" key.

    "indexes" should be a list of N ranges [a, b], where a <= b. One
    attribute definition will be yielded for each element (i1, ..., iN)
    of the cartesian product of the provided ranges. The "name" field
    of each attribute will be formatted with name.format(i1, ..., iN).

    Additionally "indexes" may have an increment to allow for equally spaced
    non sequential oid's [a, b, c] where b = a + (N-1)c. In this case it may also
    be desireable for the name to run sequentially. Therefore 2 additional specifiers
    have been added "start_index" and  "placeholder_index" from which the
    names formating placeholder_index is substituted which the new starting index
    (i1 ..., placeholder_index, ... iN)

    If "indexes" is not present, attr will be yielded unmodified. This
    function also performs some validation on the attribute definition.

    :param attr: the attribute

    :raises ValueError: formatting errors

    :yields: copies of the attribute
    """
    suffix = attr["oid"][2:]
    start_index = attr.pop("start_index", None)
    placeholder_index = attr.pop("placeholder_index", 0)
    indexes = attr.pop("indexes", [])
    name = attr["name"]

    # Be kind, provide useful error messages
    replacements = [x for _, x, _, _ in string.Formatter().parse(name) if x is not None]
    if indexes:
        if not replacements:
            raise ValueError(
                f'Attribute name "{name}" contains no format specifiers,'
                " but defines an index"
            )
    else:
        if replacements:
            raise ValueError(
                f'Attribute name "{name}" contains format specifiers,'
                " but no indexes were provided"
            )
        if not suffix:
            raise ValueError(
                f'OID for attribute "{name}" must have a suffix'
                " - use 0 for a scalar object"
            )

    index_ranges = (
        (range(v[0], v[1] + v[2], v[2])) if len(v) > 2 else (range(v[0], v[1] + 1))
        for v in indexes
    )
    for element in itertools.product(*([i] for i in suffix), *index_ranges):
        index_vars = element[len(suffix) :]  # black wants this space T_T
        index_vars_list = list(index_vars)
        if start_index is not None:
            index_vars_list[placeholder_index] = start_index
            start_index += 1
        formatted_name = name.format(*index_vars_list)
        if not formatted_name.isidentifier():
            raise ValueError(
                f'Attribute name "{formatted_name}" is not a valid Python identifier'
            )

        yield {
            **attr,
            "name": formatted_name,
            "oid": [*attr["oid"], *index_vars],
        }

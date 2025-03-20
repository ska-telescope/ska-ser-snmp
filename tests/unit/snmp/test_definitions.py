#  -*- coding: utf-8 -*-
#
# This file is part of the SKA SER SNMP project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defines the tests the device definitions for ska-ser-snmp."""

import pytest
import yaml
from tango import AttrWriteType

from ska_snmp_device.definitions import (
    _adjust_overrides,
    _expand_attribute,
    load_device_definition,
    parse_device_definition,
)


def test_parse_definition_regression(definition_path: str) -> None:
    """
    Test parsing the device definition file.

    :param definition_path: localtion of the yaml file
    """
    definition = load_device_definition(definition_path, "")
    attributes = parse_device_definition(definition)
    # TODO compare this properly to a baseline
    assert len(attributes) == 9


def test_expand_attribute_singular() -> None:
    """Test loading a single attribute."""
    template = yaml.safe_load(
        """
    name: singular_attr_the_second
    oid: [MY-MIB, anotherObject, 2, 8, what, 5]
    """
    )
    assert [template] == list(_expand_attribute(template))


def test_expand_attribute_indexed() -> None:
    """Test loading an indexed attribute."""
    template = yaml.safe_load(
        """
    name: plural_attr_{}
    oid: [MY-MIB, tableObject]
    indexes:
      - [4, 6]
    """
    )

    expected = yaml.safe_load(
        """
    - name: plural_attr_4
      oid: [MY-MIB, tableObject, 4]
    - name: plural_attr_5
      oid: [MY-MIB, tableObject, 5]
    - name: plural_attr_6
      oid: [MY-MIB, tableObject, 6]
    """
    )

    assert expected == list(_expand_attribute(template))


def test_expand_attribute_nested() -> None:
    """Test loading a nested attribute."""
    template = yaml.safe_load(
        """
    name: flipped_{1}_nested_{0}
    oid: [MY-MIB, weirdObject, 3, string]
    indexes:
      - [4, 5]
      - [1, 2]
    """
    )

    expected = yaml.safe_load(
        """
    - name: flipped_1_nested_4
      oid: [MY-MIB, weirdObject, 3, string, 4, 1]
    - name: flipped_2_nested_4
      oid: [MY-MIB, weirdObject, 3, string, 4, 2]
    - name: flipped_1_nested_5
      oid: [MY-MIB, weirdObject, 3, string, 5, 1]
    - name: flipped_2_nested_5
      oid: [MY-MIB, weirdObject, 3, string, 5, 2]
    """
    )

    assert expected == list(_expand_attribute(template))


def test_expand_attribute_wr16() -> None:
    """Test loading non-sequential indexd attributes."""
    template = yaml.safe_load(
        """
    name: net_wr{1}_status
    oid: [MY-MIB, wrzParamValue]
    start_index: 0
    placeholder_index: 1
    indexes:
      - [4, 4]
      - [2010, 2310, 100]
      - [5, 5]
    """
    )

    expected = yaml.safe_load(
        """
    - name: net_wr0_status
      oid: [MY-MIB, wrzParamValue, 4, 2010, 5]
    - name: net_wr1_status
      oid: [MY-MIB, wrzParamValue, 4, 2110, 5]
    - name: net_wr2_status
      oid: [MY-MIB, wrzParamValue, 4, 2210, 5]
    - name: net_wr3_status
      oid: [MY-MIB, wrzParamValue, 4, 2310, 5]
    """
    )

    assert expected == list(_expand_attribute(template))


def test_expand_attribute_missing_suffix() -> None:
    """Test loading an attribute with malformed oid definition."""
    template = yaml.safe_load(
        """
    name: some_attribeaut
    oid: [CAW, blimey]
    """
    )

    with pytest.raises(ValueError, match="suffix"):
        list(_expand_attribute(template))


def test_expand_attribute_missing_index() -> None:
    """Test loading an attribute with malformed oid index definition."""
    template = yaml.safe_load(
        """
    name: attriboot_{}
    oid: [DOC, marten]
    """
    )

    with pytest.raises(ValueError, match="no index"):
        list(_expand_attribute(template))


def test_expand_attribute_missing_format() -> None:
    """Test loading an attribute with missing format specifiers."""
    template = yaml.safe_load(
        """
    name: attribrackets
    oid: [MIBBY, mibmib, 0]
    indexes:
      - [1, 5]
    """
    )

    with pytest.raises(ValueError, match="no format"):
        list(_expand_attribute(template))


def test_expand_attribute_invalid_identifier() -> None:
    """Test loading an invalid attribute."""
    template = yaml.safe_load(
        """
    name: attriboat!
    oid: [HMS, titanic, 0]
    """
    )

    with pytest.raises(ValueError, match="identifier"):
        list(_expand_attribute(template))


def test_expand_attribute_with_access() -> None:
    """Test loading an attribute with access mode specified."""
    template = yaml.safe_load(
        """
    attributes:
        - name: net_wr0_status
          oid: [MY-MIB, wr0_status, 0]
          access: read
        - name: net_wr1_status
          oid: [MY-MIB, wr1_status, 0]
          access: readonly
        - name: net_wr2_status
          oid: [MY-MIB, wr2_status, 0]
          access: read-only
        - name: net_wr3_status
          oid: [MY-MIB, wr3_status, 0]
          access: write
        - name: net_wr4_status
          oid: [MY-MIB, wr4_status, 0]
          access: writeonly
        - name: net_wr5_status
          oid: [MY-MIB, wr5_status, 0]
          access: write-only
        - name: net_wr6_status
          oid: [MY-MIB, wr6_status, 0]
          access: readwrite
        - name: net_wr7_status
          oid: [MY-MIB, wr7_status, 0]
          access: read-write
        """
    )
    expected = [
        {
            "name": "net_wr0_status",
            "oid": ["MY-MIB", "wr0_status", 0],
            "access": AttrWriteType.READ,
        },
        {
            "name": "net_wr1_status",
            "oid": ["MY-MIB", "wr1_status", 0],
            "access": AttrWriteType.READ,
        },
        {
            "name": "net_wr2_status",
            "oid": ["MY-MIB", "wr2_status", 0],
            "access": AttrWriteType.READ,
        },
        {
            "name": "net_wr3_status",
            "oid": ["MY-MIB", "wr3_status", 0],
            "access": AttrWriteType.WRITE,
        },
        {
            "name": "net_wr4_status",
            "oid": ["MY-MIB", "wr4_status", 0],
            "access": AttrWriteType.WRITE,
        },
        {
            "name": "net_wr5_status",
            "oid": ["MY-MIB", "wr5_status", 0],
            "access": AttrWriteType.WRITE,
        },
        {
            "name": "net_wr6_status",
            "oid": ["MY-MIB", "wr6_status", 0],
            "access": AttrWriteType.READ_WRITE,
        },
        {
            "name": "net_wr7_status",
            "oid": ["MY-MIB", "wr7_status", 0],
            "access": AttrWriteType.READ_WRITE,
        },
    ]
    attrlist = template["attributes"]
    adjusted = [_adjust_overrides(attr) for attr in attrlist]
    assert adjusted == expected

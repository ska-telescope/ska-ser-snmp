import pytest
import yaml

from ska_snmp_device.definitions import (
    _expand_attribute,
    load_device_definition,
    parse_device_definition,
)


def test_parse_definition_regression(definition_path):
    definition = load_device_definition(definition_path)
    attributes = parse_device_definition(definition)
    # TODO compare this properly to a baseline
    assert len(attributes) == 8


def test_expand_attribute_singular():
    template = yaml.safe_load(
        """
    name: singular_attr_the_second
    oid: [MY-MIB, anotherObject, 2, 8, what, 5]
    """
    )
    assert [template] == list(_expand_attribute(template))


def test_expand_attribute_indexed():
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


def test_expand_attribute_nested():
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


def test_expand_attribute_missing_suffix():
    template = yaml.safe_load(
        """
    name: some_attribeaut
    oid: [CAW, blimey]
    """
    )

    with pytest.raises(ValueError, match="suffix"):
        list(_expand_attribute(template))


def test_expand_attribute_missing_index():
    template = yaml.safe_load(
        """
    name: attriboot_{}
    oid: [DOC, marten]
    """
    )

    with pytest.raises(ValueError, match="no index"):
        list(_expand_attribute(template))


def test_expand_attribute_missing_format():
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


def test_expand_attribute_invalid_identifier():
    template = yaml.safe_load(
        """
    name: attriboat!
    oid: [HMS, titanic, 0]
    """
    )

    with pytest.raises(ValueError, match="identifier"):
        list(_expand_attribute(template))

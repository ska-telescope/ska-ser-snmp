#  -*- coding: utf-8 -*-
#
# This file is part of the SKA SER SNMP project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module tests the ska_ser_snmp version."""

import ska_snmp_device


def test_version() -> None:
    """Test that the ska_ser_snmp version is as expected."""
    assert ska_snmp_device.__version__ == "0.3.1"

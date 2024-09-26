#  -*- coding: utf-8 -*-
#
# This file is part of the SKA SER SNMP project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This package provides a generic Tango device class for controlling SNMP devices."""

__version__ = "0.2.0"

__all__ = [
    "SNMPDevice",
    "SNMPComponentManager",
    "SNMPAttrInfo",
    "attr_args_from_snmp_type",
]

from .snmp_device import SNMPDevice
from .snmp_component_manager import SNMPComponentManager
from .types import SNMPAttrInfo, attr_args_from_snmp_type

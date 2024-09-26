#  -*- coding: utf-8 -*-
#
# This file is part of the SKA SER SNMP project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This package implements SKA SER SNMP subsystem.
"""

__version__ = "0.3.1"
__version_info__ = (
    "ska-ser-snmp",
    "0.3.1",
    "This package implements SKA SER SNMP subsystem.",
)

__all__ = [
    # devices
    "AttributePollingDevice",
    "SNMPDevice",
    "SNMPAttrInfo",
    "attr_args_from_snmp_type",
    # device subpackages
    "ska_attribute_polling",
    "ska_snmp_device",
]

from .ska_attribute_polling import AttributePollingDevice
from .ska_snmp_device import SNMPDevice, SNMPAttrInfo, attr_args_from_snmp_type

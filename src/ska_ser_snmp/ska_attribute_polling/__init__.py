#  -*- coding: utf-8 -*-
#
# This file is part of the SKA SER SNMP project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Module for ska_attribute_polling."""

__version__ = "0.3.1"

__all__ = [
    "AttributePollingDevice",
    "AttributePollingComponentManager"
]

from .attribute_polling_device import AttributePollingDevice
from .attribute_polling_component_manager import AttributePollingComponentManager

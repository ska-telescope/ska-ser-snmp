#  -*- coding: utf-8 -*-
#
# This file is part of the SKA SER SNMP project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements a generic snmp device."""
from __future__ import annotations

from tango.server import device_property

from ska_ser_snmp.ska_attribute_polling.attribute_polling_device import AttributePollingDevice
from ska_ser_snmp.ska_snmp_device.definitions import load_device_definition, parse_device_definition
from ska_ser_snmp.ska_snmp_device.snmp_component_manager import SNMPComponentManager


class SNMPDevice(AttributePollingDevice):
    """An implementation of a generic snmp Tango device."""

    DeviceDefinition = device_property(dtype=str, mandatory=True)
    Host = device_property(dtype=str, mandatory=True)
    Port = device_property(dtype=int, default_value=161)
    V2Community = device_property(dtype=str)
    V3UserName = device_property(dtype=str)
    V3AuthKey = device_property(dtype=str)
    V3PrivKey = device_property(dtype=str)
    MaxObjectsPerSNMPCmd = device_property(dtype=int, default_value=24)

    def create_component_manager(self: SNMPDevice) -> SNMPComponentManager:
        """
        Create and return a component manager. Called during init_device().

        :returns: tne component manager
        """
        # This goes here because you don't have access to properties
        # until tango.server.BaseDevice.init_device() has been called
        dynamic_attrs = parse_device_definition(
            load_device_definition(self.DeviceDefinition)
        )

        self._dynamic_attrs = {attr.name: attr for attr in dynamic_attrs}

        assert (self.V2Community and not self.V3UserName) or (
            not self.V2Community and self.V3UserName
        ), "Can't be V2 & V3 simultaneously"

        if self.V2Community:
            authority = self.V2Community
        else:
            authority = {
                "auth": self.V3UserName,
                "authKey": self.V3AuthKey,
                "privKey": self.V3PrivKey,
            }

        return SNMPComponentManager(
            host=self.Host,
            port=self.Port,
            authority=authority,
            max_objects_per_pdu=self.MaxObjectsPerSNMPCmd,
            logger=self.logger,
            communication_state_callback=self._communication_state_changed,
            component_state_callback=self._component_state_changed,
            attributes=dynamic_attrs,
            poll_rate=self.UpdateRate,
        )


# ----------
# Run server
# ----------
def main(*args: str, **kwargs: str) -> int:  # pragma: no cover
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return SNMPDevice.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()

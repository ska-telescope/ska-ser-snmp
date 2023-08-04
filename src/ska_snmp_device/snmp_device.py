from tango.server import device_property

from ska_low_itf_devices.attribute_polling_device import AttributePollingDevice
from ska_snmp_device.definitions import load_device_definition, parse_device_definition
from ska_snmp_device.snmp_component_manager import SNMPComponentManager


class SNMPDevice(AttributePollingDevice):
    DeviceDefinition = device_property(dtype=str, mandatory=True)
    Host = device_property(dtype=str, mandatory=True)
    Port = device_property(dtype=int, default_value=161)
    V2Community = device_property(dtype=str)
    V3UserName = device_property(dtype=str)
    V3AuthKey = device_property(dtype=str)
    V3PrivKey = device_property(dtype=str)
    MaxObjectsPerSNMPCmd = device_property(dtype=int, default_value=24)

    def create_component_manager(self) -> SNMPComponentManager:
        """Create and return a component manager. Called during init_device()."""
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

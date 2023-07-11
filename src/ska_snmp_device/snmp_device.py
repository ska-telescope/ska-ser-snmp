from typing import Any

from ska_control_model import CommunicationStatus, PowerState
from ska_tango_base import SKABaseDevice
from tango import AttReqType, Attribute, AttrQuality, WAttribute
from tango.server import attribute, device_property

from ska_snmp_device.definitions import load_device_definition, parse_device_definition
from ska_snmp_device.snmp_component_manager import SNMPComponentManager
from ska_snmp_device.types import SNMPAttrInfo


class SNMPDevice(SKABaseDevice[SNMPComponentManager]):
    DeviceDefinition = device_property(dtype=str, mandatory=True)
    Host = device_property(dtype=str, mandatory=True)
    Port = device_property(dtype=int, default_value=161)
    V2Community = device_property(dtype=str)
    V3UserName = device_property(dtype=str)
    V3AuthKey = device_property(dtype=str)
    V3PrivKey = device_property(dtype=str)
    UpdateRate = device_property(dtype=float, default_value=2.0)
    MaxObjectsPerSNMPCmd = device_property(dtype=int, default_value=24)

    def create_component_manager(self) -> SNMPComponentManager:
        """Create and return a component manager. Called during init_device()."""
        # This goes here because you don't have access to properties
        # until tango.server.BaseDevice.init_device() has been called
        dynamic_attrs = parse_device_definition(
            load_device_definition(self.DeviceDefinition)
        )

        # pylint: disable-next=attribute-defined-outside-init
        self._dynamic_attrs: dict[str, SNMPAttrInfo] = {
            attr.name: attr for attr in dynamic_attrs
        }

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
            snmp_attributes=dynamic_attrs,
            poll_rate=self.UpdateRate,
        )

    def initialize_dynamic_attributes(self) -> None:
        """Do what the name says. Called by Tango during init_device()."""
        for name, attr_info in self._dynamic_attrs.items():
            attr = attribute(
                fget=self._dynamic_get,
                fset=self._dynamic_set,
                fisallowed=self._dynamic_is_allowed,
                **attr_info.attr_args,
            )
            self.add_attribute(attr)

            # Allow clients to subscribe to changes for this property
            self.set_change_event(name, True)
            self.set_archive_event(name, True)

    def _dynamic_is_allowed(self, attr_req_type: AttReqType) -> bool:
        # pylint: disable=unused-argument
        return (
            self.component_manager.communication_state
            == CommunicationStatus.ESTABLISHED
        )

    def _dynamic_get(self, attr: Attribute) -> None:
        # pylint: disable=protected-access
        val = self.component_manager._component_state[attr.get_name()]
        if val is None:
            attr.set_quality(AttrQuality.ATTR_INVALID)
        else:
            attr.set_quality(AttrQuality.ATTR_VALID)
            attr.set_value(val)

    def _dynamic_set(self, attr: WAttribute) -> None:
        value = attr.get_write_value()
        attr_name = attr.get_name()
        self.component_manager.enqueue_write(attr_name, value)

    def _component_state_changed(
        self,
        fault: bool | None = None,
        power: PowerState | None = None,
        **kwargs: dict[str, Any],
    ) -> None:
        super()._component_state_changed(fault=fault, power=power)
        for name, value in kwargs.items():
            self.push_change_event(name, value)
            self.push_archive_event(name, value)

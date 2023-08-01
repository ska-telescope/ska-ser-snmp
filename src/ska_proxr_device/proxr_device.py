import tango
from tango.server import device_property

from ska_low_itf_devices.attribute_polling_component_manager import AttrInfo
from ska_low_itf_devices.attribute_polling_device import AttributePollingDevice
from ska_proxr_device.proxr_component_manager import ProXRComponentManager


class ProXRDevice(AttributePollingDevice):
    NumberOfRelays = device_property(dtype=int, default_value=8)
    Host = device_property(dtype=str, mandatory=True)
    Port = device_property(dtype=int, default_value=161)
    UpdateRate = device_property(dtype=float, default_value=2.0)

    def create_component_manager(self) -> ProXRComponentManager:
        """Create and return a component manager. Called during init_device()."""
        # This goes here because you don't have access to properties
        # until tango.server.BaseDevice.init_device() has been
        dynamic_attrs = [
            AttrInfo(
                polling_period=self.UpdateRate,
                attr_args={
                    "name": f"Relay{i}",
                    "dtype": bool,
                    "access": tango.AttrWriteType.READ_WRITE,
                },
            )
            for i in range(1, self.NumberOfRelays + 1)
        ]
        self._dynamic_attrs = {attr.name: attr for attr in dynamic_attrs}

        return ProXRComponentManager(
            host=self.Host,
            port=self.Port,
            logger=self.logger,
            communication_state_callback=self._communication_state_changed,
            component_state_callback=self._component_state_changed,
            attributes=dynamic_attrs,
            poll_rate=self.UpdateRate,
        )

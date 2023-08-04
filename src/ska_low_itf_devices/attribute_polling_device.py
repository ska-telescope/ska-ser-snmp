from typing import Any

from ska_control_model import CommunicationStatus, PowerState
from ska_tango_base import SKABaseDevice
from tango import AttReqType, Attribute, AttrQuality, WAttribute
from tango.server import attribute, device_property

from .attribute_polling_component_manager import (
    AttributePollingComponentManager,
    AttrInfo,
)


class AttributePollingDevice(SKABaseDevice[AttributePollingComponentManager]):
    _dynamic_attrs: dict[str, AttrInfo] = {}

    UpdateRate = device_property(dtype=float, default_value=2.0)

    def create_component_manager(self) -> AttributePollingComponentManager:
        """
        Create and return a component manager. Called during init_device().

        You should set _dynamic_attrs in here - they'll be initialised later
        in initialise_dynamic_attributes().

        FIXME: that's pretty janky
        """
        raise NotImplementedError()

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

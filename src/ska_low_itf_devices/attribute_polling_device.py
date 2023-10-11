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

    component_manager: AttributePollingComponentManager

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
        val, tstamp = self.component_manager.get_attr_value_time(attr.get_name())
        if val is None:
            attr.set_quality(AttrQuality.ATTR_INVALID)
        else:
            if tstamp == float("-inf"):
                self.logger.warning(
                    "Attribute %s set without timestamp", attr.get_name()
                )
                attr.set_value(val)
            else:
                attr.set_value_date_quality(val, tstamp, AttrQuality.ATTR_VALID)

    def _dynamic_set(self, attr: WAttribute) -> None:
        value = attr.get_write_value()
        attr_name = attr.get_name()
        self.component_manager.enqueue_write(attr_name, value)

    def _component_state_changed(
        self,
        fault: bool | None = None,
        power: PowerState | None = None,
        **kwargs: Any,
    ) -> None:
        super()._component_state_changed(fault=fault, power=power)
        for name, value in kwargs.items():
            val, tstamp = self.component_manager.get_attr_value_time(name)
            assert (
                val == value
            ), "value passed to _component_state_changed and current component state do not agree"
            self.push_change_event(name, value, tstamp, AttrQuality.ATTR_VALID)
            self.push_archive_event(name, value, tstamp, AttrQuality.ATTR_VALID)

    def push_change_event(self, *args: Any, **kwargs: Any) -> None:
        """
        Push a device server change event.

        Overridden from SKABaseDevice to support extra args, specifically date.

        :param args: positional arguments to be passed to push_change_event
        :param kwargs: keyword arguments to be passed to push_change_event
        """
        self._submit_tango_operation("push_change_event", *args, **kwargs)

    def push_archive_event(self, *args: Any, **kwargs: Any) -> None:
        """
        Push a device server archive event.

        Overridden from SKABaseDevice to support extra args, specifically date.

        :param args: positional arguments to be passed to push_archive_event
        :param kwargs: keyword arguments to be passed to push_archive_event
        """
        self._submit_tango_operation("push_archive_event", *args, **kwargs)

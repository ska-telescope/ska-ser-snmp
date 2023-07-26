import logging
import queue
import time
from contextlib import contextmanager
from queue import SimpleQueue
from typing import Any, Generator

import numpy as np
import tango
from ska_control_model import AdminMode
from tango import DeviceProxy, DevState, EventData, EventType
from tango.server import device_property
from tango.test_context import DeviceTestContext

from ska_low_itf_devices.attribute_polling_device import AttributePollingDevice
from ska_proxr_device.proxr_component_manager import (
    ProXRAttrInfo,
    ProXRComponentManager,
)


class ProXRDevice(AttributePollingDevice):
    NumberOfRelays = device_property(dtype=int, default_value=8)
    Host = device_property(dtype=str, mandatory=True)
    Port = device_property(dtype=int, default_value=161)
    UpdateRate = device_property(dtype=float, default_value=2.0)

    def create_component_manager(self) -> ProXRComponentManager:
        """Create and return a component manager. Called during init_device()."""
        # This goes here because you don't have access to properties
        # until tango.server.BaseDevice.init_device() has been called
        dynamic_attrs = [
            ProXRAttrInfo(
                polling_period=self.UpdateRate,
                attr_args={
                    "name": "R" + str(i + 1),
                    "dtype": bool,
                    "access": tango.AttrWriteType.READ_WRITE,
                },
            )
            for i in range(self.NumberOfRelays)
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


def expect_attribute(
    tango_device: DeviceProxy,
    attr: str,
    value: Any,
    *,
    timeout: float = 10.0,
) -> bool:
    """
    Wait for Tango attribute to have a certain value using a subscription.

    Sets up a subscription to a Tango device attribute,
    waits for the attribute to have the provided value within a given time,
    then removes the subscription.

    :param tango_device: a DeviceProxy to a Tango device
    :param attr: the name of the attribute to be monitored
    :param value: the attribute value we're waiting for
    :param timeout: the maximum time to wait, in seconds
    :return: True if the attribute has the expected value within the given timeout
    """
    logging.debug(
        f"Expecting {tango_device.dev_name()}/{attr} == {value!r} within {timeout}s"
    )
    _queue: SimpleQueue[EventData] = SimpleQueue()
    subscription_id = tango_device.subscribe_event(
        attr,
        EventType.CHANGE_EVENT,
        _queue.put,
    )
    deadline = time.time() + timeout
    current_value = object()
    try:
        while True:
            event = _queue.get(timeout=deadline - time.time())
            current_value = event.attr_value.value
            if event.err:
                logging.debug(
                    f"Got {tango_device.dev_name()}/{attr} error {event.errors}"
                )
            else:
                logging.debug(
                    f"Got {tango_device.dev_name()}/{attr} == {current_value!r}"
                )
                if isinstance(current_value, np.ndarray):
                    # np.ndarray will raise if you compare it directly to a list/tuple
                    if type(value)(current_value) == value:
                        return True
                elif current_value == value:
                    return True
    except queue.Empty:
        raise TimeoutError(
            f"{tango_device.dev_name()}/{attr} was not {value!r} within {timeout}s, last value was {current_value}"
        )
    finally:
        tango_device.unsubscribe_event(subscription_id)


def device():
    ctx = DeviceTestContext(
        ProXRDevice,
        properties=dict(
            NumberOfRelays=8,
            Host="localhost",
            Port=5025,
            LoggingLevelDefault=5,
            UpdateRate=0.5,
        ),
    )
    return ctx


def main():
    pass


if __name__ == "__main__":
    main()
    ctx = device()
    with ctx as proxr_device:
        proxr_device.adminMode = AdminMode.ONLINE
        expect_attribute(proxr_device, "State", DevState.ON)
        proxr_device.R1 = True
        expect_attribute(proxr_device, "R1", True)
        proxr_device.R1 = False
        expect_attribute(proxr_device, "R1", False)
        proxr_device.R5 = True
        expect_attribute(proxr_device, "R5", True)
        proxr_device.R5 = False
        expect_attribute(proxr_device, "R5", False)

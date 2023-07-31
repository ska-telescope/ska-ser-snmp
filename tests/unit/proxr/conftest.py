import logging
import os
import queue
import threading
import time
from queue import SimpleQueue
from typing import Any

import numpy as np
import pytest
from ska_control_model import AdminMode
from tango import DeviceProxy, DevState, EventData, EventType
from tango.test_context import DeviceTestContext

from ska_proxr_device.proxr_device import ProXRDevice
from ska_proxr_device.proxr_server import ProXRServer
from ska_proxr_device.proxr_simulator import ProXRSimulator


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


@pytest.fixture(scope="session")
def simulator():
    if os.getenv("SKA_PROXR_DEVICE_SIMULATOR", "1").strip():
        sim = ProXRSimulator()
        server = ProXRServer(sim.receive_send, ("localhost", 0))
        with server:
            server_thread = threading.Thread(
                name="ProXR relay simulator thread",
                target=server.serve_forever,
            )
            try:
                server_thread.start()
                yield server.server_address
            finally:
                server.shutdown()

    else:
        yield None


@pytest.fixture
def endpoint(simulator: tuple[str, int]) -> tuple[str, int]:
    if simulator:
        return simulator
    else:
        host, port = os.getenv("SKA_PROXR_DEVICE_TEST_ENDPOINT").strip().split(":")
        return host, int(port)


@pytest.fixture
def proxr_device(endpoint: tuple[str, int], number_of_relays: int) -> DeviceProxy:
    host, port = endpoint
    ctx = DeviceTestContext(
        ProXRDevice,
        properties=dict(
            NumberOfRelays=number_of_relays,
            Host=host,
            Port=port,
            LoggingLevelDefault=5,
            UpdateRate=0.5,
        ),
    )
    with ctx as dev:
        dev.adminMode = AdminMode.ONLINE
        expect_attribute(dev, "State", DevState.ON)
        assert dev.State() == DevState.ON
        yield dev
        dev.adminMode = AdminMode.OFFLINE
        expect_attribute(dev, "State", DevState.DISABLE)
        assert dev.State() == DevState.DISABLE


@pytest.fixture
def number_of_relays() -> int:
    return 8

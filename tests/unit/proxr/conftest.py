import logging
import os
import queue
import signal
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from queue import SimpleQueue
from typing import Any, Generator

import numpy as np
import pytest
from ska_control_model import AdminMode
from tango import DeviceProxy, DevState, EventData, EventType
from tango.test_context import DeviceTestContext

from ska_proxr_device.proxr_device import ProXRDevice
from ska_snmp_device.snmp_device import SNMPDevice


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
    yield None
    # if os.getenv("SKA_SNMP_DEVICE_SIMULATOR", "1").strip():
    #     sim_user = os.getenv("SKA_SNMP_DEVICE_SIMULATOR_USER", "").strip()
    #     if sim_user:
    #         user, group = sim_user.split(":")
    #         user_args = [f"--process-user={user}", f"--process-group={group}"]
    #     else:
    #         user_args = []
    #     host, port = "127.0.0.1", 5161
    #     sim_process: Any = subprocess.Popen(  # Any because mypy seems to hate Popen
    #         [
    #             "snmpsim-command-responder",
    #             *user_args,
    #             "--data-dir=tests/snmpsim_data",
    #             "--variation-module-options=sql:dbtype:sqlite3,database:tests/snmpsim_data/snmpsim.db,dbtable:snmprec",
    #             f"--agent-udpv4-endpoint={host}:{port}",
    #         ],
    #         encoding="utf-8",
    #         stderr=subprocess.PIPE,
    #     )
    #     try:
    #         while sim_process.poll() is None:
    #             line = sim_process.stderr.readline()
    #             if line.startswith(f"  Listening at UDP/IPv4 endpoint {host}:{port}"):
    #                 yield host, port
    #                 break
    #         else:
    #             cmd = " ".join(sim_process.args)
    #             return_code = sim_process.returncode
    #             raise RuntimeError(
    #                 f'Simulator command "{cmd}" exited with code {return_code} without ever listening'
    #             )
    #     finally:
    #         sim_process.send_signal(signal.SIGTERM)
    #         sim_process.wait()
    # else:
    #     yield None


@pytest.fixture
def endpoint(simulator: tuple[str, int]) -> tuple[str, int]:
    if simulator:
        return simulator
    else:
        host, port = os.getenv("SKA_PROXR_DEVICE_TEST_ENDPOINT").strip().split(":")
        return host, int(port)


@pytest.fixture
def proxr_context(endpoint: tuple[str, int]):
    host, port = endpoint
    ctx = DeviceTestContext(
        ProXRDevice,
        properties=dict(
            NumberOfRelays=8,
            Host=host,
            Port=port,
            LoggingLevelDefault=5,
            UpdateRate=0.5,
        ),
    )
    return ctx
    # with ctx as dev:
    #     dev.adminMode = AdminMode.ONLINE
    #     expect_attribute(dev, "State", DevState.ON)
    #     assert dev.State() == DevState.ON
    #     yield dev
    #     dev.adminMode = AdminMode.OFFLINE
    #     expect_attribute(dev, "State", DevState.DISABLE)
    #     assert dev.State() == DevState.DISABLE

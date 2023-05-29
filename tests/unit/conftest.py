import os
import queue
import signal
import time
from contextlib import contextmanager
from pathlib import Path
from queue import SimpleQueue
from subprocess import Popen
from typing import Any, Generator

import numpy as np
import pytest
from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi import CommunityData, ContextData, UdpTransportTarget, getCmd
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType
from ska_control_model import AdminMode
from tango import DeviceProxy, DevState, EventData, EventType
from tango.test_context import DeviceTestContext

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
    print(f"Expecting {tango_device.dev_name()}/{attr} == {value!r} within {timeout}s")
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
                print(f"Got {tango_device.dev_name()}/{attr} error {event.errors}")
            else:
                print(f"Got {tango_device.dev_name()}/{attr} == {current_value!r}")
                if isinstance(current_value, np.ndarray):
                    # an ndarray will raise if you compare it directly to a list
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
    if os.getenv("SKA_SNMP_DEVICE_SIMULATOR", True):
        sim_user = os.getenv("SKA_SNMP_DEVICE_SIMULATOR_USER")
        if sim_user:
            user, group = sim_user.split(":")
            user_args = f"--process-user {user} --process-group {group} "
        else:
            user_args = ""
        host, port = "127.0.0.1", 5161
        sim_process = Popen(
            f"snmpsim-command-responder {user_args}"
            "--data-dir resources/snmpsim_data "
            f"--agent-udpv4-endpoint={host}:{port} "
            "--variation-module-options=sql:dbtype:sqlite3,database:tests/snmpsim.db,dbtable:snmprec",
            shell=True,
        )

        # Wait until the server's active. Is there a better way?
        try:
            iterator = getCmd(
                SnmpEngine(),
                CommunityData("private"),
                UdpTransportTarget((host, port), retries=10, timeout=0.5),
                ContextData(),
                ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)),
            )
            for error_indication, _, _, result in iterator:
                if error_indication:
                    raise error_indication
            yield host, port
        finally:
            sim_process.send_signal(signal.SIGTERM)
            sim_process.wait()
    else:
        yield None


@contextmanager
def restore(
    dev: DeviceProxy, attr: str, setval: Any = object
) -> Generator[Any, None, None]:
    old_val = getattr(dev, attr)
    yield old_val
    setattr(dev, attr, old_val if setval is object else setval)
    expect_attribute(dev, attr, old_val, timeout=15)


@pytest.fixture
def definition_path():
    return Path(__file__).parent.resolve() / "SKA-7357.yaml"


@pytest.fixture
def endpoint(simulator: tuple[str, int]) -> tuple[str, int]:
    if simulator:
        return simulator
    else:
        host, port = os.getenv("SKA_SNMP_DEVICE_TEST_ENDPOINT").split(":")
        return host, int(port)


@pytest.fixture
def snmp_device(definition_path: str, endpoint: tuple[str, int]) -> DeviceProxy:
    host, port = endpoint
    ctx = DeviceTestContext(
        SNMPDevice,
        properties=dict(
            DeviceDefinition=definition_path,
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

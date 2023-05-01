import queue
import random
import string
import time
from enum import Enum
from queue import SimpleQueue

import pytest
from more_itertools import iter_except, partition
from tango import DevFailed, EventData, EventType

from .conftest import expect_attribute, restore


def test_int(snmp_device):
    with restore(snmp_device, "writeableInt"):
        snmp_device.writeableInt = 5
        expect_attribute(snmp_device, "writeableInt", 5)
        snmp_device.writeableInt = 10
        expect_attribute(snmp_device, "writeableInt", 10)


def test_bits(snmp_device, endpoint):
    host, _ = endpoint
    # Hack for EN6808-specific behaviour, where you can't
    # write [], so you set the 4 bit to clear all the others
    if host == "127.0.0.1":
        setval = object
    else:
        setval = [4]
    with restore(snmp_device, "bitEnum", setval=setval):
        snmp_device.bitEnum = [0]
        expect_attribute(snmp_device, "bitEnum", [0])

        val = snmp_device.bitEnum
        assert all(isinstance(v, Enum) for v in val)

        snmp_device.bitEnum = [1, 3]
        expect_attribute(snmp_device, "bitEnum", [1, 3])


def test_string(snmp_device):
    with restore(snmp_device, "writeableString"):
        name = "test-" + "".join(random.choices(string.ascii_letters, k=4))
        snmp_device.writeableString = name
        expect_attribute(snmp_device, "writeableString", name)


def test_enum(snmp_device):
    with restore(snmp_device, "writeableEnum") as current:
        assert isinstance(current, Enum)
        dtype = type(current)
        snmp_device.writeableEnum = dtype.on  # noqa
        expect_attribute(snmp_device, "writeableEnum", 1)
        snmp_device.writeableEnum = dtype.lastKnownState  # noqa
        expect_attribute(snmp_device, "writeableEnum", 2)


def test_enum_invalid(snmp_device):
    with pytest.raises(DevFailed, match="ValueError: Enum value 0"):
        snmp_device.enumWithInvalid = 0


def test_constrained_int(snmp_device):
    with pytest.raises(DevFailed, match="above the maximum"):
        snmp_device.writeableConstrainedInt = 3601
    attr_config = snmp_device.get_attribute_config("writeableConstrainedInt")
    assert attr_config.min_value == "0"
    assert attr_config.max_value == "3600"


def test_polling_period(snmp_device):
    pytest.skip("Doesn't work against simulator")
    _queue: SimpleQueue[EventData] = SimpleQueue()

    slow_id = snmp_device.subscribe_event(
        "slowPoller",
        EventType.CHANGE_EVENT,
        _queue.put,
    )
    fast_id = snmp_device.subscribe_event(
        "fastPoller",
        EventType.CHANGE_EVENT,
        _queue.put,
    )
    time.sleep(10)
    snmp_device.unsubscribe_event(slow_id)
    snmp_device.unsubscribe_event(fast_id)

    # drain the captured events into two buckets
    slow_events, fast_events = partition(
        # for some reason, sometimes the attribute name is differently-cased
        lambda ev: ev.attr_value.name.lower() == "fastpoller",
        iter_except(_queue.get_nowait, queue.Empty),
    )
    slow_events, fast_events = list(slow_events), list(fast_events)

    # This could fail if the SNMP agent is verrrryy slow
    assert len(fast_events) >= 7
    assert len(slow_events) <= 2

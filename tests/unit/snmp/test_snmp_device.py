import queue
import random
import string
import time
from enum import Enum
from itertools import islice
from queue import SimpleQueue

import pytest
from more_itertools import iter_except, partition
from tango import DevFailed, EventData, EventType

from ska_snmp_device.types import _SNMP_ENUM_INVALID_PREFIX

from .conftest import expect_attribute, restore


def test_int(snmp_device):
    with restore(snmp_device, "writeableInt"):
        snmp_device.writeableInt = 5
        expect_attribute(snmp_device, "writeableInt", 5)
        snmp_device.writeableInt = 10
        expect_attribute(snmp_device, "writeableInt", 10)


def test_bits(snmp_device, simulator):
    # Hack for EN6808-specific behaviour, where you can't
    # write [], so you set the 4 bit to clear all the others
    setval = object if simulator else [4]

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
        snmp_device.writeableEnum = dtype(1)
        expect_attribute(snmp_device, "writeableEnum", 1)
        snmp_device.writeableEnum = dtype(2)
        expect_attribute(snmp_device, "writeableEnum", 2)
        assert snmp_device.writeableEnum.name == "lastKnownState"


def test_enum_invalid(snmp_device):
    with pytest.raises(DevFailed, match="ValueError: Enum value 0"):
        snmp_device.writeableEnumWithInvalid = 0


def test_enum_nonsequential(snmp_device):
    dtype = type(snmp_device.nonSequentialEnum)
    expected = {
        1: "temperature",
        2: "humidity",
        3: "doorSwitch",
        4: "dryContact",
        5: "spotFluid",
        6: "ropeFluid",
        7: "smoke",
        8: "beacon",
        9: "airVelocity",
        17: "modbusAdapter",
        18: "hidAdapter",
        19: "eHandleAdapter",
        25: "assetmodule",
    }
    for entry in dtype:
        if entry.value in expected:
            assert entry.name == expected[entry.value]
        else:
            assert entry.name == _SNMP_ENUM_INVALID_PREFIX + str(entry.value)


def test_constrained_int(snmp_device):
    attr_config = snmp_device.get_attribute_config("writeableConstrainedInt")
    assert attr_config.min_value == "0"
    assert attr_config.max_value == "3600"
    with pytest.raises(DevFailed, match="above the maximum"):
        snmp_device.writeableConstrainedInt = 3601


def test_polling_period(snmp_device):
    event_queue: SimpleQueue[EventData] = SimpleQueue()

    slow_id = snmp_device.subscribe_event(
        "slowPoller",
        EventType.CHANGE_EVENT,
        event_queue.put,
    )
    fast_id = snmp_device.subscribe_event(
        "fastPoller",
        EventType.CHANGE_EVENT,
        event_queue.put,
    )

    # capture ten events into fast and slow buckets
    slow_events, fast_events = [
        list(events)
        for events in partition(
            # for some reason, sometimes the attribute name is differently-cased
            lambda ev: ev.attr_value.name.lower() == "fastpoller",
            islice(iter_except(event_queue.get, queue.Empty), 10),
        )
    ]

    snmp_device.unsubscribe_event(slow_id)
    snmp_device.unsubscribe_event(fast_id)

    assert len(fast_events) >= 7
    assert len(slow_events) <= 3


def test_attribute_timestamps(snmp_device):
    event_queue: SimpleQueue[EventData] = SimpleQueue()
    fast_id = snmp_device.subscribe_event(
        "fastPoller",
        EventType.CHANGE_EVENT,
        event_queue.put,
    )

    for ev in islice(iter_except(event_queue.get, queue.Empty), 1, 5):
        timestamps = {
            snmp_device.read_attribute(attr).time.totime()
            for attr in ["writeableInt", "writeableString", "nonSequentialEnum"]
        }
        ev_time = ev.attr_value.time.totime()
        assert list(timestamps) == [ev_time]

    snmp_device.unsubscribe_event(fast_id)

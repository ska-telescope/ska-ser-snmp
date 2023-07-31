import queue
import random
import string
from enum import Enum
from itertools import islice
from queue import SimpleQueue

import pytest
from more_itertools import iter_except, partition
from ska_control_model import AdminMode
from tango import DevFailed, DevState, EventData, EventType

from .conftest import expect_attribute


def test_switching(proxr_context):
    with proxr_context as proxr_device:
        proxr_device.adminMode = AdminMode.ONLINE
        expect_attribute(proxr_device, "State", DevState.ON)
        assert proxr_device.State() == DevState.ON
        proxr_device.R1 = True
        expect_attribute(proxr_device, "R1", True)
        proxr_device.R1 = False
        expect_attribute(proxr_device, "R1", False)
        proxr_device.R5 = True
        expect_attribute(proxr_device, "R5", True)
        proxr_device.R5 = False
        expect_attribute(proxr_device, "R5", False)
        proxr_device.adminMode = AdminMode.OFFLINE
        expect_attribute(proxr_device, "State", DevState.DISABLE)
        assert proxr_device.State() == DevState.DISABLE

import logging
import time
from typing import Any

import pytest
from ska_control_model import CommunicationStatus

from ska_snmp_device.snmp_component_manager import SNMPComponentManager
from ska_snmp_device.types import SNMPAttrInfo


@pytest.fixture
def component_manager(endpoint):
    def comm_state_changed(comm_state: CommunicationStatus) -> None:
        pass

    def component_state_changed(state_updates: dict[str, Any]) -> None:
        pass

    host, port = endpoint

    return SNMPComponentManager(
        host=host,
        port=port,
        authority="public",
        logger=logging.getLogger(),
        communication_state_callback=comm_state_changed,
        component_state_callback=component_state_changed,
        attributes=[
            SNMPAttrInfo(
                attr_args=dict(
                    name="fast",
                    dtype=int,
                ),
                polling_period=0.5,
                identity=("MIB", "tastic", 1),
            ),
            SNMPAttrInfo(
                attr_args=dict(
                    name="slow",
                    dtype=int,
                ),
                polling_period=1.0,
                identity=("MIB", "tastic", 2),
            ),
        ],
        poll_rate=2.0,
        max_objects_per_pdu=24,
    )


def test_component_manager_polling_periods(component_manager):
    mgr = component_manager
    assert all(t == float("-inf") for t in mgr._last_polled.values())

    def time_travel(d: float) -> None:
        mgr._last_polled.update((k, v - d) for k, v in mgr._last_polled.items())

    attrs_to_poll = set(mgr.get_request().reads)
    assert attrs_to_poll == {"slow", "fast"}

    now = time.time()
    mgr._last_polled.update({"slow": now, "fast": now})

    time_travel(0.25)
    assert not mgr.get_request().reads

    time_travel(0.5)
    to_poll = set(mgr.get_request().reads)
    assert to_poll == {"fast"}

    time_travel(0.5)
    to_poll = set(mgr.get_request().reads)
    assert to_poll == {"slow", "fast"}

    mgr._last_polled["fast"] = time.time()
    to_poll = set(mgr.get_request().reads)
    assert to_poll == {"slow"}

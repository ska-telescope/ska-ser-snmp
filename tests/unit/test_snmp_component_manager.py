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
        community="public",
        logger=logging.getLogger(),
        communication_state_callback=comm_state_changed,
        component_state_callback=component_state_changed,
        snmp_attributes=[
            SNMPAttrInfo(
                "fast",
                ("MIB", "tastic", 1),
                attr_args={},
                polling_period=0.5,
                dtype=int,
            ),
            SNMPAttrInfo(
                "slow",
                ("MIB", "tastic", 2),
                attr_args={},
                polling_period=1.0,
                dtype=int,
            ),
        ],
        poll_rate=2.0,
        max_objects_per_pdu=24,
    )


def test_component_manager_polling_periods(component_manager):
    mgr = component_manager
    assert all(t == float("-inf") for t in mgr._last_polled.values())

    def oid_for_object(o: Any) -> Any:
        identity, _ = o._ObjectType__args
        return identity._ObjectIdentity__args

    def time_travel(d: float) -> None:
        mgr._last_polled.update((k, v - d) for k, v in mgr._last_polled.items())

    fast_oid = ("MIB", "tastic", 1)
    slow_oid = ("MIB", "tastic", 2)

    to_poll = {oid_for_object(o) for o in component_manager.get_request()}
    assert to_poll == {slow_oid, fast_oid}

    now = time.time()
    mgr._last_polled.update({slow_oid: now, fast_oid: now})

    time_travel(0.25)
    assert not component_manager.get_request()

    time_travel(0.5)
    to_poll = {oid_for_object(o) for o in component_manager.get_request()}
    assert to_poll == {fast_oid}

    time_travel(0.5)
    to_poll = {oid_for_object(o) for o in component_manager.get_request()}
    assert to_poll == {slow_oid, fast_oid}

    mgr._last_polled[fast_oid] = time.time()
    to_poll = {oid_for_object(o) for o in component_manager.get_request()}
    assert to_poll == {slow_oid}

"""
This package provides a generic Tango device class for controlling ProXR devices.
"""

__version__ = "0.0.1"

__all__ = [
    "ProXRDevice",
    "ProXRSimulator",
    "ProXRServer",
    "ProXRClient",
    "ProXRComponentManager",
]

from .proxr_client import ProXRClient
from .proxr_component_manager import ProXRComponentManager
from .proxr_device import ProXRDevice
from .proxr_server import ProXRServer
from .proxr_simulator import ProXRSimulator

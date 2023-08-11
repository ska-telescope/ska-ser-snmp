"""
This package provides a generic Tango device class for controlling ProXR devices.
"""

__version__ = "0.2.0"

__all__ = [
    "ProXRDevice",
    "ProXRComponentManager",
]

from .proxr_component_manager import ProXRComponentManager
from .proxr_device import ProXRDevice

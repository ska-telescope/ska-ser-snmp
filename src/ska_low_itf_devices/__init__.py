"""Main module for ska_low_itf_devices."""

__version__ = "0.1.0"

from typing import Any

import yaml


def load_device_definition(filename: str) -> Any:
    """
    Return the parsed contents of the YAML file at filename.
    """
    with open(filename, encoding="utf-8") as def_file:
        # TODO here would be a good place for some schema validation
        return yaml.safe_load(def_file)

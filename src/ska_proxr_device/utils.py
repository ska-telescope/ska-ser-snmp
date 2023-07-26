from enum import IntEnum


class _StartingHex(IntEnum):
    pass


def prepare_payload(data_packet: list[int]) -> bytes:
    """
    Prepend header bytes and append checksum.

    """
    header = [0xAA, len(data_packet)]
    data_packet = header + data_packet

    checksum = sum(data_packet) & 255
    payload = bytes(data_packet + [checksum])
    return payload


def get_payload_by_command(command: _StartingHex, relay: int, bank: int = 1) -> bytes:
    """
    Return the payload for an input command.
    """
    return prepare_payload([0xFE, relay + command, bank])


def process_read_status(bytes_back: bytes) -> bool:
    """
    Process the bytes packet that is received from the component.

    :param bytes_back: bytes packet from component
    :return: relay state as boolean type
    """
    # The status of the relay is located after the the header
    # 0xAA and byte length 0x01.
    data_packet = list(bytes_back)
    print(f"Processing the following data packet: {data_packet}")
    validate_format(data_packet)

    # Status is the second to last item, just before the
    # checksum
    return bool(data_packet[-2])


def validate_format(data_packet: list[int]) -> None:
    """
    Validate the format of the received data packet from component.

    :param data_packet: received data packet
    :raises ValueError: invalid format
    :return: None
    """
    length_of_packet = len(data_packet)
    calculated_checksum = sum(data_packet[:-1]) & 255  # Exclude checksum in calculation

    header = data_packet[0] == 0xAA
    bytes_length = data_packet[1] == length_of_packet - 3
    checksum = data_packet[-1] == calculated_checksum
    if header and bytes_length and checksum:
        pass
    else:
        raise ValueError("Invalid return bytes packet")

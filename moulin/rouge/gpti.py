# SPDX-License-Identifier: Apache-2.0
# Copyright 2023 EPAM Systems
"""
gpt-image interface/wrapper for rouge image builder
"""

from pprint import pformat
from typing import List, Tuple, BinaryIO, Any
from gpt_image.geometry import Geometry
from gpt_image.table import Table
from gpt_image.partition import Partition
import struct
import logging

log = logging.getLogger(__name__)

DEFAULT_ALIGNMENT = 1 * 1024 * 1024  # 1 MiB


def _div_up(num: int, dem: int) -> int:
    if num % dem:
        return (num // dem) + 1
    return num // dem


def _align(val, align) -> int:
    return _div_up(val, align) * align


def fixup_partition_table(partitions: List[Any], sector_size=512) -> Tuple[List[Any], int]:
    """
    Return fixed partition table so it can be really written to disk.
    Also return total size of partition.
    """
    size_estimate = 0
    for part in partitions:
        size_estimate = size_estimate + part.size
    # size_estimate *= 1.2
    size_estimate = _div_up(size_estimate * 6, 5)

    geometry = Geometry(size_estimate, sector_size)
    table = Table(geometry)
    ret = []
    for part in partitions:
        size = _align(part.size, sector_size)
        table.partitions.add(Partition(
            part.label, size, part.gpt_type,
            part.gpt_guid, DEFAULT_ALIGNMENT // sector_size)
            )
        pe = table.partitions.entries[-1]

        # Workaround for gpt-image: in release 0.9.0 they changed how first LBA
        # is stored. Now we need to read `first_lba_staged` property. Problem
        # is that we don't know which version is installed on the user's
        # machine. So, first we try to read `first_lba_staged` and if it fails
        # - old `first_lba` property.
        first_lba = 0
        try:
            first_lba = pe.first_lba_staged
        except AttributeError:
            first_lba = pe.first_lba

        start = first_lba * sector_size
        ret.append(part._replace(start=start, size=size))
        end = start + size

    log.debug("Partition table: %s", pformat(ret))
    # Account for GPT copy
    return ret, end + 16 * 1024 * 1024


def create_mbr(partitions: List[Any]):
    partition_format = struct.Struct("<B3xB3xII")

    # Bootstrap code area. Hope, no on use it today
    ret = bytes(446)

    # Count partitions
    part_count = len(partitions)
    if part_count > 3:
        log.warn(
            f"There are {part_count} partitions in the partition table, but Hybrid MBR will contain only first 3"
        )

    # Write info about real partitions
    for i in range(min(3, part_count)):
        if partitions[i].protective_mbr_type > 0xFF:
            raise Exception(
                "You must provide mbr_type for all partitions when Hybrd MBR is enabled")
        ret += partition_format.pack(0x80, partitions[i].protective_mbr_type,
                                     partitions[i].start // 512, partitions[i].size // 512)

    # Write protective partition
    ret += partition_format.pack(0x80, 0xEE, 1, (partitions[0].start - 1) // 512)

    # Pad till full sector size
    if part_count < 3:
        ret += bytes(16) * (3 - part_count)

    # Add magic bytes aka boot signature
    ret += b"\x55\xAA"

    return ret


def write(fp: BinaryIO,
          partitions: List[Any],
          offset: int,
          size: int,
          sector_size=512,
          hybrid_mbr=False):
    geometry = Geometry(size, sector_size)
    table = Table(geometry)
    for part in partitions:
        table.partitions.add(
            Partition(part.label, part.size, part.gpt_type, part.gpt_guid,
                      DEFAULT_ALIGNMENT // sector_size))
    table.update()
    fp.seek(offset)

    # Create Protective or Hybryd MBR
    if not hybrid_mbr:
        fp.write(table.protective_mbr.marshal())
    else:
        if sector_size != 512:
            raise Exception(f"It is not possible to use sector size {sector_size} with hybrid MBR")
        fp.write(create_mbr(partitions))

    # write primary header
    fp.seek(offset + geometry.primary_header_byte)
    fp.write(table.primary_header.marshal())
    # write primary partition table
    fp.seek(offset + geometry.primary_array_byte)
    fp.write(table.partitions.marshal())
    # move to secondary header location and write
    fp.seek(offset + geometry.alternate_header_byte)
    fp.write(table.secondary_header.marshal())
    # write secondary partition table
    fp.seek(offset + geometry.alternate_array_byte)
    fp.write(table.partitions.marshal())

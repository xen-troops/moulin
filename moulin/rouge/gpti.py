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
        start = pe.first_lba * sector_size
        ret.append(part._replace(start=start, size=size))
        end = start + size

    log.debug("Partition table: %s", pformat(ret))
    # Account for GPT copy
    return ret, end + 16 * 1024 * 1024


def write(fp: BinaryIO, partitions: List[Any], offset: int, size: int, sector_size=512):
    geometry = Geometry(size, sector_size)
    table = Table(geometry)
    for part in partitions:
        table.partitions.add(Partition(
            part.label, part.size, part.gpt_type,
            part.gpt_guid, DEFAULT_ALIGNMENT // sector_size)
            )
    table.update()
    fp.seek(offset)
    fp.write(table.protective_mbr.marshal())
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

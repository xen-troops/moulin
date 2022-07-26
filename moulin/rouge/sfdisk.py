# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
sfdisk interface/wrapper for rouge image builder
"""

from pprint import pformat
from typing import List, Tuple, BinaryIO, Any
import subprocess
import logging

log = logging.getLogger(__name__)

DEFAULT_ALIGNMENT = 1 * 1024 * 1024  # 1 MiB


def _div_up(num: int, dem: int) -> int:
    if num % dem:
        return (num // dem) + 1
    return num // dem


def _sect(val, sector_size) -> int:
    return _div_up(val, sector_size)


def _align(val, align) -> int:
    return _div_up(val, align) * align


def _to_script(part: Any, sector_size=512) -> str:
    "Convert GPT Partition object to sfdisk script line"

    args = [
        f"start={_sect(part.start, sector_size)}", f"size={_sect(part.size, sector_size)}",
        f"type={part.gpt_type}", f"name={part.label}"
    ]

    if part.gpt_guid:
        args.append(f"uuid={part.gpt_guid}")

    return ", ".join(args)


def _check_sfdisk():
    # We are checking result explicitely
    # pylint: disable=subprocess-run-check
    ret = subprocess.run(["which", "sfdisk"], stdout=subprocess.DEVNULL)
    if ret.returncode != 0:
        raise Exception("Please make sure that 'sfdisk' is installed")


def _sfdisk_header():
    return "\n".join(["label: gpt", "unit: sectors"])


def fixup_partition_table(partitions: List[Any], sector_size=512) -> Tuple[List[Any], int]:
    """
    Return fixed partition table so it can be really written to disk.
    Also return total size of partition.
    """
    start_offset = 0
    if _sect(partitions[0].start, sector_size) < 2048:
        start_offset = 2048
    end = start_offset * sector_size
    ret = []
    for part in partitions:
        start = _align(end, DEFAULT_ALIGNMENT)  # Align to 1 MB
        size = _align(part.size, sector_size)
        ret.append(part._replace(start=start, size=size))
        end = start + size

    log.debug("Partition table: %s", pformat(ret))
    # Account for GPT copy
    return ret, end + 16 * 1024 * 1024


def write(fileo: BinaryIO, partitions: List[Any]):
    "Write partitions to a file"
    _check_sfdisk()

    # Generate sfdisk script file
    script = _sfdisk_header() + "\n"
    script += "\n".join(map(_to_script, partitions))

    log.debug("sfdisk script: %s", script)
    log.info("Creating GPT partition in %s", fileo.name)
    subprocess.run(["sfdisk", fileo.name],
                   input=bytes(script, 'UTF-8'),
                   check=True,
                   stdout=subprocess.DEVNULL)

# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
External utils interfaces/wrappers for rouge image builder
"""

from typing import BinaryIO, Union
import subprocess
import logging

log = logging.getLogger(__name__)


def _run_cmd(args):
    log.info("Running %s", " ".join(args))
    subprocess.run(args, check=True)


# pylint: disable=invalid-name
def dd(file_in: Union[str, BinaryIO], file_out: BinaryIO, out_offset: int):
    "Run dd with the given arguments"
    # Try to guess block size. We would like to use as big block as
    # possible. But we need take into account that "seek" parameter
    # uses block size as the unit.
    blocksize: int = 65536
    while out_offset % blocksize != 0:
        blocksize //= 2

    if isinstance(file_in, str):
        file_in_path = file_in
    else:
        file_in_path = file_in.name
    args = [
        "dd",
        f"if={file_in_path}",
        f"of={file_out.name}",
        f"bs={blocksize}",
        f"seek={out_offset // blocksize}",
        "status=progress",
        "conv=sparse",
        "conv=notrunc",
    ]  # yapf: disable
    _run_cmd(args)


def simg2img(file_in: Union[str, BinaryIO], file_out: BinaryIO):
    "Run simg2img with the given arguments"
    if isinstance(file_in, str):
        file_in_path = file_in
    else:
        file_in_path = file_in.name
    args = [
        "simg2img",
        file_in_path,
        file_out.name,
    ]  # yapf: disable
    _run_cmd(args)


def mkext4fs(file_out: BinaryIO, contents_dir=None):
    "Create ext4 fs in given file"
    args = ["mkfs.ext4", file_out.name]
    if contents_dir:
        args.append("-d")
        args.append(contents_dir)

    _run_cmd(args)


def bmaptool(file: BinaryIO):
    args = ["bmaptool", "create", "-o", file.name + ".bmap", file.name]

    _run_cmd(args)


def mkvfatfs(file_out: BinaryIO):
    "Create ext4 fs in given file"
    args = ["mkfs.vfat", file_out.name]

    _run_cmd(args)


def compress(file: BinaryIO):
    args = ["gzip", "-1kf", file.name]

    _run_cmd(args)


def mcopy(img: BinaryIO, file: str, name: str):
    "Copy a file to a vfat image with a given name"
    args = ["mcopy", "-i", img.name, file, "::" + name]

    _run_cmd(args)

# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Main 'rouge' logic lives there
"""

import os.path
import struct
import shutil
import logging
import itertools
from typing import List, Tuple, NamedTuple, cast
from tempfile import NamedTemporaryFile, TemporaryDirectory

from yaml import Mark
from moulin.rouge import sfdisk, ext_utils
from moulin.yaml_helpers import YAMLProcessingError
from moulin.yaml_wrapper import YamlValue

log = logging.getLogger(__name__)


class BlockEntry():
    "Base class for various block entries"

    # pylint: disable=too-few-public-methods

    def write(self, _file, _offset):
        "write() in base class does nothing"

    def get_deps(self) -> List[str]:  # pylint: disable=no-self-use
        "get_deps() in base class does nothing"
        return []


class GPTPartition(NamedTuple):
    "Represents one partition in GPT"
    label: str
    gpt_type: str
    gpt_guid: str
    start: int
    size: int
    entry: BlockEntry


class GPT(BlockEntry):
    "Represents GUID Partition Table"

    def __init__(self, node: YamlValue):
        self._partitions: List[GPTPartition] = []
        self._size: int = 0

        for part_id, part in node["partitions"].items():
            label = part_id
            entry_obj, gpt_type, gpt_guid = self._process_entry(part)
            self._partitions.append(GPTPartition(label, gpt_type, gpt_guid, start=0, size=0, entry=entry_obj))

    def size(self) -> int:
        "Returns size in bytes"
        if not self._size:
            self._complete_init()
        return self._size

    @staticmethod
    def _process_entry(node: YamlValue):
        entry_obj = construct_entry(node)
        gpt_type = node.get("gpt_type", "").as_str
        if not gpt_type:
            log.warning("No GPT type is provided %s, using default", node.mark)
            gpt_type = "8DA63339-0007-60C0-C436-083AC8230908"

        gpt_guid = node.get("gpt_guid", "").as_str

        return (entry_obj, gpt_type, gpt_guid)

    def _complete_init(self):
        partitions = [x._replace(size=x.entry.size()) for x in self._partitions]
        self._partitions, self._size = sfdisk.fixup_partition_table(partitions)

    def write(self, fp, offset):
        if not self._size:
            self._complete_init()
        if offset == 0:
            sfdisk.write(fp, self._partitions)
        else:
            # Write partition into temporary file, then copy it into
            # resulting file
            with NamedTemporaryFile("wb") as tempf:
                tempf.truncate(self._size)
                sfdisk.write(tempf, self._partitions)
                ext_utils.dd(tempf, fp, offset)

        for part in self._partitions:
            part.entry.write(fp, part.start + offset)

    def get_deps(self) -> List[str]:
        "Return list of dependencies needed to build this block"
        return list(itertools.chain().from_iterable(
            [part.entry.get_deps() for part in self._partitions]))


class RawImage(BlockEntry):
    "Represents raw image file which needs to be copied as is"

    def __init__(self, node: YamlValue):
        self._node = node
        self._fname = self._node["image_path"].as_str
        self._size = 0

    def _complete_init(self):
        mark = self._node["image_path"].mark
        if not os.path.exists(self._fname):
            raise YAMLProcessingError(f"Can't find file '{self._fname}'", mark)
        fsize = os.path.getsize(self._fname)
        size_node = self._node.get("size", None)
        if size_node:
            self._size = _parse_size(size_node)
            if fsize > self._size:
                raise YAMLProcessingError(
                    f"File '{self._fname}' is bigger than partition entry ({self._size})",
                    size_node.mark)
        else:
            self._size = fsize

    def size(self) -> int:
        "Returns size in bytes"
        if not self._size:
            self._complete_init()
        return self._size

    def write(self, fp, offset):
        if not self._size:
            self._complete_init()
        ext_utils.dd(self._fname, fp, offset)

    def get_deps(self) -> List[str]:
        "Return list of dependencies needed to build this block"
        return [self._fname]


class AndroidSparse(BlockEntry):
    "Represents android sparse image file"

    def __init__(self, node: YamlValue):
        self._node = node
        self._fname = self._node["image_path"].as_str
        self._size = 0

    def _read_size(self, mark: Mark):
        # pylint: disable=invalid-name
        FMT = "<IHHHHIIII"
        MAGIC = 0xed26ff3a
        size = struct.calcsize(FMT)
        with open(self._fname, "rb") as data:
            buf = data.read(size)
            if len(buf) < size:
                raise YAMLProcessingError(
                    f"Not enough data for Android sparse header in '{self._fname}'", mark)
            header = struct.unpack(FMT, buf)
            if header[0] != MAGIC:
                raise YAMLProcessingError(f"Invalid Android sparse header in '{self._fname}'", mark)
            # blk_sz * total_blks
            return header[5] * header[6]

    def _complete_init(self):
        mark = self._node["image_path"].mark
        if not os.path.exists(self._fname):
            raise YAMLProcessingError(f"Can't find file '{self._fname}'", mark)
        fsize = self._read_size(mark)
        size_node = self._node.get("size", None)
        if size_node:
            self._size = _parse_size(size_node)
            if fsize > self._size:
                raise YAMLProcessingError(
                    f"Un-sparesd file '{self._fname}' is bigger than partition entry",
                    size_node.mark)
        else:
            self._size = fsize

    def size(self) -> int:
        "Returns size in bytes"
        if not self._size:
            self._complete_init()
        return self._size

    def write(self, fp, offset):
        if not self._size:
            self._complete_init()
        with NamedTemporaryFile("w+b", dir=".") as tmpf:
            ext_utils.simg2img(self._fname, tmpf)
            ext_utils.dd(tmpf, fp, offset)

    def get_deps(self) -> List[str]:
        "Return list of dependencies needed to build this block"
        return [self._fname]


class EmptyEntry(BlockEntry):
    "Represents empty partition"

    def __init__(self, node: YamlValue):
        self._size = _parse_size(node["size"])

    def size(self) -> int:
        "Returns size in bytes"
        return self._size


class FileSystem(BlockEntry):
    "Represents a filesystem with list of files"

    def __init__(self, node: YamlValue):
        self._node = node
        self._size = 0
        self._files: List[Tuple[str, str, Mark]] = []
        files_node = self._node.get("files", None)
        if files_node:
            for remote_node, local_node in cast(YamlValue, files_node).items():
                remote_name = remote_node
                local_name = local_node.as_str
                self._files.append((remote_name, local_name, local_node.mark))

    def _complete_init(self):
        for _, local_name, local_mark in self._files:
            if not os.path.isfile(local_name):
                raise YAMLProcessingError(f"Can't find file '{local_name}'", local_mark)

        files_size = sum([os.path.getsize(x[1]) for x in self._files]) + 8 * 1024 * 1024
        size_node = self._node.get("size", None)
        if size_node:
            self._size = _parse_size(size_node)
            if files_size > self._size:
                raise YAMLProcessingError(
                    f"Computed size is {files_size}, it is bigger than partition size {self._size}",
                    size_node.mark)
        else:
            self._size = files_size

    def size(self) -> int:
        "Returns size in bytes"
        if not self._size:
            self._complete_init()
        return self._size

    def write(self, fp, offset):
        raise NotImplementedError()

    def get_deps(self) -> List[str]:
        "Return list of dependencies needed to build this block"
        return [f[1] for f in self._files]


class Ext4(FileSystem):
    "Represents ext4 fs with list of files"
    def write(self, fp, offset):
        if not self._size:
            self._complete_init()
        with NamedTemporaryFile() as tempf, TemporaryDirectory() as tempd:
            for remote, local, _ in self._files:
                shutil.copyfile(local, os.path.join(tempd, remote))
            tempf.truncate(self._size)
            ext_utils.mkext4fs(tempf, tempd)
            ext_utils.dd(tempf, fp, offset)


class Vfat(FileSystem):
    "Represents vfat fs with list of files"
    def write(self, fp, offset):
        if not self._size:
            self._complete_init()
        with NamedTemporaryFile() as tempf:
            tempf.truncate(self._size)
            ext_utils.mkvfatfs(tempf)
            for remote, local, _ in self._files:
                ext_utils.mcopy(tempf, local, remote)
            ext_utils.dd(tempf, fp, offset)


_ENTRY_TYPES = {
    "gpt": GPT,
    "raw_image": RawImage,
    "ext4": Ext4,
    "vfat": Vfat,
    "empty": EmptyEntry,
    "android_sparse": AndroidSparse,
}


def construct_entry(node: YamlValue) -> BlockEntry:
    "Construct BlockEntry object from YAML node"
    entry_type = node["type"]
    if entry_type.as_str not in _ENTRY_TYPES:
        raise YAMLProcessingError(f"Unknown type '{entry_type.as_str}'", entry_type.mark)

    return _ENTRY_TYPES[entry_type.as_str](node)


_SUFFIXES = {
    "B": 1,
    "KB": 1000,
    "MB": 1000000,
    "GB": 1000000000,
    "TB": 1000000000000,
    "KiB": 1024,
    "MiB": 1024 * 1024,
    "GiB": 1024 * 1024 * 1024,
    "TiB": 1024 * 1024 * 1024 * 1024,
}


def _parse_size(node: YamlValue) -> int:
    components = node.as_str.split(" ")
    if len(components) == 1:
        return int(components[0])
    if len(components) == 2:
        suffix = components[1]
        if suffix not in _SUFFIXES:
            raise YAMLProcessingError(f"Unknown size suffix '{suffix}'", node.mark)
        scaler = _SUFFIXES[suffix]
        return int(components[0]) * scaler
    raise YAMLProcessingError(f"Can't parse size entry '{node.as_str}'", node.mark)

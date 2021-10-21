# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Main 'rouge' logic lives there
"""

import os.path
import struct
import shutil
import logging
from typing import List, Tuple, NamedTuple
from tempfile import NamedTemporaryFile, TemporaryDirectory

from yaml.nodes import MappingNode, ScalarNode
from moulin.rouge import sfdisk, ext_utils
from moulin.yaml_helpers import get_scalar_node, get_mapping_node, YAMLProcessingError

log = logging.getLogger(__name__)


class BlockEntry():
    "Base class for various block entries"

    # pylint: disable=too-few-public-methods

    def write(self, _file, _offset):
        "write() in base class does nothing"


class GPTPartition(NamedTuple):
    "Represents one partition in GPT"
    label: str
    gpt_type: str
    start: int
    size: int
    entry: BlockEntry


class GPT(BlockEntry):
    "Represents GUID Partition Table"

    def __init__(self, node: MappingNode):
        entries: List[GPTPartition] = []

        partitions = get_mapping_node(node, "partitions")
        if not partitions:
            raise YAMLProcessingError("Can't find 'partitions' entry", node.start_mark)
        for part_id, part in partitions.value:
            label: str = part_id.value
            if not isinstance(part, MappingNode):
                raise YAMLProcessingError("Excepted mapping node", part.start_mark)

            entry_obj, gpt_type = self._process_entry(part)
            entries.append(
                GPTPartition(label, gpt_type, start=0, size=entry_obj.size(), entry=entry_obj))

        self._partitions, self._size = sfdisk.fixup_partition_table(entries)

    def size(self) -> int:
        "Returns size in bytes"
        return self._size

    @staticmethod
    def _process_entry(node: MappingNode):
        entry_obj = construct_entry(node)
        gpt_type_node = get_scalar_node(node, "gpt_type")
        if not gpt_type_node:
            log.warning("No GPT type is provided %s, using default", node.start_mark)
            gpt_type = "8DA63339-0007-60C0-C436-083AC8230908"
        else:
            gpt_type = gpt_type_node.value

        return (entry_obj, gpt_type)

    def write(self, fp, offset):
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


class RawImage(BlockEntry):
    "Represents raw image file which needs to be copied as is"

    def __init__(self, node: MappingNode):

        file_node = get_scalar_node(node, "image_path")
        if not file_node:
            raise YAMLProcessingError("'image_path' is required", node.start_mark)
        fname = file_node.value
        if not os.path.exists(fname):
            raise YAMLProcessingError(f"Can't find file '{fname}'", file_node.start_mark)
        self.fname = fname

        fsize = os.path.getsize(fname)
        size_node = get_scalar_node(node, "size")
        if size_node:
            self._size = _parse_size(size_node)
            if fsize > self._size:
                raise YAMLProcessingError(
                    f"File '{fname}' is bigger than partition entry ({self.size})",
                    size_node.start_mark)
        else:
            self._size = fsize

    def size(self) -> int:
        "Returns size in bytes"
        return self._size

    def write(self, fp, offset):
        ext_utils.dd(self.fname, fp, offset)


class AndroidSparse(BlockEntry):
    "Represents android sparse image file"

    def __init__(self, node: MappingNode):

        file_node = get_scalar_node(node, "image_path")
        if not file_node:
            raise YAMLProcessingError("'image_path' is required", node.start_mark)
        fname = file_node.value
        if not os.path.exists(fname):
            raise YAMLProcessingError(f"Can't find file '{fname}'", file_node.start_mark)
        self._fname = fname

        fsize = self._read_size(file_node.start_mark)
        size_node = get_scalar_node(node, "size")
        if size_node:
            self._size = _parse_size(size_node)
            if fsize > self._size:
                raise YAMLProcessingError(
                    f"Un-sparesd file '{fname}' is bigger than partition entry",
                    size_node.start_mark)
        else:
            self._size = fsize

    def _read_size(self, mark):
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

    def size(self) -> int:
        "Returns size in bytes"
        return self._size

    def write(self, fp, offset):
        with NamedTemporaryFile("w+b", dir=".") as tmpf:
            ext_utils.simg2img(self._fname, tmpf)
            ext_utils.dd(tmpf, fp, offset)


class EmptyEntry(BlockEntry):
    "Represents empty partition"

    def __init__(self, node: MappingNode):

        size_node = get_scalar_node(node, "size")
        if size_node:
            self._size = _parse_size(size_node)
        else:
            raise YAMLProcessingError("size is mandatory for 'empty' entry", node.start_mark)

    def size(self) -> int:
        "Returns size in bytes"
        return self._size


class Ext4(BlockEntry):
    "Represents ext4 fs with list of files"

    def __init__(self, node: MappingNode):
        files_node = get_mapping_node(node, "files")
        self._files: List[Tuple[str, str]] = []
        if files_node:
            remote_node: ScalarNode
            local_node: ScalarNode
            for remote_node, local_node in files_node.value:
                if not isinstance(remote_node, ScalarNode) or not isinstance(
                        local_node, ScalarNode):
                    raise YAMLProcessingError("Expected mapping 'remote':'local'",
                                              remote_node.start_mark)
                remote_name = remote_node.value
                local_name = local_node.value
                if not os.path.isfile(local_name):
                    raise YAMLProcessingError(f"Can't find file '{local_name}'",
                                              local_node.start_mark)
                self._files.append((remote_name, local_name))
        files_size = sum([os.path.getsize(x[1]) for x in self._files]) + 2 * 1024 * 1024
        size_node = get_scalar_node(node, "size")
        if size_node:
            self._size = _parse_size(size_node)
            if files_size > self._size:
                raise YAMLProcessingError(
                    f"Computed size is {files_size}, it is bigger than partition size {self._size}",
                    size_node.start_mark)
        else:
            self._size = files_size

    def size(self) -> int:
        "Returns size in bytes"
        return self._size

    def write(self, fp, offset):
        with NamedTemporaryFile() as tempf, TemporaryDirectory() as tempd:
            for remote, local in self._files:
                shutil.copyfile(local, os.path.join(tempd, remote))
            tempf.truncate(self._size)
            ext_utils.mkext4fs(tempf, tempd)
            ext_utils.dd(tempf, fp, offset)


_ENTRY_TYPES = {
    "gpt": GPT,
    "raw_image": RawImage,
    "ext4": Ext4,
    "empty": EmptyEntry,
    "android_sparse": AndroidSparse,
}


def construct_entry(node: MappingNode) -> BlockEntry:
    "Construct BlockEntry object from YAML node"
    type_node = get_scalar_node(node, "type")
    if not type_node:
        raise YAMLProcessingError("Entry 'type' is required", node.start_mark)

    entry_type: str = type_node.value
    if entry_type not in _ENTRY_TYPES:
        raise YAMLProcessingError(f"Unknown type '{entry_type}'", type_node.start_mark)

    return _ENTRY_TYPES[entry_type](node)


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


def _parse_size(node: ScalarNode) -> int:
    components = node.value.split(" ")
    if len(components) == 1:
        return int(components[0])
    if len(components) == 2:
        suffix = components[1]
        if suffix not in _SUFFIXES:
            raise YAMLProcessingError(f"Unknown size suffix '{suffix}'", node.start_mark)
        scaler = _SUFFIXES[suffix]
        return int(components[0]) * scaler
    raise YAMLProcessingError(f"Can't parse size entry '{node.value}'", node.start_mark)

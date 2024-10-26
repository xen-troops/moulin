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
import subprocess
from typing import List, Tuple, NamedTuple, cast
from tempfile import NamedTemporaryFile, TemporaryDirectory

from typing import Optional
from yaml import Mark
from moulin.rouge import gpti, ext_utils
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
    protective_mbr_type: int
    entry: BlockEntry


class GPT(BlockEntry):
    "Represents GUID Partition Table"

    def __init__(self, node: YamlValue, **kwargs):
        self._partitions: List[GPTPartition] = []
        self._size: int = 0
        self._sector_size: int = 512
        self._requested_image_size: Optional[int] = None

        self._hybrid_mbr: bool = node.get("hybrid_mbr", False).as_bool

        _requested_image_size_node = node.get("image_size", None)
        if _requested_image_size_node:
            self._requested_image_size = _parse_size(_requested_image_size_node)

        self._sector_size = node.get("sector_size", 512).as_int

        for part_id, part in node["partitions"].items():
            label = part_id
            entry_obj, gpt_type, gpt_guid, mbr_type = self._process_entry(
                part, sector_size=self._sector_size)
            self._partitions.append(
                GPTPartition(label,
                             gpt_type,
                             gpt_guid,
                             start=0,
                             size=0,
                             entry=entry_obj,
                             protective_mbr_type=mbr_type))

    def size(self) -> int:
        "Returns size of image in bytes. Requested in yaml or actually calculated."
        if not self._size:
            self._complete_init()

        if self._requested_image_size:
            if self._requested_image_size < self._size:
                raise Exception(
                    f"Actual size ({self._size}) of image is bigger than requested one ({self._requested_image_size}).")
            else:
                self._size = self._requested_image_size

        return self._size

    @staticmethod
    def _process_entry(node: YamlValue, **kwargs):
        entry_obj = construct_entry(node, **kwargs)
        gpt_type = node.get("gpt_type", "").as_str
        if not gpt_type:
            log.warning("No GPT type is provided %s, using default", node.mark)
            gpt_type = "8DA63339-0007-60C0-C436-083AC8230908"

        gpt_guid = node.get("gpt_guid", "").as_str

        mbr_type = node.get("mbr_type", 0x100).as_int

        return (entry_obj, gpt_type, gpt_guid, mbr_type)

    def _complete_init(self):
        partitions = [x._replace(size=x.entry.size()) for x in self._partitions]
        self._partitions, self._size = gpti.fixup_partition_table(partitions, self._sector_size)

    def write(self, fp, offset):
        if not self._size:
            self._complete_init()

        gpti.write(fp, self._partitions, offset, self._size, self._sector_size, self._hybrid_mbr)

        for part in self._partitions:
            part.entry.write(fp, part.start + offset)

    def get_deps(self) -> List[str]:
        "Return list of dependencies needed to build this block"
        return list(itertools.chain().from_iterable(
            [part.entry.get_deps() for part in self._partitions]))


class RawImage(BlockEntry):
    "Represents raw image file which needs to be copied as is"

    def __init__(self, node: YamlValue, **kwargs):
        self._node = node
        self._fname = self._node["image_path"].as_str
        self._size = 0
        self._resize = True

    def _complete_init(self):
        mark = self._node["image_path"].mark
        if not os.path.exists(self._fname):
            raise YAMLProcessingError(f"Can't find file '{self._fname}'", mark)
        fsize = os.path.getsize(self._fname)
        self._resize = self._node.get("resize", True).as_bool
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

        fsize = os.path.getsize(self._fname)

        if self._resize and fsize < self._size:
            # Not using default /tmp to prevent filling ram with huge images
            with TemporaryDirectory(dir=".") as tmpd:
                shutil.copy(self._fname, tmpd)
                with open(os.path.join(tmpd, os.path.basename(self._fname)), "rb+") as data:
                    data.truncate(self._size)
                try:
                    ext_utils.resize2fs(os.path.join(tmpd, os.path.basename(self._fname)))
                except subprocess.CalledProcessError as e:
                    log.error(
                        """Failed to resize %s partition.
        Right now we support resizing for EXT{2,3,4} partitions only.
        If you don't really want to resize it, please remove 'size' parameter or set 'resize' to false.
        If you want to resize some other type of partitions - please create a PR or notify us at least.""",
                        self._fname)
                    raise e

                ext_utils.dd(os.path.join(tmpd, os.path.basename(self._fname)), fp, offset)
        else:
            ext_utils.dd(self._fname, fp, offset)

    def get_deps(self) -> List[str]:
        "Return list of dependencies needed to build this block"
        return [self._fname]


class AndroidSparse(BlockEntry):
    "Represents android sparse image file"

    def __init__(self, node: YamlValue, **kwargs):
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

    def __init__(self, node: YamlValue, **kwargs):
        self._size = _parse_size(node["size"])
        self._fill_by_zero = (node.get("filled", "").as_str == "zeroes")

    def size(self) -> int:
        "Returns size in bytes"
        return self._size

    def write(self, fp, offset):
        if self._fill_by_zero:
            ext_utils.dd("/dev/zero", fp, offset, out_size=self._size)


class FileSystem(BlockEntry):
    "Represents a filesystem with list of files"

    def __init__(self, node: YamlValue, **kwargs):
        self._node = node
        self._size = 0
        self._items: List[Tuple[str, str, Mark]] = []

        files_node = self._node.get("files", None)
        if files_node:
            log.warn("Usage of 'files' is deprecated. Use 'items' please.")
            for remote_name, local_node in cast(YamlValue, files_node).items():
                self._items.append((remote_name, local_node.as_str, local_node.mark))

        items_node = self._node.get("items", None)
        if items_node:
            for remote_name, local_node in cast(YamlValue, items_node).items():
                self._items.append((remote_name, local_node.as_str, local_node.mark))

    def _complete_init(self):
        for _, local_name, local_mark in self._items:
            if not os.path.isfile(local_name) and not os.path.isdir(local_name):
                raise YAMLProcessingError(f"Can't find file '{local_name}'", local_mark)

        # calculate size of original files and directories
        files_size = 0
        for remote_path, local_path, _ in self._items:
            if os.path.isfile(local_path):
                files_size += os.path.getsize(local_path)
            if os.path.isdir(local_path):
                files_size += os.path.getsize(local_path)
                for (dirpath, dirnames, filenames) in os.walk(local_path, topdown=True):
                    for filename in filenames:
                        # we may have links to location that is incorrect on host, so we use lstat to handle this
                        files_size += os.lstat(os.path.join(dirpath, filename)).st_size
                    for dirname in dirnames:
                        files_size += os.path.getsize(os.path.join(dirpath, dirname))
        files_size += 8 * 1024 * 1024

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
        return [f[1] for f in self._items]


class Ext4(FileSystem):
    "Represents ext4 fs with list of files"
    def write(self, fp, offset):
        if not self._size:
            self._complete_init()
        with NamedTemporaryFile() as tempf, TemporaryDirectory() as tempd:
            for remote, local, _ in self._items:
                # user can specify destination folder from root
                # and we need to remove very first '/' for correct
                # work of os.path.join
                remote = remote.lstrip('/')
                # create destination subfolders
                remote_path_and_name = os.path.split(remote)
                if remote_path_and_name[0]:
                    # create destination subfolder
                    os.makedirs(os.path.join(tempd, remote_path_and_name[0]), exist_ok=True)

                if os.path.isfile(local):
                    shutil.copyfile(local, os.path.join(tempd, remote))
                if os.path.isdir(local):
                    shutil.copytree(local, os.path.join(tempd, remote), symlinks=True, dirs_exist_ok=True)
            tempf.truncate(self._size)
            ext_utils.mkext4fs(tempf, tempd)
            ext_utils.dd(tempf, fp, offset)


class Vfat(FileSystem):
    "Represents vfat fs with list of files"

    def __init__(self, node: YamlValue, **kwargs):
        super(Vfat, self).__init__(node, **kwargs)
        self._sector_size = kwargs.get('sector_size')

    def unwrap_dirs(self):
        "Return list of files with flatten content of the directories"
        out_list: List[Tuple[str, str, Mark]] = []
        for remote, local, mark in self._items:
            if os.path.isfile(local):
                out_list.append([remote, local, mark])
            if os.path.isdir(local):
                for (dirpath, _, filenames) in os.walk(local, topdown=True):
                    remote_dirpath = dirpath.replace(local, remote, 1)
                    for filename in filenames:
                        # we skip symlinks as not supported on vfat
                        if os.path.islink(os.path.join(dirpath, filename)):
                            log.warn("Symlink '%s' is skipped.", os.path.join(dirpath, filename))
                        else:
                            out_list.append([os.path.join(remote_dirpath, filename),
                                             os.path.join(dirpath, filename), mark])
        return out_list

    def write(self, fp, offset):
        if not self._size:
            self._complete_init()
        with NamedTemporaryFile() as tempf:
            tempf.truncate(self._size)
            ext_utils.mkvfatfs(tempf, self._sector_size)
            # for vfat we have to create each subdir (if any) and copy file one by one
            # that's why we need to 'unwrap' content of any input directory
            self._items = self.unwrap_dirs()
            # scan all remote filenames and collect the list of folders to create
            list_for_mmd = list()
            for remote, _, _ in self._items:
                # remove starting '/' to avoid:
                # - icluding different forms of same name, like "/zxc" and "zxc"
                # - adding root folder "/" to list
                remote_path_and_name = os.path.split(remote.lstrip('/'))
                if remote_path_and_name[0]:
                    # Here is explanation of what we do here.
                    # mmd can't create chain of folders like '/a/s/d' if parent
                    # folders (/a/s/) do not exist.
                    # You need to create each subfolder by separate call or provide them
                    # in incremental way, like `mmd /a /a/s /a/s/d`.
                    # Taking into account that we work with an image file,
                    # we need to prefix each folder with "::".
                    # So here we split each folder into slices,
                    # and re-assemble slices in incremental way.
                    current_path = ""
                    for path_slice in remote_path_and_name[0].split('/'):
                        if path_slice:
                            current_path += "/" + path_slice
                            list_for_mmd.append("::" + current_path)
            if list_for_mmd:
                # Remove duplicates by transforming the list of strings to the set of strings.
                # And sort strings because after 'set()' we may have 'a/s/d' before 'a/s' in some cases.
                list_for_mmd = sorted(set(list_for_mmd))
                # create all destination subfolders at once
                ext_utils.mmd(tempf, list_for_mmd)

            for remote, local, _ in self._items:
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


def construct_entry(node: YamlValue, **kwargs) -> BlockEntry:
    "Construct BlockEntry object from YAML node"
    entry_type = node["type"]
    if entry_type.as_str not in _ENTRY_TYPES:
        raise YAMLProcessingError(f"Unknown type '{entry_type.as_str}'", entry_type.mark)

    return _ENTRY_TYPES[entry_type.as_str](node, **kwargs)


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

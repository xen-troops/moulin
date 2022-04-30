# SPDX-License-Identifier: Apache-2.0
# Copyright 2022 EPAM Systems
"""Unpacker fetcher module"""

import os.path
import subprocess
from typing import List
from moulin.yaml_helpers import YAMLProcessingError
from moulin.yaml_wrapper import YamlValue
from moulin import ninja_syntax


def get_fetcher(conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
    """Construct and return RepoFetcher object"""
    return UnpackFetcher(conf, build_dir, generator)


def gen_build_rules(generator: ninja_syntax.Writer):
    """Generate build rules using Ninja generator"""
    generator.rule("tar_unpack",
                   command="mkdir -p $out_dir && tar -m -C $out_dir -xf $in",
                   description="Unpack $in with tar")
    generator.rule("zip_unpack",
                   command="mkdir -p $out_dir && unzip -DD -n $in -d $out_dir",
                   description="Unpack $in with unzip")
    generator.newline()


class UnpackFetcher:
    """
    Unpak fetcher class. Provides methods to generate rules for
    unpacking various archives
    """

    def __init__(self, conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
        self.conf = conf
        self.build_dir = build_dir
        self.generator = generator
        self.fname = conf["file"].as_str
        dirname = conf.get("dir", default=".").as_str
        self.out_dir = os.path.join(build_dir, dirname)
        self.type = conf["archive_type"].as_str

        known_types = ["tar", "zip"]
        if self.type not in known_types:
            raise YAMLProcessingError(f"Unkown archive type: {self.type}",
                                      self.conf["archive_type"].mark)

        if not os.path.exists(self.fname):
            raise YAMLProcessingError(f"File \"{self.fname}\" does not exist",
                                      self.conf["file"].mark)

    def gen_fetch(self) -> List[str]:
        """Generate instructions to unpack archive"""
        rule_name = f"{self.type}_unpack"
        files = self.get_file_list()
        self.generator.build(files, rule_name, self.fname, variables={"out_dir": self.out_dir})

        return files

    def get_file_list(self) -> List[str]:
        "Get list of files in archive"

        commands = {
            "tar": ["tar", "--list", "-f", f"{self.fname}"],
            "zip": ["unzip", "-Z", "-2", f"{self.fname}"]
        }
        ret = subprocess.run(commands[self.type],
                             check=True,
                             stdout=subprocess.PIPE,
                             universal_newlines=True)
        return [os.path.join(self.out_dir, x) for x in ret.stdout.split("\n") if len(x) > 0]

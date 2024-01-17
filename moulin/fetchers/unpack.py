# SPDX-License-Identifier: Apache-2.0
# Copyright 2022 EPAM Systems
"""Unpacker fetcher module"""

import sys
import os.path
import subprocess
from typing import List
from moulin.yaml_helpers import YAMLProcessingError
from moulin.yaml_wrapper import YamlValue
from moulin import ninja_syntax
from moulin.utils import create_stamp_name
import logging

if __name__ != "__main__":
    log = logging.getLogger(__name__)
else:
    log = logging.getLogger("moulin.fetcher.unpack")


def get_fetcher(conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
    """Construct and return RepoFetcher object"""
    return UnpackFetcher(conf, build_dir, generator)


def gen_build_rules(generator: ninja_syntax.Writer):
    """Generate build rules using Ninja generator"""
    generator.rule("tar_unpack",
                   command="mkdir -p $out_dir && tar -m -C $out_dir -xf $in && touch $out",
                   description="Unpack $in with tar")
    generator.rule("zip_unpack",
                   command="mkdir -p $out_dir && unzip -DD -n $in -d $out_dir && touch $out",
                   description="Unpack $in with unzip")
    generator.rule("unpack_fetcher_dyndep",
                   command='python3 -m "moulin.fetchers.unpack" gen_dyndep $in $out $type $outdir',
                   description="List files for $in")
    generator.newline()


def main() -> None:
    """
    Entry point for unpack module. This function is supposed to be called
    by build system (aka Ninja) to generate dyndep file, which contains list of
    the archive contents
    """
    if sys.argv[1] != "gen_dyndep":
        log.error("Module supports only gen_dyndep operation")
        sys.exit(1)
    fname = sys.argv[2]
    outfile = open(sys.argv[3], "w")
    archive_type = sys.argv[4]
    outdir = sys.argv[5]
    generator = ninja_syntax.Writer(outfile)
    generator.variable("ninja_dyndep_version", "1")
    contents = _get_archive_file_list(archive_type, fname, outdir)
    generator.build(_create_stamp_name(outdir, fname),
                    "dyndep",
                    implicit_outputs=contents,
                    variables=dict(restat=1))


def _get_archive_file_list(archive_type: str, fname: str, out_dir: str) -> List[str]:
    "Get list of files in archive"

    commands = {
        "tar": ["tar", "--list", "-f", f"{fname}"],
        "zip": ["unzip", "-Z", "-2", f"{fname}"]
    }
    ret = subprocess.run(commands[archive_type],
                         check=True,
                         stdout=subprocess.PIPE,
                         universal_newlines=True)
    return [os.path.join(out_dir, x) for x in ret.stdout.split("\n") if len(x) > 0]


def _create_stamp_name(outdir: str, fname: str):
    return create_stamp_name(outdir, fname)


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

    def gen_fetch(self) -> List[str]:
        """Generate instructions to unpack archive"""
        rule_name = f"{self.type}_unpack"
        stamp = _create_stamp_name(self.out_dir, self.fname)
        dyndep = create_stamp_name(self.out_dir, self.fname, "dyndep")
        self.generator.build(stamp,
                             rule_name,
                             self.fname,
                             order_only=[dyndep],
                             variables={"out_dir": self.out_dir},
                             dyndep=dyndep)
        self.generator.build(dyndep,
                             "unpack_fetcher_dyndep",
                             self.fname,
                             variables=dict(outdir=self.out_dir, type=self.type))

        return stamp

    def get_file_list(self) -> List[str]:
        "Get list of files in archive"

        return _get_archive_file_list(self.type, self.fname, self.out_dir)


if __name__ == "__main__":
    main()

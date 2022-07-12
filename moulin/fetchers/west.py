# SPDX-License-Identifier: Apache-2.0
# Copyright 2022 EPAM Systems
"""West fetcher module"""

import shlex
import os.path
import subprocess
import pygit2
from typing import List
from moulin.utils import create_stamp_name
from moulin.yaml_wrapper import YamlValue
from moulin import ninja_syntax


def get_fetcher(conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
    """Construct and return WestFetcher object"""
    return WestFetcher(conf, build_dir, generator)


def gen_build_rules(generator: ninja_syntax.Writer):
    """Generate build rules using Ninja generator"""

    cmd = " && ".join([
        "mkdir -p $build_dir",
        "cd $build_dir",
        "west init $west_args",
    ])
    generator.rule("west_init",
                   command=cmd,
                   description="Creating a west workspace (west init)")
    generator.newline()

    # `west update -n` is used here to narrow down fetched data
    # and significantly reduce number of output lines.
    # See `west help update` for additional info.
    cmd = " && ".join([
        "cd $build_dir",
        "west update -n",
        "touch $out",
    ])
    generator.rule("west_update",
                   command=cmd,
                   description="west update")
    generator.newline()


class WestFetcher:
    """
    West fetcher class. Provides methods to generate rules for
    fetching zephyr-based repositories using west meta-tool
    """
    def __init__(self, conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
        self.conf = conf
        self.build_dir = build_dir
        self.generator = generator

    def gen_fetch(self):
        """Generate instructions to fetch west-based repository"""
        west_args = []

        url = self.conf.get("url", "").as_str
        if url:
            west_args.append(f"-m {shlex.quote(url)}")
        rev = self.conf.get("rev", "").as_str
        if rev:
            west_args.append(f"--mr {shlex.quote(rev)}")
        filename = self.conf.get("file", "").as_str
        if filename:
            west_args.append(f"--mf {shlex.quote(filename)}")

        init_target = os.path.join(self.build_dir, ".west")
        update_target = create_stamp_name(self.build_dir, "update")

        self.generator.build(init_target,
                             "west_init",
                             variables={
                                 "build_dir": self.build_dir,
                                 "west_args": " ".join(west_args)
                             })
        self.generator.newline()

        self.generator.build(update_target,
                             "west_update",
                             init_target,
                             variables={
                                 "build_dir": self.build_dir
                             })
        self.generator.newline()

        return update_target

    def get_file_list(self) -> List[str]:
        """Get list of files under version control"""

        # First, get list of projects
        west_out = subprocess.run(["west", "list", "--format='{path}'"],
                                  check=True,
                                  cwd=self.build_dir,
                                  stdout=subprocess.PIPE,
                                  encoding="utf-8")
        projects = [x.strip("'") for x in west_out.stdout.split("\n")]

        # Then interrogate each git repo
        result: List[str] = []
        for project in projects:
            if len(project) == 0:
                continue
            git_dir = os.path.join(self.build_dir, project)
            repo = pygit2.Repository(git_dir)
            index = repo.index
            index.read()
            for entry in index:
                path = os.path.join(git_dir, entry.path)
                if os.path.isfile(path):
                    result.append(path.replace("$", "$$"))
        return result

    def capture_state(self):
        """Update provided conf with the current fetcher state"""
        raise Exception("capture_state is not implemented for west fetcher")

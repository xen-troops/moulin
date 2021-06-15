# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""Repo fetcher module"""

import shlex
import os.path
from moulin.utils import create_stamp_name


def get_fetcher(conf, build_dir, generator):
    """Construct and return RepoFetcher object"""
    return RepoFetcher(conf, build_dir, generator)


def gen_build_rules(generator):
    """Generate build rules using Ninja generator"""
    cmd = " && ".join([
        "mkdir -p $repo_dir",
        "cd $repo_dir",
        "repo init -u $url $repo_args",
    ])
    generator.rule("repo_init",
                   command=cmd,
                   description="Initialize repo directory")
    generator.newline()

    generator.rule("repo_sync",
                   command="cd $repo_dir && repo sync && touch $out",
                   description="Repo sync")
    generator.newline()


class RepoFetcher:
    """
    Repo fetcher class. Provides methods to generate rules for
    fetching repo-based repositories
    """
    def __init__(self, conf, build_dir, generator):
        self.conf = conf
        self.build_dir = build_dir
        self.generator = generator
        self.url = conf["url"]
        self.repo_dir = os.path.join(build_dir, conf.get("dir", "."))

    def gen_fetch(self):
        """Generate instructions to fetch repo-based repository"""
        repo_args = []
        conf = self.conf
        if "manifest" in conf:
            repo_args.append(f"-m {shlex.quote(conf['manifest'])}")
        if "rev" in conf:
            repo_args.append(f"-b {shlex.quote(conf['rev'])}")
        if "depth" in conf:
            repo_args.append(f"--depth={conf['depth']}")
        if "groups" in conf:
            repo_args.append(f"-g {conf['groups']}")

        init_target = os.path.join(self.repo_dir, ".repo")
        sync_stamp = create_stamp_name(self.build_dir, self.url, "sync")

        self.generator.build(init_target,
                             "repo_init",
                             variables={
                                 "repo_dir": self.repo_dir,
                                 "url": self.url,
                                 "repo_args": " ".join(repo_args)
                             })
        self.generator.newline()

        self.generator.build(sync_stamp,
                             "repo_sync",
                             init_target,
                             variables={"repo_dir": self.repo_dir})
        self.generator.newline()

        return sync_stamp

    def capture_state(self):
        """
        Update provided conf with the current repo state. This is
        mostly needed for build history/reproducible builds.
        """
        raise Exception("capture_state is not implemented for repo fetcher")

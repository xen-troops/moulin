# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""Repo fetcher module"""

import shlex
import os.path
import subprocess
from typing import List
import pygit2
from moulin.utils import create_stamp_name
from moulin.yaml_wrapper import YamlValue
from moulin import ninja_syntax


def get_fetcher(conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
    """Construct and return RepoFetcher object"""
    return RepoFetcher(conf, build_dir, generator)


def gen_build_rules(generator: ninja_syntax.Writer):
    """Generate build rules using Ninja generator"""
    cmd = " && ".join([
        "mkdir -p $repo_dir",
        "cd $repo_dir",
        "repo init -u $url $repo_args",
    ])
    generator.rule("repo_init", command=cmd, description="Initialize repo directory")
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
    def __init__(self, conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
        self.conf = conf
        self.build_dir = build_dir
        self.generator = generator
        self.url = conf["url"].as_str
        dirname = conf.get("dir", default=".").as_str
        self.repo_dir = os.path.join(build_dir, dirname)

    def gen_fetch(self):
        """Generate instructions to fetch repo-based repository"""
        repo_args = []
        manifest = self.conf.get("manifest", "").as_str
        if manifest:
            repo_args.append(f"-m {shlex.quote(manifest)}")
        rev = self.conf.get("rev", "").as_str
        if rev:
            repo_args.append(f"-b {shlex.quote(rev)}")
        depth = self.conf.get("depth", 0).as_int
        if depth:
            repo_args.append(f"--depth={depth}")
        groups = self.conf.get("groups", "").as_str
        if groups:
            repo_args.append(f"-g {groups}")

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

    def get_file_list(self) -> List[str]:
        "Get list of files under repo control"

        # First, get list of projects
        repo_out = subprocess.run(["repo", "list"],
                                  check=True,
                                  cwd=self.repo_dir,
                                  stdout=subprocess.PIPE,
                                  encoding="utf-8")
        projects = [x.split(":")[0].strip() for x in repo_out.stdout.split("\n")]

        # Then interrogate each git repo
        result: List[str] = []
        for project in projects:
            if len(project) == 0:
                continue
            git_dir = os.path.join(self.repo_dir, project)
            repo = pygit2.Repository(git_dir)
            index = repo.index
            index.read()
            for entry in index:
                path = os.path.join(git_dir, entry.path)
                if os.path.isfile(path):
                    result.append(path.replace("$", "$$"))
        return result

    def capture_state(self):
        """
        Update provided conf with the current repo state. This is
        mostly needed for build history/reproducible builds.
        """
        raise Exception("capture_state is not implemented for repo fetcher")

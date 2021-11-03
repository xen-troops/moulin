# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""Git fetcher module"""

import os.path
from typing import cast
import pygit2
from yaml.nodes import MappingNode
from yaml.representer import SafeRepresenter
from moulin.utils import create_stamp_name
from moulin import yaml_helpers as yh
from moulin import ninja_syntax


def get_fetcher(conf: MappingNode, build_dir: str, generator: ninja_syntax.Writer):
    """Construct and return GitFetcher object"""
    return GitFetcher(conf, build_dir, generator)


def gen_build_rules(generator: ninja_syntax.Writer):
    """Generate build rules using Ninja generator"""
    generator.rule("git_clone",
                   command="git clone -q $git_url $git_dir && touch $out",
                   description="git clone")
    generator.newline()

    generator.rule("git_checkout",
                   command="git -C $git_dir checkout -q $git_rev && touch $out",
                   description="git checkout")
    generator.newline()


def _guess_dirname(url: str):
    # TODO: Add support for corner cases
    if url.endswith(".git"):
        url = url[:-4]
    if url.endswith("/"):
        url = url[:-1]
    return url.split("/")[-1]


_SEEN_REPOS = []


class GitFetcher:
    """Git fetcher class. Provides methods to generate rules for fetching git repositories"""
    def __init__(self, conf: MappingNode, build_dir: str, generator: ninja_syntax.Writer):
        self.conf = conf
        self.build_dir = build_dir
        self.generator = generator
        self.url = cast(str, yh.get_mandatory_str_value(conf, "url")[0])
        dirname = cast(str, yh.get_str_value(conf, "dir", default=_guess_dirname(self.url))[0])
        self.git_dir = os.path.join(build_dir, dirname)
        self.git_rev = yh.get_str_value(conf, "rev", default="master")[0]

    def gen_fetch(self):
        """Generate instruction to fetch git repo"""
        clone_target = self.git_dir
        checkout_stamp = create_stamp_name(self.build_dir, self.url, "checkout")

        # Do not checkout repos for the second time
        if checkout_stamp in _SEEN_REPOS:
            return checkout_stamp

        _SEEN_REPOS.append(checkout_stamp)
        self.generator.build(clone_target,
                             "git_clone",
                             variables={
                                 "git_url": self.url,
                                 "git_dir": self.git_dir
                             })
        self.generator.newline()
        self.generator.build(checkout_stamp,
                             "git_checkout",
                             clone_target,
                             variables={
                                 "git_rev": self.git_rev,
                                 "git_dir": self.git_dir
                             })
        self.generator.newline()
        return checkout_stamp

    def capture_state(self):
        """
        Update provided conf with the actual commit ID. This is
        mostly needed for build history/reproducible builds.
        """
        repo = pygit2.Repository(self.git_dir)
        head = repo.revparse_single("HEAD")
        rev_node = yh.get_scalar_node(self.conf, "rev")
        if rev_node:
            rev_node.value = str(head)
        else:
            representer = SafeRepresenter()
            self.conf.value.append(representer.represent_str("rev"),
                                   representer.represent_str(str(head)))

# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""Git fetcher module"""

import os.path
import pygit2
from moulin.utils import create_stamp_name


def get_fetcher(conf, build_dir, generator):
    """Construct and return GitFetcher object"""
    return GitFetcher(conf, build_dir, generator)


def gen_build_rules(generator):
    """Generate build rules using Ninja generator"""
    generator.rule("git_clone",
                   command="git clone -q $git_url $git_dir && touch $out",
                   description="git clone")
    generator.newline()

    generator.rule(
        "git_checkout",
        command="git -C $git_dir checkout -q $git_rev && touch $out",
        description="git checkout")
    generator.newline()


def _guess_dirname(url):
    # TODO: Add support for corner cases
    if url.endswith(".git"):
        url = url[:-4]
    if url.endswith("/"):
        url = url[:-1]
    return url.split("/")[-1]


_SEEN_REPOS = []


class GitFetcher:
    """Git fetcher class. Provides methods to generate rules for fetching git repositories"""
    def __init__(self, conf, build_dir, generator):
        self.conf = conf
        self.build_dir = build_dir
        self.generator = generator
        self.url = conf["url"]
        self.git_dir = os.path.join(build_dir,
                                    conf.get("dir", _guess_dirname(self.url)))
        self.git_rev = conf.get("rev", "master")

    def gen_fetch(self):
        """Generate instruction to fetch git repo"""
        clone_target = self.git_dir
        checkout_stamp = create_stamp_name(self.build_dir, self.url,
                                           "checkout")

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
        self.conf["rev"] = str(head)

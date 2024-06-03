# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""Git fetcher module"""

import os.path
from typing import List
import pygit2
from moulin.yaml_helpers import YAMLProcessingError
from moulin.yaml_wrapper import YamlValue
from moulin.utils import create_stamp_name
from moulin import ninja_syntax


def get_fetcher(conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
    """Construct and return GitFetcher object"""
    return GitFetcher(conf, build_dir, generator)


def gen_build_rules(generator: ninja_syntax.Writer):
    """Generate build rules using Ninja generator"""
    # We use git with the console which is hidden from the user.
    # That's why we need to disable any interaction with the user.
    # Here we address two cases:
    #
    # SSH access to unknown host results in SSH asking confirmation
    # from the user, so we use `GIT_SSH_COMMAND='ssh -o BatchMode=yes'`
    # to inform user to add host manually.
    #
    # HTTPS access to private repo results in git asking for
    # username/password. So we use `GIT_TERMINAL_PROMPT=0`
    # to abort fetching and inform user, that may be other way should
    # be used, like ssh.
    generator.rule("git_clone",
                   command="GIT_SSH_COMMAND='ssh -o BatchMode=yes' "
                           "GIT_TERMINAL_PROMPT=0 "
                           "git clone $git_clone_opts -q $git_url $git_dir  && touch $out",
                   description="git clone")
    generator.newline()

    generator.rule("git_checkout",
                   command="git -C $git_dir checkout $git_checkout_opts -q $git_rev && touch $out",
                   description="git checkout")
    generator.newline()


def _guess_dirname(url: str):
    # TODO: Add support for corner cases
    if url.endswith(".git"):
        url = url[:-4]
    if url.endswith("/"):
        url = url[:-1]
    return url.split("/")[-1]


_SEEN_REPOS_REV = {}


class GitFetcher:
    """Git fetcher class. Provides methods to generate rules for fetching git repositories"""
    def __init__(self, conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
        self.conf = conf
        self.build_dir = build_dir
        self.generator = generator
        self.url = conf["url"].as_str
        dirname = conf.get("dir", default=_guess_dirname(self.url)).as_str
        self.git_dir = os.path.join(build_dir, dirname)
        self.git_rev = conf.get("rev", default="master").as_str
        self.clone_opts = []
        self.checkout_opts = []
        depth = conf.get("depth", 0).as_int
        if depth:
            self.clone_opts.append(f"--depth {depth}")
        if conf.get("submodules", default=False).as_bool:
            self.enable_submodules = True
            self.clone_opts.append("--recurse-submodules")
            self.checkout_opts.append("--recurse-submodules")
            if depth:
                self.clone_opts.append("--shallow-submodules")
        else:
            self.enable_submodules = False

        # Download only requested revision. This is less flexible for
        # developers, but it is bulletproof in terms of potential
        # checkout issues
        if depth or self.enable_submodules:
            self.clone_opts.append(f"--branch {self.git_rev}")
        else:
            self.clone_opts.append("--no-checkout")

    def gen_fetch(self):
        """Generate instruction to fetch git repo"""
        clone_target = self.git_dir
        clone_stamp = create_stamp_name(self.build_dir, clone_target, self.url, "clone")
        checkout_stamp = create_stamp_name(self.build_dir, clone_target, self.url, "checkout")

        if checkout_stamp in _SEEN_REPOS_REV:
            if self.git_rev != _SEEN_REPOS_REV[checkout_stamp]:
                # Fail on occurrence of different revision for the already downloaded repository
                raise YAMLProcessingError(f"ERROR: Repository {self.url} cloned to '{clone_target}' "
                                          f"has two revisions '{self.git_rev}' "
                                          f"and '{_SEEN_REPOS_REV[checkout_stamp]}'", self.conf["rev"].mark)
            else:
                # Do not checkout repos for the second time
                return checkout_stamp

        _SEEN_REPOS_REV[checkout_stamp] = self.git_rev

        self.generator.build([clone_target, clone_stamp],
                             "git_clone",
                             variables={
                                 "git_url": self.url,
                                 "git_dir": self.git_dir,
                                 "git_clone_opts": " ".join(self.clone_opts),
                             })
        self.generator.newline()
        self.generator.build(checkout_stamp,
                             "git_checkout",
                             clone_stamp,
                             variables={
                                 "git_rev": self.git_rev,
                                 "git_dir": self.git_dir,
                                 "git_checkout_opts": " ".join(self.checkout_opts),
                             })
        self.generator.newline()
        return checkout_stamp

    def get_file_list(self) -> List[str]:
        "Get list of files under git control"
        files = []
        repo = pygit2.Repository(self.git_dir)
        index = repo.index
        index.read()
        files.extend([os.path.join(self.git_dir, entry.path) for entry in index])

        if self.enable_submodules:
            for submodule in repo.submodules:
                sub_repo = submodule.open()
                index = sub_repo.index
                index.read()
                files.extend(
                    [os.path.join(self.git_dir, submodule.path, entry.path) for entry in index])

        return files

    def capture_state(self):
        """
        Update provided conf with the actual commit ID. This is
        mostly needed for build history/reproducible builds.
        """
        repo = pygit2.Repository(self.git_dir)
        head = repo.revparse_single("HEAD")
        self.conf["rev"] = str(head)
        # TODO: Store submodules state
        if self.enable_submodules:
            raise NotImplementedError("Can't (yet) capture state for git submodules")

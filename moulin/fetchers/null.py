# SPDX-License-Identifier: Apache-2.0
# Copyright 2022 EPAM Systems
"""Null fetcher module"""

from typing import List

from moulin.yaml_wrapper import YamlValue
from moulin import ninja_syntax


def get_fetcher(conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
    """Construct and return NullFetcher object"""
    return NullFetcher(conf, build_dir, generator)


def gen_build_rules(generator: ninja_syntax.Writer):
    """Generate build rules using Ninja generator"""
    generator.newline()


class NullFetcher:
    """
    Repo fetcher class. Provides methods to generate rules for
    fetching repo-based repositories
    """
    def __init__(self, conf: YamlValue, build_dir: str, generator: ninja_syntax.Writer):
        pass

    def gen_fetch(self):
        """Generate instructions to fetch repo-based repository"""
        return "null.stamp"

    def get_file_list(self) -> List[str]:
        """Get list of files under fetcher control"""
        return []

    def capture_state(self):
        """Update provided conf with the current fetcher state"""

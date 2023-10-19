# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""Module hosting different utility functions"""

import os.path
import sys
import re


def create_stamp_name(*args):
    """Generate stamp file name based on input keywords"""
    stamp = "-".join(args)
    path = os.path.join(".stamps", stamp.replace("-", "--").replace(os.sep, "-").replace(":", "-"))
    return os.path.abspath(path)


def construct_fetcher_dep_cmd() -> str:
    "Generate command line to generate fetcher dependency file"
    this_script = os.path.abspath(sys.argv[0])
    args = " ".join(sys.argv[1:])
    return f"{this_script} {args} --fetcherdep $name"


def escape(val: str) -> str:
    """
    Escape special characters in the input string.

    This function takes an input string `val` and escapes special characters by adding escape
    sequences to them. The following transformations are applied:
    - Double quotes (") are escaped as \\".
    - Dollar signs ($) are escaped as $$.
    Args:
        val (str): The input string to be escaped.
    Returns:
        str: The escaped string.
    """
    result = val
    result = result.replace(r"\"", r"\\\"")
    result = result.replace("$", "$$")
    result = re.sub('(([^\\\\])"|^()")', '\\2\\"', result)
    return result

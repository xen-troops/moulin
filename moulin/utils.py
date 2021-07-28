# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""Module hosting different utility functions"""

import os.path
from typing import List, Union, Any


def create_stamp_name(*args):
    """Generate stamp file name based on input keywords"""
    stamp = "-".join(args)
    path = os.path.join(
        ".stamps",
        stamp.replace("-", "--").replace(os.sep, "-").replace(":", "-"))
    return os.path.abspath(path)


def flatten_list(lst: List[Union[List, Any]]) -> List[Any]:
    """Flatten list of lists"""
    result = []
    for elm in lst:
        if isinstance(elm, list):
            result.extend(elm)
        else:
            result.append(elm)
    return result

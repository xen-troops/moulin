# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""Module hosting different utility functions"""

import os.path


def create_stamp_name(*args):
    """Generate stamp file name based on input keywords"""
    stamp = "-".join(args)
    path = os.path.join(".stamps", stamp.replace("-", "--").replace(os.sep, "-").replace(":", "-"))
    return os.path.abspath(path)

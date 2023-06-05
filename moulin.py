#!/usr/bin/env python3

# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Console entry point for moulin
"""

from moulin.main import moulin_entry


def main():
    try:
        moulin_entry()
    except Exception as err:
        print(err)


if __name__ == "__main__":
    main()

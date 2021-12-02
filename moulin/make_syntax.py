# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Very minimal python module for generating Makefiles.
Loosely based on Ninja generator.
"""

import textwrap
from typing import List, Union, IO
from .ninja_syntax import as_list


class Writer:
    "Minimal Makefile Writter"

    def __init__(self, output: IO, width: int = 78):
        self.output = output
        self.width = width

    def _line(self, text: str) -> None:
        for line in textwrap.wrap(text,
                                  break_long_words=False,
                                  break_on_hyphens=False,
                                  subsequent_indent='  '):
            self.output.write(line + " \\\n")
        self.newline()

    def newline(self) -> None:
        "Emit a new line"
        self.output.write('\n')

    def comment(self, text) -> None:
        "Emit a comment"
        for line in textwrap.wrap(text,
                                  self.width - 2,
                                  break_long_words=False,
                                  break_on_hyphens=False):
            self.output.write('# ' + line + '\n')

    def simple_dep(self, outputs: Union[str, List[str]], inputs: Union[str, List[str]]) -> None:
        "Emit a simple dependency without build rules"
        outputs = as_list(outputs)
        inputs = as_list(inputs)

        self._line('%s: %s' % (' '.join(outputs), ' '.join(inputs)))

    def close(self) -> None:
        "Close the output file"
        self.output.close()

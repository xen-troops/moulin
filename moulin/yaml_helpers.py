# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""YAML processing helper functions and objects"""

from typing import Optional
from yaml.nodes import MappingNode, ScalarNode, SequenceNode, Node
from yaml import Mark


class YAMLProcessingError(Exception):
    "Error during processing YAML file"

    def __init__(self, message: str, mark: Mark):
        super().__init__()
        self.message = message
        self.mark = mark

    def __str__(self):
        return f"{self.message} {self.mark}"


def get_node(node: MappingNode, name: str) -> Optional[Node]:
    "Return node with given name from mapping"
    if not isinstance(node, MappingNode):
        raise YAMLProcessingError("Not a mapping node", node.start_mark)
    for subpair in node.value:
        if subpair[0].value == name:
            return subpair[1]
    return None


def get_scalar_node(node: MappingNode, name: str) -> Optional[ScalarNode]:
    "Return scalar node with given name from mapping"
    value = get_node(node, name)
    if not value:
        return None
    if not isinstance(value, ScalarNode):
        raise YAMLProcessingError("Expected scalar value", value.start_mark)
    return value


def get_mapping_node(node: MappingNode, name: str) -> Optional[MappingNode]:
    "Return mapping node with given name from mapping"
    value = get_node(node, name)
    if not value:
        return None
    if not isinstance(value, MappingNode):
        raise YAMLProcessingError("Expected mapping", value.start_mark)
    return value


def get_sequence_node(node: MappingNode, name: str) -> Optional[SequenceNode]:
    "Return sequence node with given name from mapping"
    value = get_node(node, name)
    if not value:
        return None
    if not isinstance(value, SequenceNode):
        raise YAMLProcessingError("Expected sequence", value.start_mark)
    return value

# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""YAML processing helper functions and objects"""

from typing import Optional, TypeVar, Tuple, List, Any, cast
from yaml.nodes import MappingNode, ScalarNode, SequenceNode, Node
from yaml.constructor import SafeConstructor
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


def get_mandatory_mapping_node(node: MappingNode, name: str) -> MappingNode:
    "Return mandatory mapping node with given name from mapping"
    ret = get_mapping_node(node, name)
    if not ret:
        raise YAMLProcessingError(f"Key '{name} is mandatory'", node.start_mark)
    return ret


def get_mandatory_sequence_node(node: MappingNode, name: str) -> SequenceNode:
    "Return mandatory sequence node with given name from mapping"
    ret = get_sequence_node(node, name)
    if not ret:
        raise YAMLProcessingError(f"Key '{name} is mandatory'", node.start_mark)
    return ret


def flatten_list(node: SequenceNode) -> None:
    "Flatten sequence of sequences in-place"
    for element in node.value:
        if isinstance(element, SequenceNode):
            node.value.remove(element)
            node.value.extend(element.value)


T = TypeVar('T')  # pylint: disable=invalid-name

yaml_constructor = SafeConstructor()


def get_typed_value(mapping_node: MappingNode,
                    name: str,
                    expected_type: type,
                    default: Optional[T] = None) -> Tuple[Optional[T], Optional[Mark]]:
    "Return scalar node with given name from mapping as value of type T"
    node = get_scalar_node(mapping_node, name)
    if not node:
        return default, None
    val = yaml_constructor.construct_object(node)
    if not isinstance(val, expected_type):
        raise YAMLProcessingError(
            f"Expected value of type {expected_type.__name__} for " +
            f" '{name}', not {type(val).__name__}", node.start_mark)
    return cast(Optional[T], val), node.start_mark


def get_mandatory_typed_value(mapping_node: MappingNode, name: str,
                              expected_type: type) -> Tuple[T, Mark]:
    "Return mandatory scalar node with given name from mapping as value of type T"
    ret, mark = get_typed_value(mapping_node, name, expected_type)
    if not ret or not mark:
        raise YAMLProcessingError(f"{name} key is mandatory", mapping_node.start_mark)
    return ret, mark


def get_boolean_value(mapping_node: MappingNode,
                      name: str,
                      default: Optional[bool] = None) -> Tuple[Optional[bool], Optional[Mark]]:
    "Return scalar node with given name from mapping as a boolean value"
    return get_typed_value(mapping_node, name, bool, default)


def get_str_value(mapping_node: MappingNode,
                  name: str,
                  default: Optional[str] = None) -> Tuple[Optional[str], Optional[Mark]]:
    "Return scalar node with given name from mapping as a string value"
    return get_typed_value(mapping_node, name, str, default)


def get_mandatory_str_value(mapping_node: MappingNode, name: str) -> Tuple[str, Mark]:
    "Return scalar node with given name from mapping as a string value"
    return get_mandatory_typed_value(mapping_node, name, str)


def get_mandatory_mapping(node: MappingNode, name: str) -> List[Tuple[Node, Any]]:
    "Return mandatory sequence node with given name from mapping"
    return get_mandatory_mapping_node(node, name).value

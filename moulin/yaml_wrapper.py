# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Wrappers for yaml.Node that provide better API
"""

from typing import Optional, List, Tuple, Iterator, Union, Dict

from yaml.nodes import MappingNode, ScalarNode, SequenceNode, Node
from yaml.constructor import SafeConstructor
from yaml.representer import SafeRepresenter
from yaml import Mark
from moulin.yaml_helpers import YAMLProcessingError

yaml_constructor = SafeConstructor()


class _YamlDefaultValue:
    """
    Helper class that have the same API as YamlValue, but is
    constructed from a builtin type. It is used to provide default
    value in YamlValue.get() method
    """
    def __init__(self, val: Union[bool, str, int, float, List, Dict, None]):
        self._val = val

    def __bool__(self):
        return self._val is not None

    @property
    def as_bool(self) -> bool:
        "Get the boolean value"
        if not isinstance(self._val, bool):
            raise TypeError("Expected boolean value")
        return self._val

    @property
    def as_str(self) -> str:
        "Get the string value"
        if not isinstance(self._val, str):
            raise TypeError("Expected string value")
        return self._val

    @property
    def as_int(self) -> int:
        "Get the integer value"
        if not isinstance(self._val, int):
            raise TypeError("Expected integer value")
        return self._val

    @property
    def as_float(self) -> float:
        "Get the floating point value"
        if not isinstance(self._val, float):
            raise TypeError("Expected floating point value")
        return self._val

    @property
    def is_list(self) -> bool:
        """Check if this node represents a list"""
        return isinstance(self._val, list)

    def __iter__(self) -> Iterator["_YamlDefaultValue"]:
        if not isinstance(self._val, list):
            raise TypeError("Expected list value")
        for item in self._val:
            # We need to wrap the value in _YamlDefaultValue to provide the same API
            yield _YamlDefaultValue(item)

    def __len__(self) -> int:
        if not isinstance(self._val, list):
            raise TypeError("Expected list value")
        return len(self._val)

    def __getitem__(self, idx: Union[int, str]) -> "_YamlDefaultValue":
        if isinstance(idx, int):
            if not isinstance(self._val, list):
                raise TypeError("Expected list value")
            # We need to wrap the value in _YamlDefaultValue to provide the same API
            return _YamlDefaultValue(self._val[idx])
        elif isinstance(idx, str):
            if not isinstance(self._val, dict):
                raise TypeError("Expected dict value")
            return _YamlDefaultValue(self._val[idx])
        else:
            raise KeyError("Key should have either type 'str' or 'int'")

    def __setitem__(self, idx: Union[int, str], val: Union[str, int, bool, float]):
        if isinstance(idx, int):
            if not isinstance(self._val, list):
                raise TypeError("Expected list value")
            self._val[idx] = val
        elif isinstance(idx, str):
            if not isinstance(self._val, dict):
                raise TypeError("Expected dict value")
            self._val[idx] = val
        else:
            raise KeyError("Key should have either type 'str' or 'int")

    def _get(self, name: str) -> Optional["_YamlDefaultValue"]:
        if not isinstance(self._val, dict):
            raise TypeError("Expected dict value")
        if name in self._val:
            return _YamlDefaultValue(self._val[name])
        return None

    def get(self, name: str, default) -> "_YamlDefaultValue":
        val = self._get(name)
        if val:
            return val
        return _YamlDefaultValue(default)

    def keys(self) -> List[str]:
        """Get all keys for this mapping"""
        if not isinstance(self._val, dict):
            raise TypeError("Expected dict value")
        return list(self._val.keys())

    def items(self) -> List[Tuple[str, "_YamlDefaultValue"]]:
        """Get all items for this mapping"""
        if not isinstance(self._val, dict):
            raise TypeError("Expected dict value")
        return [(key, _YamlDefaultValue(val)) for key, val in self._val.items()]


class YamlValue:  # pylint: disable=too-few-public-methods
    """Wrapper for yaml.Node class. It provides type-safe access to YAML nodes"""
    def __init__(self, node: Node):
        self._node = node
        if isinstance(node, ScalarNode):
            self._val = yaml_constructor.construct_object(node)
        else:
            self._val = None

    @property
    def mark(self) -> Mark:
        "Get the start mark for YAML Node"
        return self._node.start_mark

    @property
    def as_bool(self) -> bool:
        "Get the boolean value"
        if not isinstance(self._val, bool):
            raise YAMLProcessingError(f"Expected boolean value, got {type(self._val)}", self.mark)
        return self._val

    @property
    def as_str(self) -> str:
        "Get the string value"
        if not isinstance(self._val, str):
            raise YAMLProcessingError(f"Expected string value, got {type(self._val)}", self.mark)
        return self._val

    @property
    def as_int(self) -> int:
        "Get the integer value"
        if not isinstance(self._val, int):
            raise YAMLProcessingError(f"Expected integer value, got {type(self._val)}", self.mark)
        return self._val

    @property
    def as_float(self) -> float:
        "Get the floating point value"
        if not isinstance(self._val, float):
            raise YAMLProcessingError(f"Expected floating point value, got {type(self._val)}",
                                      self.mark)
        return self._val

    @property
    def is_list(self) -> bool:
        """Check if this node represents a list"""
        return isinstance(self._node, SequenceNode)

    def _get(self, name: str) -> Optional["YamlValue"]:
        "Get optional value by name"
        if not isinstance(self._node, MappingNode):
            raise YAMLProcessingError("Mapping node is expected", self.mark)
        for key, val in self._node.value:
            if key.value == name:
                return YamlValue(val)
        return None

    def get(self, name: str, default) -> Union["YamlValue", _YamlDefaultValue]:
        "Get optional value by name"
        val = self._get(name)
        if val:
            return val
        return _YamlDefaultValue(default)

    def keys(self) -> List[str]:
        """Get all keys for this mapping"""
        if not isinstance(self._node, MappingNode):
            raise YAMLProcessingError("Mapping node is expected", self.mark)
        return [key.value for key, _ in self._node.value]

    def items(self) -> List[Tuple[str, "YamlValue"]]:
        """Get all items for this mapping"""
        if not isinstance(self._node, MappingNode):
            raise YAMLProcessingError("Mapping node is expected", self.mark)
        return [(key.value, YamlValue(val)) for key, val in self._node.value]

    def __getitem__(self, idx: Union[str, int]) -> "YamlValue":
        if isinstance(idx, int):
            if not isinstance(self._node, SequenceNode):
                raise YAMLProcessingError("SequenceNode node is expected", self.mark)
            return YamlValue(self._node.value[idx])
        if isinstance(idx, str):
            val = self._get(idx)
            if not val:
                raise YAMLProcessingError(f"Key '{idx}' is mandatory", self.mark)
            return val
        raise KeyError("Key should have either type 'str' or 'int'")

    def _represent_value(self, val: Union[str, int, bool, float]) -> Node:
        representer = SafeRepresenter()
        if isinstance(val, str):
            return representer.represent_str(val)
        if isinstance(val, int):
            return representer.represent_int(val)
        if isinstance(val, bool):
            return representer.represent_bool(val)
        if isinstance(val, float):
            return representer.represent_float(val)
        raise TypeError(f"Unsupported type {type(val)}")

    def __setitem__(self, idx: Union[str, int], val: Union[str, int, bool, float]):
        # We need to make a copy of the node because yaml modules caches the nodes
        # and will ignore the new value
        if isinstance(idx, int):
            if not isinstance(self._node, SequenceNode):
                raise YAMLProcessingError("SequenceNode node is expected", self.mark)
            self._node.value[idx] = self._represent_value(val)
        elif isinstance(idx, str):
            for k, v in self._node.value:
                if k.value == idx:
                    self._node.value.remove((k, v))
            key_node = self._represent_value(idx)
            val_node = self._represent_value(val)
            self._node.value.append((key_node, val_node))
        else:
            raise KeyError("Key should have either type 'str' or 'int'")

    def __iter__(self) -> Iterator["YamlValue"]:
        for item in self._node.value:
            yield YamlValue(item)

    def __len__(self) -> int:
        return len(self._node.value)

    def __contains__(self, key: str) -> bool:
        """Test if key is present in mapping"""
        if not isinstance(self._node, MappingNode):
            raise YAMLProcessingError("Mapping node is expected", self.mark)
        return key in self.keys()

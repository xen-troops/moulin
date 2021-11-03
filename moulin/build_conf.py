# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""Defines Configuration class that holds the the whole configuration object"""

import logging
import re
from typing import List, Optional, Dict, Union, NamedTuple
from functools import partial
from packaging.version import Version

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode, Node
from moulin.yaml_helpers import get_boolean_value, get_str_value, get_mandatory_str_value, \
    get_mapping_node, YAMLProcessingError

log = logging.getLogger(__name__)


class ParameterVariant:
    "Represents possible parameter value"

    # pylint: disable=too-few-public-methods

    def __init__(self, name: str, node: MappingNode):
        self.name = name
        self.default, _ = get_boolean_value(node, "default", default=False)
        self._overrides: Optional[MappingNode] = None
        overrides_node = get_mapping_node(node, "overrides")
        if overrides_node:
            self._overrides = overrides_node

    def apply_overrides(self, node: MappingNode):
        "Apply variant overrides to a mapping node"
        if self._overrides:
            self._override(node, self._overrides)

    @staticmethod
    def _override(remote_node: Node, local_node: Node):
        # pylint: disable=unidiomatic-typecheck
        if type(remote_node) != type(local_node):
            raise YAMLProcessingError(
                f"Incompatible types {type(remote_node)} and " +
                f" {type(local_node)} while trying to apply overrides", local_node.start_mark)
        if isinstance(remote_node, MappingNode):
            for lname, lval in local_node.value:
                for i, rentry in enumerate(remote_node.value):
                    if rentry[0].value == lname.value:
                        if isinstance(rentry[1], ScalarNode):
                            remote_node.value[i] = (lname, lval)
                        else:
                            ParameterVariant._override(rentry[1], lval)
                        break
                else:
                    remote_node.value.append((lname, lval))
        elif isinstance(remote_node, SequenceNode):
            remote_node.value.extend(local_node.value)
        else:
            raise YAMLProcessingError(f"Unknown node type f{type(remote_node)}",
                                      remote_node.start_mark)


class Parameter:
    "Represents parametrization option"

    # pylint: disable=too-few-public-methods

    def __init__(self, name: str, node: MappingNode):
        self.name = name
        self.desc, _ = get_mandatory_str_value(node, "desc")

        self.variants: Dict[str, ParameterVariant] = {}
        vname: Node
        vnode: Node
        for vname, vnode in node.value:
            if not isinstance(vname, ScalarNode) or not isinstance(vname.value, str):
                raise YAMLProcessingError("Variant name is expected to be string", vname.start_mark)
            if vname.value == "desc":
                continue
            if not isinstance(vnode, MappingNode):
                raise YAMLProcessingError("Variant definition is expected to be a dict",
                                          vnode.start_mark)
            self.variants[vname.value] = ParameterVariant(vname.value, vnode)

        self.default: Optional[ParameterVariant] = None
        for variant in self.variants.values():
            if variant.default:
                self.default = variant
                break

    def apply_overrides(self, node: MappingNode, variant_name: str):
        "Apply given variant to a mapping node"

        self.variants[variant_name].apply_overrides(node)


escaped_percent = re.compile(r"(%%)")
variable_re = re.compile(r"%\{(\w[\w\d\-]*)\}")


class VariableRef(NamedTuple):
    "Represents variable reference"
    name: str


class Variable(NamedTuple):
    "Represents variable"
    name: str
    tokens: List[Union[str, VariableRef]]
    mark: yaml.Mark


class ExpandedVariable(NamedTuple):
    "Represents expanded variable"
    name: str
    value: str
    mark: yaml.Mark


class MoulinConfiguration:
    "This class holds the whole build configuration"

    def __init__(self, node: MappingNode):
        self._node = node

        min_ver, _ = get_str_value(node, "min_ver")
        if not min_ver:
            self.min_ver = None
        else:
            self.min_ver = Version(min_ver)

        self.desc, _ = get_mandatory_str_value(node, "desc")

        parameters_node = get_mapping_node(node, "parameters")
        self._params: Dict[str, Parameter] = {}
        if parameters_node:
            self._read_params(parameters_node)

        self._variables: Dict[str, ExpandedVariable] = {}

    def _read_params(self, node: MappingNode):
        pname: Node
        pnode: Node
        for pname, pnode in node.value:
            if not isinstance(pname, ScalarNode) or not isinstance(pname.value, str):
                raise YAMLProcessingError("Parameter node is expected to be string",
                                          pname.start_mark)
            if not isinstance(pnode, MappingNode):
                raise YAMLProcessingError("Parameter variants is expected to be a dict",
                                          pnode.start_mark)
            self._params[pname.value] = Parameter(pname.value, pnode)

    def get_parameters(self):
        "Return available parameters"
        return self._params

    def _prepare_variables(self):
        variables_node = get_mapping_node(self._node, "variables")
        variables: Dict[str, Variable] = {}
        if not variables_node:
            return
        for vname_node, vval_node in variables_node.value:
            if not isinstance(vname_node, ScalarNode) or not isinstance(vname_node.value, str):
                raise YAMLProcessingError("Variable name is expected to be string",
                                          vname_node.start_mark)
            if not isinstance(vval_node, ScalarNode) or not isinstance(vval_node.value, str):
                raise YAMLProcessingError("Variable value is expected to be string",
                                          vval_node.start_mark)
            vname = vname_node.value
            variables[vname] = Variable(vname, _tokenize(vval_node.value), vname_node.start_mark)
            # Sanity check
            for token in variables[vname].tokens:
                if isinstance(token, VariableRef):
                    if token.name == vname:
                        raise YAMLProcessingError(f"Variable {vname} refers to self",
                                                  vname.start_mark)
        self._variables = _try_to_expand_variables(variables)

    def complete_init(self, options):
        "Complete object initialization with given options"
        if options:
            log.info("Completing setup with following parameters:")
        for param_name, param_value in options.items():
            log.info("  %s: %s", param_name, param_value)
            self._params[param_name].apply_overrides(self._node, param_value)

        log.debug("Expanding variables...")
        self._prepare_variables()
        for var in self._variables.values():
            log.debug("  %s = %s", var.name, var.value)

        log.debug("Substituting variables...")
        _traverse_tree(self._node, partial(_substitute_variables, variables=self._variables))

        log.debug("Cleaning up config...")
        # Drop 'variables' and 'parameters'
        self._node.value = list(
            filter(lambda x: x[0].value not in ["variables", "parameters"], self._node.value))

    def dumps(self):
        "Return processed YAML stream"
        return yaml.serialize(self._node)

    def get_root_node(self):
        "Return root YAML node"
        return self._node


#
# Variable processing helpers.
#


def _extract_refs(string: str) -> List[Union[str, VariableRef]]:
    ret: List[Union[str, VariableRef]] = []
    for i, part in enumerate(variable_re.split(string)):
        # Even (zero-based) entries are just strings
        # Odd entries are variable references
        if i % 2 == 0 and part:
            ret.append(part)
        elif part:
            ret.append(VariableRef(part))
    return ret


def _tokenize(string: str) -> List[Union[str, VariableRef]]:
    ret: List[Union[str, VariableRef]] = []
    for part in escaped_percent.split(string):
        if part:
            if escaped_percent.fullmatch(part):
                ret.append("%%")
            else:
                ret.extend(_extract_refs(part))
    return ret


def _map_token(token: Union[str, VariableRef], variables: Dict[str, ExpandedVariable],
               mark: yaml.Mark):
    if isinstance(token, str):
        return token
    if isinstance(token, VariableRef):
        name = token.name
        if name not in variables:
            return token
        return variables[name].value
    raise YAMLProcessingError(f"Unexptected token of type '{type(token)}'", mark)


def _contains_ref(tokens):
    for token in tokens:
        if isinstance(token, VariableRef):
            return True
    return False


def _list_compare(list1, list2):
    "Compare contents of lists, not list object themselves"
    if len(list1) != len(list2):
        return False
    for i, j in zip(list1, list2):
        if i != j:
            return False
    return True


def _try_to_expand_variables(variables: Dict[str, Variable]) -> Dict[str, ExpandedVariable]:
    # This is not most effective way. But it is good enough. Iterate
    # over all variables, trying to expand one of them
    expanded_variables: Dict[str, ExpandedVariable] = {}
    stop = False
    while not stop:
        stop = True
        for key, var in variables.items():
            new_tokens = list(
                map(partial(_map_token, variables=expanded_variables, mark=var.mark), var.tokens))
            if not _contains_ref(new_tokens):
                expanded_variables[key] = ExpandedVariable(var.name, "".join(new_tokens), var.mark)
                del variables[key]
                stop = False
                break
            if not _list_compare(var.tokens, new_tokens):
                variables[key] = Variable(var.name, new_tokens, var.mark)

    # We can't expand more variables. Either all are expanded, or
    # there is a some user error. Perform sanity check.
    for var in variables.values():
        for token in var.tokens:
            if isinstance(token, VariableRef):
                if token.name == var.name:
                    raise YAMLProcessingError(f"Variable {var.name} indirectly refers to self",
                                              var.mark)
                if token.name not in variables:
                    raise YAMLProcessingError(
                        f"Variable {var.name} refers to unknown variable {token.name}", var.mark)
    if variables:
        raise Exception(f"Found circular dependency in variables {list(variables.keys())}")

    return expanded_variables


def _substitute_variables(node: ScalarNode, variables: Dict[str, ExpandedVariable]):
    if not isinstance(node.value, str):
        return
    tokens = _tokenize(node.value)
    tokens = list(map(partial(_map_token, variables=variables, mark=node.start_mark), tokens))
    for token in tokens:
        if isinstance(token, VariableRef):
            raise YAMLProcessingError(f"Reference to unknown variable {token.name}",
                                      node.start_mark)
    node.value = "".join(tokens)  # type: ignore # there are only strings left in tokens


def _traverse_tree(node, fn):
    # pylint: disable=invalid-name
    if isinstance(node, MappingNode):
        for name, val in node.value:
            _traverse_tree(name, fn)
            _traverse_tree(val, fn)
    elif isinstance(node, SequenceNode):
        for subnode in node.value:
            _traverse_tree(subnode, fn)
    elif isinstance(node, ScalarNode):
        fn(node)
    else:
        raise YAMLProcessingError(f"Unknown node type {type(node)}", node.start_mark)

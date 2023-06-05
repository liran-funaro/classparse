"""
Author: Liran Funaro <liran.funaro@gmail.com>

Copyright (c) 2023-2023, Liran Funaro.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the
   names of its contributors may be used to endorse or promote products
   derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
"""
import argparse
import dataclasses
from typing import Any, Dict, Generic, Iterator, List, Optional, Type, TypeVar, Union

from classparse import docs
from classparse.types import update_field_type

NO_ARG = "__no_arg__"
POS_ARG = "__pos_arg__"
NAME_OR_FLAG = "__name_or_flag__"


def to_arg_name(name: str) -> str:
    """Convert a valid variable name to an argument name"""
    return name.replace("_", "-")


def to_var_name(name: str) -> str:
    """Convert a valid argument name to an variable name"""
    return name.replace("-", "_")


def _set_nested(dct: Dict[str, Any], flat_key: str, value: Any):
    *internal_keys, last_key = flat_key.split(".")
    for k in internal_keys:
        dct = dct.setdefault(k, {})
    dct[last_key] = value


def to_nested_dict(dct: Dict[str, Any]) -> Dict[str, Any]:
    """Converts flat named dict to a nested dict"""
    ret_dct: Dict[str, Any] = {}
    for key, value in dct.items():
        _set_nested(ret_dct, key, value)
    return ret_dct


def namespace_to_vars(namespace) -> Dict[str, Any]:
    """
    Convert a dict with argument key notation (dash word separation)
    to variable key notation (underscore word separation).
    Then converts it from flat named dict to a nested dict.
    """
    if not isinstance(namespace, dict):
        namespace = vars(namespace)
    namespace = {to_var_name(k): v for k, v in namespace.items()}
    return to_nested_dict(namespace)


def _add_prefix(arg_name: str, prefix: Optional[List[str]] = None):
    if not prefix:
        return arg_name
    return ".".join((*prefix, arg_name))


def _name_or_flags_arg(
    arg_name: str,
    name_or_flag: Optional[List[str]] = None,
    positional: bool = False,
    prefix: Optional[List[str]] = None,
) -> List[str]:
    arg_name = to_arg_name(_add_prefix(arg_name, prefix))
    if positional:
        assert name_or_flag is None, "Flag is not supported for positional argument"
        return [arg_name]
    if name_or_flag is None:
        name_or_flag = []
    return [f"--{arg_name}", *name_or_flag]


_T = TypeVar("_T", bound=object)
InstanceOrClass = Union[Type[_T], _T]


@dataclasses.dataclass
class FieldDescriptor(Generic[_T]):
    """Describes a dataclass field"""

    name: str
    kwargs: Dict[str, Any]
    is_arg: bool = False
    type: Any = None
    default: Any = None
    args: Optional[List[str]] = None
    sub_analyzer: Optional["DataclassFieldAnalyzer[_T]"] = None


class DataclassFieldAnalyzer(Generic[_T]):
    """Analyzes a dataclass and its fields"""

    def __init__(
        self,
        instance_or_cls: InstanceOrClass[_T],
        default_argument_args: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        arg_prefix: Optional[List[str]] = None,
    ):
        if not dataclasses.is_dataclass(instance_or_cls):
            raise TypeError("Cannot operate on a non-dataclass object.")

        self.cls = instance_or_cls if isinstance(instance_or_cls, type) else type(instance_or_cls)
        self.default_argument_args = default_argument_args or {}
        self.arg_prefix = arg_prefix or []
        self.description = description
        if self.description is None:
            self.description = self.cls.__doc__

        class_docs = docs.get_argument_docs(self.cls)
        self.field_desc: Dict[str, FieldDescriptor] = {
            field.name: self._make_field_descriptor(field, class_docs.get(field.name, None))
            for field in dataclasses.fields(self.cls)
        }

        self.class_default_vars = {field.name: field.default for field in self.field_desc.values()}
        self.all_types = {field.name: field.type for field in self.field_desc.values()}

    def _iter_sub_analyzers_fields(self):
        for field in self.field_desc.values():
            if field.sub_analyzer is not None:
                yield field

    def _iter_arg_fields(self):
        for field in self.field_desc.values():
            if field.is_arg:
                yield field

    def iter_flatten_fields(self) -> Iterator[str]:
        """Iterate over all the fields and subfields of nested classes"""
        yield from self.field_desc.keys()
        for field in self._iter_sub_analyzers_fields():
            yield from (f"{field.name}.{k}" for k in field.sub_analyzer.iter_flatten_fields())

    def _make_field_descriptor(self, field: dataclasses.Field, field_doc: Optional[str]) -> FieldDescriptor[_T]:
        desc: FieldDescriptor[_T] = FieldDescriptor(field.name, dict(self.default_argument_args))
        metadata_kwargs = dict(field.metadata)
        desc.is_arg = not metadata_kwargs.pop(NO_ARG, False)
        is_explicit_positional = metadata_kwargs.pop(POS_ARG, False)
        name_or_flag = metadata_kwargs.pop(NAME_OR_FLAG, None)
        has_default = field.default is not dataclasses.MISSING or field.default_factory is not dataclasses.MISSING
        is_positional = is_explicit_positional or not has_default

        # Type precedence: field.metadata, field.type
        metadata_kwargs.setdefault("type", field.type)

        # Help precedence: field.metadata, field_doc
        if field_doc is not None:
            metadata_kwargs.setdefault("help", field_doc)

        # Default precedence: override default (later), field.default(_factory), field.metadata
        if field.default is not dataclasses.MISSING:
            metadata_kwargs["default"] = field.default
        if field.default_factory is not dataclasses.MISSING:
            metadata_kwargs["default"] = field.default_factory()

        # Store default before updating type, because it may change an Enum default to string for readability
        desc.default = metadata_kwargs.get("default", None)
        desc.type = metadata_kwargs.get("type", None)

        if not dataclasses.is_dataclass(desc.type):
            # Regular type
            desc.type = update_field_type(metadata_kwargs)
            desc.args = _name_or_flags_arg(desc.name, name_or_flag, is_positional, self.arg_prefix)
        else:
            # Nested dataclass
            assert not is_explicit_positional, f"Nested dataclass field '{desc.name}' cannot be positional."
            assert name_or_flag is None, f"Nested dataclass field '{desc.name}' cannot have additional names or flags."
            desc.sub_analyzer = DataclassFieldAnalyzer(
                desc.type,
                default_argument_args=self.default_argument_args,
                description=metadata_kwargs.get("help", None),
                arg_prefix=[*self.arg_prefix, field.name],
            )
            desc.type = desc.sub_analyzer.all_types
            if desc.default is not None:
                desc.default = desc.sub_analyzer.get_vars(desc.default)

        # Keyword arguments precedence: type updates, field.metadata or overrides, default_argument_args
        desc.kwargs.update(metadata_kwargs)
        return desc

    def is_cls(self, instance_or_cls: Optional[InstanceOrClass[_T]] = None):
        """Returns True if the input is None or the analyzed class (not an instance)"""
        return instance_or_cls is None or instance_or_cls is self.cls

    def get_vars(self, instance_or_cls=None) -> Dict[str, Any]:
        """See `DataclassParser.get_vars()`"""
        if self.is_cls(instance_or_cls):
            return dict(self.class_default_vars)
        assert dataclasses.is_dataclass(instance_or_cls)
        return dataclasses.asdict(instance_or_cls)

    def _fetch_defaults(self, instance_or_cls=None) -> Dict[str, Any]:
        if dataclasses.is_dataclass(instance_or_cls):
            return self.get_vars(instance_or_cls)
        if isinstance(instance_or_cls, dict):
            return instance_or_cls

        assert instance_or_cls is None
        return {}

    def add_all_arguments(
        self,
        instance_or_cls,
        parser: argparse.ArgumentParser,
        group=None,
    ):
        """Add all dataclass arguments to a parser."""
        if group is None:
            group = parser
        default_values = self._fetch_defaults(instance_or_cls)
        for field in self._iter_arg_fields():
            kwargs = field.kwargs
            if field.name in default_values:
                kwargs = dict(kwargs, default=default_values[field.name])
            if field.sub_analyzer is not None:
                sub_group = parser.add_argument_group(
                    title=to_arg_name(field.name), description=field.sub_analyzer.description
                )
                field.sub_analyzer.add_all_arguments(kwargs.get("default", None), parser, sub_group)
            else:
                group.add_argument(*field.args, **kwargs)

    def transform(self, instance_or_cls, namespace: Any):
        """Transforms an input object into the analyzed dataclass"""
        values = self.get_vars(instance_or_cls)
        values.update({k: v for k, v in namespace_to_vars(namespace).items() if k in self.field_desc})
        for field in self._iter_sub_analyzers_fields():
            value = values.get(field.name, None)
            if isinstance(value, dict):
                values[field.name] = field.sub_analyzer.transform(field.kwargs.get("default", None), value)
        return self.cls(**values)

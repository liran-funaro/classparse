"""
Declarative `ArgumentParser` definition with `dataclass` notation.

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
import functools
import typing
from types import MethodType
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

import yaml

from classparse import docs
from classparse.types import obj_to_yaml_dict, to_nested_dict, update_field_type, yaml_dict_to_obj

__version__ = "0.1.4"
NO_ARG = "__no_arg__"
POS_ARG = "__pos_arg__"
LOAD_DEFAULTS_FILED = "load_defaults"


def arg(*name_or_flag, default=None, **metadata):
    """
    Allow adding parameters to a named argument.
    See `argparse.add_argument()`.
    """
    if len(name_or_flag) > 0:
        metadata.update(name_or_flag=name_or_flag)
    return dataclasses.field(default=default, metadata=metadata)


def pos_arg(default=dataclasses.MISSING, **metadata):
    """
    Allow adding parameters to a positional argument.
    See `argparse.add_argument()`.
    """
    return dataclasses.field(default=default, metadata={POS_ARG: True, **metadata})


def no_arg(default=None, **kwargs):
    """Set dataclass field as non argparse argument"""
    metadata = kwargs.setdefault("metadata", {})
    metadata[NO_ARG] = True
    return dataclasses.field(default=default, **kwargs)


def to_arg_name(name: str) -> str:
    """Convert a valid variable name to an argument name"""
    return name.replace("_", "-")


def to_var_name(name: str) -> str:
    """Convert a valid argument name to an variable name"""
    return name.replace("-", "_")


def namespace_to_vars(namespace) -> Dict[str, Any]:
    if not isinstance(namespace, dict):
        namespace = vars(namespace)
    namespace = {to_var_name(k): v for k, v in namespace.items()}
    return to_nested_dict(namespace)


def asdict(values) -> Dict[str, Any]:
    if not isinstance(values, dict):
        return values
    return {to_arg_name(k): asdict(v) for k, v in values.items()}


def _name_or_flags_arg(
    arg_name: str, name_or_flag: Optional[List[str]] = None, positional: bool = False, prefix: Optional[str] = None
) -> Iterable[str]:
    if prefix is not None:
        arg_name = prefix + arg_name
    arg_name = to_arg_name(arg_name)
    if positional:
        assert name_or_flag is None, "Flag is not supported for positional argument"
        return [arg_name]
    if name_or_flag is None:
        name_or_flag = []
    return [f"--{arg_name}", *name_or_flag]


def _add_load_defaults_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        *_name_or_flags_arg(LOAD_DEFAULTS_FILED),
        metavar="PATH",
        type=argparse.FileType("r"),
        default=None,
        help="A YAML file path that overrides the default values.",
    )


T = TypeVar("T")


class DataclassParser(Protocol[T]):  # pragma: no cover
    def __new__(cls) -> Union["DataclassParser[T]", T]:
        ...

    @classmethod
    def get_vars(cls) -> Dict[str, Any]:
        ...

    @classmethod
    def asdict(cls) -> Dict[str, Any]:
        ...

    @classmethod
    def from_dict(cls, namespace: Any) -> Union["DataclassParser[T]", T]:
        ...

    @classmethod
    def dump_yaml(cls, stream=None, sort_keys=False, **kwargs) -> Optional[str]:
        ...

    @classmethod
    def load_yaml(cls, stream) -> Union["DataclassParser[T]", T]:
        ...

    @classmethod
    def get_parser(cls) -> argparse.ArgumentParser:
        ...

    @classmethod
    def format_help(cls) -> str:
        ...

    @classmethod
    def format_usage(cls) -> str:
        ...

    @classmethod
    def print_help(cls, file=None):
        ...

    @classmethod
    def print_usage(cls, file=None):
        ...

    @classmethod
    def parse_args(cls, args: Optional[Sequence[str]] = None) -> Union["DataclassParser[T]", T]:
        ...

    @classmethod
    def parse_intermixed_args(cls, args: Optional[Sequence[str]] = None) -> Union["DataclassParser[T]", T]:
        ...

    @classmethod
    def parse_known_args(cls, args: Optional[Sequence[str]] = None) -> Tuple[Union["DataclassParser[T]", T], List[str]]:
        ...

    @classmethod
    def parse_known_intermixed_args(
        cls, args: Optional[Sequence[str]] = None
    ) -> Tuple[Union["DataclassParser[T]", T], List[str]]:
        ...


DataClass = TypeVar("DataClass")


class DataclassNamespace:
    def __init__(self, known_fields):
        self.__known_fields__ = known_fields

    def __getattribute__(self, key):
        key = to_var_name(key)

        # First, we try to return the real attribute field
        try:
            return super().__getattribute__(key)
        except AttributeError as e:
            attribute_error = e

        if key in self.__known_fields__:
            # We return a value so `hasattr()` will return True for all known fields.
            # This supress the automatic assignments of default values.
            # We need it so we can later discover if a value was actually assigned by the user.
            return None
        else:
            raise attribute_error

    def __setattr__(self, key, value):
        super().__setattr__(to_var_name(key), value)

    def __repr__(self):
        kvs = ", ".join(f"{k}={repr(v)}" for k, v in vars(self).items() if k != "__known_fields__")
        return f"{self.__class__.__name__}({kvs})"


class DataclassParserMaker(Generic[DataClass]):
    InstanceOrCls = Union[Type[DataClass], DataClass]
    DataClassWithParser = Union[DataclassParser[DataClass], DataClass]

    def __init__(
        self,
        instance_or_cls: InstanceOrCls,
        default_argument_args=None,
        load_defaults_from_file=False,
        arg_prefix=None,
        **parser_args,
    ):
        if not dataclasses.is_dataclass(instance_or_cls):
            raise TypeError("Cannot operate on a non-dataclass object.")

        if isinstance(instance_or_cls, type):
            self.cls = instance_or_cls
        else:
            self.cls = type(instance_or_cls)

        self.default_argument_args = default_argument_args or {}
        self.load_defaults_from_file = bool(load_defaults_from_file)
        self.arg_prefix = arg_prefix

        self.parser_args = parser_args
        if self.parser_args.get("description", None) is None:
            self.parser_args["description"] = self.cls.__doc__

        self.docs = docs.get_argument_docs(self.cls)
        self.args: Dict[str, Tuple[Union[List[str], DataclassParserMaker], Dict[str, Any]]] = {}
        self.class_default_vars = {}
        self.all_types = {}
        self.fields = set()

        for field in dataclasses.fields(self.cls):
            self._add_argument_from_field(field)

        self.flat_fields = set(self._flatten_fields())
        self.main_parser = self.make()

    def _flatten_fields(self) -> Set[str]:
        yield from self.fields
        for name, (sub_maker, _) in self.args.items():
            if isinstance(sub_maker, DataclassParserMaker):
                for k in sub_maker.flat_fields:
                    yield f"{name}.{k}"

    def _add_argument_from_field(self, field: dataclasses.Field):
        self.fields.add(field.name)

        metadata_kwargs = dict(field.metadata)
        is_no_arg = metadata_kwargs.pop(NO_ARG, False)
        name_or_flag = metadata_kwargs.pop("name_or_flag", None)
        is_explicit_positional = metadata_kwargs.pop(POS_ARG, False)
        has_default = field.default is not dataclasses.MISSING
        is_positional = is_explicit_positional or not has_default

        # Type precedence: field.metadata, field.type
        metadata_kwargs.setdefault("type", field.type)

        # Help precedence: field.metadata, field_doc
        field_doc = self.docs.get(field.name, None)
        if field_doc is not None:
            metadata_kwargs.setdefault("help", field_doc)

        # Default precedence: override_default, field.default, field.metadata
        if has_default:
            metadata_kwargs["default"] = field.default

        # Arguments precedence: field.metadata/overrides, default_argument_args
        kwargs = dict(self.default_argument_args)
        kwargs.update(metadata_kwargs)

        # Store default before updating type, which may change an Enum default to string for readability
        self.class_default_vars[field.name] = kwargs.get("default", None)

        if not dataclasses.is_dataclass(kwargs.get("type", None)):
            # Fix field type to work well with argparse
            update_field_type(kwargs)
            self.all_types[field.name] = kwargs.get("type", None)
            if not is_no_arg:
                args = list(_name_or_flags_arg(field.name, name_or_flag, is_positional, self.arg_prefix))
                self.args[field.name] = (args, kwargs)
        else:
            cur_type = kwargs["type"]
            assert not is_explicit_positional, f"Nested class '{cur_type}' cannot be positional."
            assert name_or_flag is None, f"Nested class '{cur_type}' cannot have additional names or flags."
            arg_prefix = f"{field.name}."
            if self.arg_prefix is not None:
                arg_prefix = self.arg_prefix + arg_prefix
            sub_maker = DataclassParserMaker(
                cur_type,
                default_argument_args=self.default_argument_args,
                load_defaults_from_file=False,
                arg_prefix=arg_prefix,
                title=to_arg_name(field.name),
                description=metadata_kwargs.get("help", None),
            )
            self.all_types[field.name] = sub_maker.all_types
            cur_default = metadata_kwargs.get("default", None)
            if cur_default is not None:
                self.class_default_vars[field.name] = sub_maker.get_vars(cur_default)
            if not is_no_arg:
                self.args[field.name] = (sub_maker, kwargs)

    def make(
        self,
        instance_or_cls: Optional[Union[InstanceOrCls, Dict[str, Any]]] = None,
        parent_parser: Optional[argparse.ArgumentParser] = None,
    ) -> argparse.ArgumentParser:
        if dataclasses.is_dataclass(instance_or_cls):
            default_values = self.get_vars(instance_or_cls)
        elif isinstance(instance_or_cls, dict):
            default_values = instance_or_cls
        else:
            assert instance_or_cls is None, f"{instance_or_cls}"
            default_values = {}

        if parent_parser is None:
            parser = argparse.ArgumentParser(**{k: v for k, v in self.parser_args.items() if k != "title"})
            parent_parser = parser
        else:
            parser = parent_parser.add_argument_group(**self.parser_args)

        if self.load_defaults_from_file:
            _add_load_defaults_arg(parser)

        for name, (args, kwargs) in self.args.items():
            if name in default_values:
                kwargs = dict(kwargs, default=default_values[name])
            if isinstance(args, DataclassParserMaker):
                args.make(kwargs.get("default", None), parent_parser)
            else:
                parser.add_argument(*args, **kwargs)

        return parser

    def _is_cls(self, instance_or_cls: Optional[InstanceOrCls] = None):
        return instance_or_cls is None or instance_or_cls is self.cls

    def parse_load_defaults(self, instance_or_cls: Optional[InstanceOrCls] = None, args=None):
        if not self.load_defaults_from_file:
            return instance_or_cls

        parser = argparse.ArgumentParser(add_help=False)
        _add_load_defaults_arg(parser)

        try:
            namespace, _ = parser.parse_known_args(args=args)
        except Exception or SystemExit:
            return instance_or_cls

        load_defaults = getattr(namespace, LOAD_DEFAULTS_FILED, None)
        if load_defaults is None:
            return instance_or_cls

        return self.load_yaml(instance_or_cls, load_defaults)

    def get_vars(self, instance_or_cls: Optional[InstanceOrCls] = None) -> Dict[str, Any]:
        if self._is_cls(instance_or_cls):
            return dict(self.class_default_vars)
        else:
            return dataclasses.asdict(instance_or_cls)

    def asdict(self, instance_or_cls: Optional[InstanceOrCls] = None) -> Dict[str, Any]:
        return asdict(self.get_vars(instance_or_cls))

    def from_dict(self, instance_or_cls: Optional[InstanceOrCls], namespace: Any) -> DataClassWithParser:
        values = self.get_vars(instance_or_cls)
        values.update({k: v for k, v in namespace_to_vars(namespace).items() if k in self.fields})
        for k, v in values.items():
            if k not in self.args:
                continue
            sub_maker, kwargs = self.args[k]
            if isinstance(v, dict) and isinstance(sub_maker, DataclassParserMaker):
                values[k] = sub_maker.from_dict(kwargs.get("default", None), v)
        return self.cls(**values)

    def dump_yaml(self, instance_or_cls: Optional[InstanceOrCls] = None, stream=None, sort_keys=False, **kwargs) -> str:
        cur_vars = self.get_vars(instance_or_cls)
        cur_vars = obj_to_yaml_dict(cur_vars)
        return yaml.safe_dump(cur_vars, stream=stream, sort_keys=sort_keys, **kwargs)

    def load_yaml(self, instance_or_cls: Optional[InstanceOrCls], stream) -> DataClassWithParser:
        loaded_vars = yaml.safe_load(stream)
        loaded_vars = yaml_dict_to_obj(loaded_vars, self.all_types)
        return self.from_dict(instance_or_cls, loaded_vars)

    def _get_parser(self, instance_or_cls: Optional[InstanceOrCls] = None) -> argparse.ArgumentParser:
        if self._is_cls(instance_or_cls):
            return self.main_parser
        else:
            return self.make(instance_or_cls)

    def _get_parser_with_defaults(
        self, instance_or_cls: Optional[InstanceOrCls] = None, args: Optional[Sequence[str]] = None
    ) -> [Optional[InstanceOrCls], DataclassNamespace, argparse.ArgumentParser]:
        instance_or_cls = self.parse_load_defaults(instance_or_cls, args)
        return instance_or_cls, DataclassNamespace(self.flat_fields), self._get_parser(instance_or_cls)

    def get_parser(self, instance_or_cls: Optional[InstanceOrCls] = None) -> argparse.ArgumentParser:
        return self.make(instance_or_cls)

    def format_help(self, instance_or_cls: Optional[InstanceOrCls] = None) -> str:
        return self._get_parser(instance_or_cls).format_help()

    def format_usage(self, instance_or_cls: Optional[InstanceOrCls] = None) -> str:
        return self._get_parser(instance_or_cls).format_usage()

    def print_help(self, instance_or_cls: Optional[InstanceOrCls] = None, file=None):
        return self._get_parser(instance_or_cls).print_help(file)

    def print_usage(self, instance_or_cls: Optional[InstanceOrCls] = None, file=None):
        return self._get_parser(instance_or_cls).print_usage(file)

    def parse_args(
        self, instance_or_cls: Optional[InstanceOrCls] = None, args: Optional[Sequence[str]] = None
    ) -> DataClassWithParser:
        instance_or_cls, namespace, parser = self._get_parser_with_defaults(instance_or_cls, args)
        parser.parse_args(args=args, namespace=namespace)
        return self.from_dict(instance_or_cls, namespace)

    def parse_intermixed_args(
        self, instance_or_cls: Optional[InstanceOrCls] = None, args: Optional[Sequence[str]] = None
    ) -> DataClassWithParser:
        instance_or_cls, namespace, parser = self._get_parser_with_defaults(instance_or_cls, args)
        parser.parse_intermixed_args(args=args, namespace=namespace)
        return self.from_dict(instance_or_cls, namespace)

    def parse_known_args(
        self, instance_or_cls: Optional[InstanceOrCls] = None, args: Optional[Sequence[str]] = None
    ) -> Tuple[DataClassWithParser, List[str]]:
        instance_or_cls, namespace, parser = self._get_parser_with_defaults(instance_or_cls, args)
        _, args = parser.parse_known_args(args=args, namespace=namespace)
        return self.from_dict(instance_or_cls, namespace), args

    def parse_known_intermixed_args(
        self, instance_or_cls: Optional[InstanceOrCls] = None, args: Optional[Sequence[str]] = None
    ) -> Tuple[DataClassWithParser, List[str]]:
        instance_or_cls, namespace, parser = self._get_parser_with_defaults(instance_or_cls, args)
        _, args = parser.parse_known_intermixed_args(args=args, namespace=namespace)
        return self.from_dict(instance_or_cls, namespace), args


def make_parser(
    instance_or_cls: Union[Type[DataClass], DataClass], default_argument_args=None, **parser_args
) -> argparse.ArgumentParser:
    return DataclassParserMaker(instance_or_cls, default_argument_args, **parser_args).main_parser


def parse_to(
    instance_or_cls: Union[Type[DataClass], DataClass], args=None, default_argument_args: dict = None, **parser_args
) -> Union[DataclassParser[DataClass], DataClass]:
    """Parse arguments to a dataclass"""
    parser_maker = DataclassParserMaker(instance_or_cls, default_argument_args=default_argument_args, **parser_args)
    return parser_maker.parse_args(instance_or_cls, args=args)


class ClassOrInstanceMethod:
    def __init__(self, f):
        self.f = f
        functools.update_wrapper(self, f)

    def __get__(self, obj, cls=None):
        return MethodType(self.f, obj if obj is not None else cls)


_dataclass_parser_methods: Tuple[str] = tuple(
    method_name for method_name in dir(DataclassParser) if not method_name.startswith("_")
)


def _transform_dataclass_parser(
    cls: Type[DataClass], /, kwargs: Dict[str, Any] = None
) -> Union[Type[DataclassParser[DataClass]], Type[DataClass]]:
    """Decorator that adds `DataclassParser` methods to the dataclass"""
    kwargs = kwargs or {}
    parser_maker = DataclassParserMaker(cls, **kwargs)
    for method_name in _dataclass_parser_methods:
        setattr(cls, method_name, ClassOrInstanceMethod(getattr(parser_maker, method_name)))
    return cls


K = TypeVar("K")


@typing.overload
def classparser(
    default_argument_args=None, load_defaults_from_file=False, **parser_args
) -> Callable[[Type[K]], Union[Type[DataclassParser[K]], Type[K]]]:
    ...  # pragma: no cover


@typing.overload
def classparser(cls: Type[DataClass]) -> Union[Type[DataclassParser[DataClass]], Type[DataClass]]:
    ...  # pragma: no cover


def classparser(cls=None, /, **kwargs):
    """Decorator that adds `DataclassParser` methods to the dataclass"""
    if cls is None:
        # The method is called with parentheses: @classparser().
        return functools.partial(_transform_dataclass_parser, kwargs=kwargs)
    else:
        # The method is called without parentheses: @classparser.
        return _transform_dataclass_parser(cls, kwargs)

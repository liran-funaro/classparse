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
    Tuple,
    Type,
    TypeVar,
    Union,
)

import yaml

from classparse import docs
from classparse.types import _obj_to_yaml_dict, _update_field_type, _yaml_dict_to_obj

__version__ = "0.1.4"
NO_ARG = "__no_arg__"
POS_ARG = "__pos_arg__"


def arg(flag=None, default=None, **metadata):
    """
    Allow adding parameters to a named argument.
    See `argparse.add_argument()`.
    """
    if flag is not None:
        metadata.update(flag=flag)
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


def _name_or_flags_arg(arg_name: str, flag: Optional[str] = None, positional: bool = False) -> Iterable[str]:
    arg_name = to_arg_name(arg_name)
    if positional:
        assert flag is None, "Flag is not supported for positional argument"
        return [arg_name]
    return filter(None, [flag, f"--{arg_name}"])


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
    def from_dict(cls, namespace: Dict[str, Any]) -> Union["DataclassParser[T]", T]:
        ...

    @classmethod
    def dump_yaml(cls, stream=None, **kwargs) -> Optional[str]:
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


class DataclassParserMaker(Generic[DataClass]):
    def __init__(self, instance_or_cls: Union[Type[DataClass], DataClass], default_argument_args=None, **parser_args):
        if not dataclasses.is_dataclass(instance_or_cls):
            raise TypeError("Cannot operate on a non-dataclass object.")

        if isinstance(instance_or_cls, type):
            self.cls = instance_or_cls
        else:
            self.cls = type(instance_or_cls)

        if default_argument_args is None:
            default_argument_args = {}
        self.default_argument_args = default_argument_args

        parser_args.setdefault("description", self.cls.__doc__)
        self.parser_args = parser_args

        self.docs = docs.get_argument_docs(self.cls)
        self.args = []

        for field in dataclasses.fields(self.cls):
            self._add_argument_from_field(field)

        self.all_types = self._get_all_kwarg("type")
        self.all_defaults = self._get_all_kwarg("default")
        self.main_parser = self.make()

    def _get_all_kwarg(self, arg_name):
        return {name: kwargs.get(arg_name, None) for name, _, kwargs in self.args}

    def _add_argument_from_field(self, field: dataclasses.Field):
        # Arguments precedence: field.metadata, default_argument_args
        kwargs = dict(self.default_argument_args)
        kwargs.update(field.metadata)
        is_no_arg = kwargs.pop(NO_ARG, False)
        if is_no_arg:
            return

        flag = kwargs.pop("flag", None)
        has_default = field.default is not dataclasses.MISSING
        is_positional = kwargs.pop(POS_ARG, False) or not has_default
        args = list(_name_or_flags_arg(field.name, flag, is_positional))

        # Type precedence: field.metadata, field.type, default_argument_args
        if "type" not in field.metadata:
            kwargs["type"] = field.type

        # Help precedence: field.metadata, field_doc, default_argument_args
        field_doc = self.docs.get(field.name, None)
        if "help" not in field.metadata and field_doc is not None:
            kwargs["help"] = field_doc

        # Default precedence: override_default, field.default, field.metadata, default_argument_args
        if has_default:
            kwargs["default"] = field.default

        # Fix field type to match work well with argparse
        _update_field_type(kwargs)

        self.args.append((field.name, args, kwargs))

    def make(self, default_values: Optional[DataClass] = None) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(**self.parser_args)
        if dataclasses.is_dataclass(default_values):
            default_values = dataclasses.asdict(default_values)
        else:
            assert default_values is None
            default_values = {}

        for name, args, kwargs in self.args:
            if name in default_values:
                kwargs = dict(kwargs, default=default_values[name])
            parser.add_argument(*args, **kwargs)

        return parser

    def cast_to_class(self, namespace) -> Union[DataclassParser[DataClass], DataClass]:
        if not isinstance(namespace, dict):
            namespace = vars(namespace)
        return self.cls(**{to_var_name(k): v for k, v in namespace.items()})

    def get_vars(self, instance_or_cls: Union[Type[DataClass], DataClass]) -> Dict[str, Any]:
        if isinstance(instance_or_cls, type):
            return dict(self.all_defaults)
        else:
            return dataclasses.asdict(instance_or_cls)

    def asdict(self, instance_or_cls: Union[Type[DataClass], DataClass]) -> Dict[str, Any]:
        return {to_arg_name(k): v for k, v in self.get_vars(instance_or_cls).items()}

    def from_dict(
        self, instance_or_cls: Union[Type[DataClass], DataClass], namespace: Union[Any, Dict[str, Any]]
    ) -> Union[DataclassParser[DataClass], DataClass]:
        if not isinstance(namespace, dict):
            namespace = vars(namespace)

        defaults = self.get_vars(instance_or_cls)
        iter_namespace = ((to_var_name(k), v) for k, v in namespace.items())
        defaults.update({k: v for k, v in iter_namespace if k in defaults})
        return self.cast_to_class(defaults)

    def dump_yaml(self, instance_or_cls: Union[Type[DataClass], DataClass], stream=None, **kwargs) -> str:
        cur_vars = self.get_vars(instance_or_cls)
        cur_vars = _obj_to_yaml_dict(cur_vars)
        return yaml.safe_dump(cur_vars, stream=stream, **kwargs)

    def load_yaml(
        self, instance_or_cls: Union[Type[DataClass], DataClass], stream
    ) -> Union[DataclassParser[DataClass], DataClass]:
        cur_vars = self.get_vars(instance_or_cls)
        loaded_vars = yaml.safe_load(stream)
        loaded_vars = _yaml_dict_to_obj(loaded_vars, self.all_types)
        cur_vars.update(loaded_vars)
        return self.cls(**cur_vars)

    def _get_parser(self, instance_or_cls: Union[Type[DataClass], DataClass]) -> argparse.ArgumentParser:
        if isinstance(instance_or_cls, type):
            return self.main_parser
        else:
            return self.make(instance_or_cls)

    def get_parser(self, instance_or_cls: Union[Type[DataClass], DataClass]) -> argparse.ArgumentParser:
        return self.make(instance_or_cls if not isinstance(instance_or_cls, type) else None)

    def format_help(self, instance_or_cls: Union[Type[DataClass], DataClass]) -> str:
        return self._get_parser(instance_or_cls).format_help()

    def format_usage(self, instance_or_cls: Union[Type[DataClass], DataClass]) -> str:
        return self._get_parser(instance_or_cls).format_usage()

    def print_help(self, instance_or_cls: Union[Type[DataClass], DataClass], file=None):
        return self._get_parser(instance_or_cls).print_help(file)

    def print_usage(self, instance_or_cls: Union[Type[DataClass], DataClass], file=None):
        return self._get_parser(instance_or_cls).print_usage(file)

    def parse_args(
        self, instance_or_cls: Union[Type[DataClass], DataClass], args: Optional[Sequence[str]] = None
    ) -> Union[DataclassParser[DataClass], DataClass]:
        namespace = self._get_parser(instance_or_cls).parse_args(args=args)
        return self.cast_to_class(namespace)

    def parse_intermixed_args(
        self, instance_or_cls: Union[Type[DataClass], DataClass], args: Optional[Sequence[str]] = None
    ) -> Union[DataclassParser[DataClass], DataClass]:
        namespace = self._get_parser(instance_or_cls).parse_intermixed_args(args=args)
        return self.cast_to_class(namespace)

    def parse_known_args(
        self, instance_or_cls: Union[Type[DataClass], DataClass], args: Optional[Sequence[str]] = None
    ) -> Tuple[Union[DataclassParser[DataClass], DataClass], List[str]]:
        namespace, args = self._get_parser(instance_or_cls).parse_known_args(args=args)
        return self.cast_to_class(namespace), args

    def parse_known_intermixed_args(
        self, instance_or_cls: Union[Type[DataClass], DataClass], args: Optional[Sequence[str]] = None
    ) -> Tuple[Union[DataclassParser[DataClass], DataClass], List[str]]:
        namespace, args = self._get_parser(instance_or_cls).parse_known_intermixed_args(args=args)
        return self.cast_to_class(namespace), args


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
        if obj is not None:
            val = obj
        else:
            val = cls
        return MethodType(self.f, val)


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
def classparser(**kwargs) -> Callable[[Type[K]], Union[Type[DataclassParser[K]], Type[K]]]:
    ...  # pragma: no cover


@typing.overload
def classparser(cls: Type[DataClass]) -> Union[Type[DataclassParser[DataClass]], Type[DataClass]]:
    ...  # pragma: no cover


def classparser(cls=None, /, **kwargs):
    """Decorator that adds `DataclassParser` methods to the dataclass"""

    # See if we're being called as @dataclass_parser or @dataclass_parser().
    if cls is None:
        # We're called with parens.
        return functools.partial(_transform_dataclass_parser, kwargs=kwargs)

    # We're called as @dataclass_parser without parens.
    return _transform_dataclass_parser(cls, kwargs)

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
LOAD_DEFAULTS_FILED = "load_defaults"


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


def namespace_to_vars(namespace) -> Dict[str, Any]:
    if not isinstance(namespace, dict):
        namespace = vars(namespace)
    return {to_var_name(k): v for k, v in namespace.items()}


def _name_or_flags_arg(arg_name: str, flag: Optional[str] = None, positional: bool = False) -> Iterable[str]:
    arg_name = to_arg_name(arg_name)
    if positional:
        assert flag is None, "Flag is not supported for positional argument"
        return [arg_name]
    return filter(None, [flag, f"--{arg_name}"])


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
    def __init__(
        self,
        instance_or_cls: Union[Type[DataClass], DataClass],
        default_argument_args=None,
        load_defaults_from_file=False,
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

        self.parser_args = parser_args
        self.parser_args.setdefault("description", self.cls.__doc__)

        self.docs = docs.get_argument_docs(self.cls)
        self.args = []

        for field in dataclasses.fields(self.cls):
            self._add_argument_from_field(field)

        self.fields = {name for name, _, _, in self.args}
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

        if self.load_defaults_from_file:
            _add_load_defaults_arg(parser)

        for name, args, kwargs in self.args:
            if name in default_values:
                kwargs = dict(kwargs, default=default_values[name])
            parser.add_argument(*args, **kwargs)

        return parser

    def parse_load_defaults(self, instance_or_cls, args=None):
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
        defaults = self.get_vars(instance_or_cls)
        defaults.update({k: v for k, v in namespace_to_vars(namespace).items() if k in self.fields})
        return self.cls(**defaults)

    def dump_yaml(self, instance_or_cls: Union[Type[DataClass], DataClass], stream=None, **kwargs) -> str:
        cur_vars = self.get_vars(instance_or_cls)
        cur_vars = _obj_to_yaml_dict(cur_vars)
        return yaml.safe_dump(cur_vars, stream=stream, **kwargs)

    def load_yaml(
        self, instance_or_cls: Union[Type[DataClass], DataClass], stream
    ) -> Union[DataclassParser[DataClass], DataClass]:
        loaded_vars = yaml.safe_load(stream)
        loaded_vars = _yaml_dict_to_obj(loaded_vars, self.all_types)
        return self.from_dict(instance_or_cls, loaded_vars)

    def _get_parser(self, instance_or_cls: Union[Type[DataClass], DataClass]) -> argparse.ArgumentParser:
        if instance_or_cls is self.cls:
            return self.main_parser
        else:
            return self.make(instance_or_cls)

    def _get_parser_with_defaults(
        self, instance_or_cls: Union[Type[DataClass], DataClass], args: Optional[Sequence[str]] = None
    ) -> argparse.ArgumentParser:
        instance_or_cls = self.parse_load_defaults(instance_or_cls, args)
        return self._get_parser(instance_or_cls)

    def get_parser(self, instance_or_cls: Union[Type[DataClass], DataClass]) -> argparse.ArgumentParser:
        return self.make(instance_or_cls)

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
        namespace = self._get_parser_with_defaults(instance_or_cls, args).parse_args(args=args)
        return self.from_dict(instance_or_cls, namespace)

    def parse_intermixed_args(
        self, instance_or_cls: Union[Type[DataClass], DataClass], args: Optional[Sequence[str]] = None
    ) -> Union[DataclassParser[DataClass], DataClass]:
        namespace = self._get_parser_with_defaults(instance_or_cls, args).parse_intermixed_args(args=args)
        return self.from_dict(instance_or_cls, namespace)

    def parse_known_args(
        self, instance_or_cls: Union[Type[DataClass], DataClass], args: Optional[Sequence[str]] = None
    ) -> Tuple[Union[DataclassParser[DataClass], DataClass], List[str]]:
        namespace, args = self._get_parser_with_defaults(instance_or_cls, args).parse_known_args(args=args)
        return self.from_dict(instance_or_cls, namespace), args

    def parse_known_intermixed_args(
        self, instance_or_cls: Union[Type[DataClass], DataClass], args: Optional[Sequence[str]] = None
    ) -> Tuple[Union[DataclassParser[DataClass], DataClass], List[str]]:
        namespace, args = self._get_parser_with_defaults(instance_or_cls, args).parse_known_intermixed_args(args=args)
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

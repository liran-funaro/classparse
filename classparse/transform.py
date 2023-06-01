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
import contextlib
import functools
from types import MethodType
from typing import Any, Dict, Generic, List, Optional, Sequence, TextIO, Tuple, Type, TypeVar, Union

import yaml

from classparse.analyze import DataclassFieldAnalyzer, to_arg_name, to_var_name
from classparse.proto import DataclassParser, DataclassParserType, dataclass_parser_methods
from classparse.types import obj_to_yaml_dict, yaml_dict_to_obj

LOAD_DEFAULTS_FILED = "load_defaults"

_T = TypeVar("_T", bound=object)
InstanceOrClass = Union[Type[_T], _T]


def _asdict_recursive(values) -> Dict[str, Any]:
    if not isinstance(values, dict):
        return values
    return {to_arg_name(k): _asdict_recursive(v) for k, v in values.items()}


def _add_load_defaults_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        f"--{to_arg_name(LOAD_DEFAULTS_FILED)}",
        metavar="PATH",
        type=argparse.FileType("r"),
        default=None,
        help="A YAML file path that overrides the default values.",
    )


def parse_load_defaults(args: Optional[Sequence[str]] = None) -> Optional[TextIO]:
    """Silently try to parse load-defaults from the arguments"""

    # pylint: disable=broad-exception-caught
    # We want to avoid any unexpected exception here.
    # If there is a real error, it will show in the exposed parser.

    with contextlib.ExitStack() as stack:
        stack.enter_context(contextlib.redirect_stderr(None))
        stack.enter_context(contextlib.redirect_stdout(None))
        try:
            parser = argparse.ArgumentParser(add_help=False)
            _add_load_defaults_arg(parser)
            namespace, _ = parser.parse_known_args(args=args)
            return getattr(namespace, LOAD_DEFAULTS_FILED, None)
        except (Exception, SystemExit):
            pass

    return None


class DataclassNamespace:
    """
    Simple object for storing attributes; similar to `argparse.Namespace`, with two notable differences:
     * All attributes are stored in a variable notation (underscore word separation).
     * "known fields" does not issue an `AttributeError`.

    As `argparse.Namespace`, it also implements equality by attribute names and values, and provides a simple
    string representation.
    """

    def __init__(self, known_fields):
        """Known fields will not issue an `AttributeError`."""
        self.__known_fields__ = known_fields

    def __getattribute__(self, key):
        key = to_var_name(key)

        # First, we try to return the real attribute field
        try:
            return super().__getattribute__(key)
        except AttributeError as exc:
            if key not in self.__known_fields__:
                raise exc

        # We return a value so `hasattr()` will return True for all known fields.
        # This supress the automatic assignments of default values.
        # We need it so we can later discover if a value was actually assigned by the user.
        return None

    def __setattr__(self, key, value):
        super().__setattr__(to_var_name(key), value)

    def __eq__(self, other):
        if not isinstance(other, DataclassNamespace):
            return NotImplemented
        return vars(self) == vars(other) and self.__known_fields__ == other.__known_fields__

    def __contains__(self, key):
        return key in self.__dict__ or key in self.__known_fields__

    def __repr__(self):
        kvs = ", ".join(f"{k}={repr(v)}" for k, v in vars(self).items() if k != "__known_fields__")
        return f"{self.__class__.__name__}({kvs})"


class DataclassParserMaker(Generic[_T]):
    """Analyzes a dataclass fields and makes a parser accordingly"""

    def __init__(
        self,
        instance_or_cls: InstanceOrClass[_T],
        default_argument_args: Optional[Dict[str, Any]] = None,
        load_defaults_from_file: bool = False,
        description: Optional[str] = None,
        **parser_args,
    ):
        self.analyzer = DataclassFieldAnalyzer(instance_or_cls, default_argument_args, description)
        self.load_defaults_from_file = bool(load_defaults_from_file)
        self.parser_args = dict(parser_args, description=self.analyzer.description)
        self.flat_fields = list(self.analyzer.iter_flatten_fields())
        self.main_parser = self.make()

    def make(self, instance_or_cls=None) -> argparse.ArgumentParser:
        """Creates a new ArgumentParser according to the dataclass fields."""
        parser = argparse.ArgumentParser(**self.parser_args)
        if self.load_defaults_from_file:
            _add_load_defaults_arg(parser)
        self.analyzer.add_all_arguments(instance_or_cls, parser)
        return parser

    def _parse_load_defaults(self, instance_or_cls, args=None):
        """If enabled, silently try to parse load-defaults from the arguments, then loads the defaults YAML file."""
        if not self.load_defaults_from_file:
            return instance_or_cls

        load_defaults = parse_load_defaults(args)
        if load_defaults is None:
            return instance_or_cls

        return self.load_yaml(instance_or_cls, load_defaults)

    def _get_parser(self, instance_or_cls=None) -> argparse.ArgumentParser:
        if self.analyzer.is_cls(instance_or_cls):
            return self.main_parser
        return self.make(instance_or_cls)

    def _call_parser_method(
        self, instance_or_cls, args: Optional[Sequence[str]], method_name: str
    ) -> Tuple[DataclassParser[_T], Any]:
        """See `DataclassParser.parse_args()`"""
        instance_or_cls = self._parse_load_defaults(instance_or_cls, args)
        namespace = DataclassNamespace(self.flat_fields)
        parser = self._get_parser(instance_or_cls)
        method = getattr(parser, method_name)
        ret = method(args=args, namespace=namespace)
        return self.analyzer.transform(instance_or_cls, namespace), ret

    def _call_parser_method_unknown(
        self, instance_or_cls, args: Optional[Sequence[str]], method_name: str
    ) -> Tuple[DataclassParser[_T], List[str]]:
        instance, (_, unknown_args) = self._call_parser_method(instance_or_cls, args, method_name)
        return instance, unknown_args

    ################################################################################################################
    # Public DataclassParser API
    ################################################################################################################

    def get_vars(self, instance_or_cls=None) -> Dict[str, Any]:
        """See `DataclassParser.get_vars()`"""
        return self.analyzer.get_vars(instance_or_cls)

    def asdict(self, instance_or_cls=None) -> Dict[str, Any]:
        """See `DataclassParser.asdict()`"""
        return _asdict_recursive(self.analyzer.get_vars(instance_or_cls))

    def from_dict(self, instance_or_cls, namespace: Any) -> DataclassParser[_T]:
        """See `DataclassParser.from_dict()`"""
        return self.analyzer.transform(instance_or_cls, namespace)

    def dump_yaml(self, instance_or_cls=None, stream=None, sort_keys=False, **kwargs) -> str:
        """See `DataclassParser.dump_yaml()`"""
        cur_vars = self.analyzer.get_vars(instance_or_cls)
        cur_vars = obj_to_yaml_dict(cur_vars)
        return yaml.safe_dump(cur_vars, stream=stream, sort_keys=sort_keys, **kwargs)

    def load_yaml(self, instance_or_cls, stream) -> DataclassParser[_T]:
        """See `DataclassParser.load_yaml()`"""
        loaded_vars = yaml.safe_load(stream)
        loaded_vars = yaml_dict_to_obj(loaded_vars, self.analyzer.all_types)
        return self.analyzer.transform(instance_or_cls, loaded_vars)

    def get_parser(self, instance_or_cls=None) -> argparse.ArgumentParser:
        """See `DataclassParser.get_parser()`"""
        return self.make(instance_or_cls)

    def format_help(self, instance_or_cls=None) -> str:
        """See `DataclassParser.format_help()`"""
        return self._get_parser(instance_or_cls).format_help()

    def format_usage(self, instance_or_cls=None) -> str:
        """See `DataclassParser.format_usage()`"""
        return self._get_parser(instance_or_cls).format_usage()

    def print_help(self, instance_or_cls=None, file=None):
        """See `DataclassParser.print_help()`"""
        return self._get_parser(instance_or_cls).print_help(file)

    def print_usage(self, instance_or_cls=None, file=None):
        """See `DataclassParser.print_usage()`"""
        return self._get_parser(instance_or_cls).print_usage(file)

    def parse_args(self, instance_or_cls=None, args: Optional[Sequence[str]] = None) -> DataclassParser[_T]:
        """See `DataclassParser.parse_args()`"""
        return self._call_parser_method(instance_or_cls, args, "parse_args")[0]

    def parse_intermixed_args(self, instance_or_cls=None, args: Optional[Sequence[str]] = None) -> DataclassParser[_T]:
        """See `DataclassParser.parse_intermixed_args()`"""
        return self._call_parser_method(instance_or_cls, args, "parse_intermixed_args")[0]

    def parse_known_args(
        self, instance_or_cls, args: Optional[Sequence[str]] = None
    ) -> Tuple[DataclassParser[_T], List[str]]:
        """See `DataclassParser.parse_known_args()`"""
        return self._call_parser_method_unknown(instance_or_cls, args, "parse_known_args")

    def parse_known_intermixed_args(
        self, instance_or_cls, args: Optional[Sequence[str]] = None
    ) -> Tuple[DataclassParser[_T], List[str]]:
        """See `DataclassParser.parse_known_intermixed_args()`"""
        return self._call_parser_method_unknown(instance_or_cls, args, "parse_known_intermixed_args")


class ClassOrInstanceMethod:
    """
    Similar to `@classmethod`, but allow the method to be applicable for both class and instance.
    That is, if the method is called on the instance, the self/cls argument will be populated with the instance.
    If the method is called on the class, the self/cls argument will be populated with the class.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, func):
        self.func = func
        functools.update_wrapper(self, func)

    def __get__(self, obj, cls=None):
        return MethodType(self.func, obj if obj is not None else cls)


def _transform_dataclass_parser(cls: Type[_T], kwargs: Dict[str, Any]) -> DataclassParserType[_T]:
    """Decorator that adds `DataclassParser` methods to the dataclass"""
    kwargs = kwargs or {}
    parser_maker: DataclassParserMaker[_T] = DataclassParserMaker(cls, **kwargs)
    for method_name in dataclass_parser_methods:
        setattr(cls, method_name, ClassOrInstanceMethod(getattr(parser_maker, method_name)))
    return cls

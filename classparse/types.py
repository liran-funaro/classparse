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
import ast
import enum
import functools
import typing
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union

_TYPE_RECURSION_LIMIT = 1024
_TRUE_STRINGS = {"t", "true", "y", "yes"}
_FALSE_STRINGS = {"f", "false", "n", "no"}


@functools.wraps(bool)
def __parse_bool(val):
    norm_val = str(val).lower().strip()
    if norm_val in _TRUE_STRINGS:
        return True
    if norm_val in _FALSE_STRINGS:
        return False

    raise ValueError(f"{val} cannot be parsed as boolean.")


def _make_enum_parser(enum_type):
    @functools.wraps(enum_type)
    def __enum_wrapper__(val):
        # We first try by key (Enum's literal name)
        try:
            return enum_type[val]
        except (KeyError, TypeError):
            pass

        # Then, by value (Enum's assigned value)
        try:
            return enum_type(val)
        except (ValueError, TypeError):
            pass

        # Finally, we try again by value with literal evaluation
        try:
            literal_val = ast.literal_eval(val)
            return enum_type(literal_val)
        except (ValueError, TypeError):
            pass

        raise ValueError(f"{val} is not a valid {enum_type}")

    return __enum_wrapper__


def _make_literal_parser(literal_type, raise_error=True):
    name = repr(literal_type)
    choices = list(typing.get_args(literal_type))
    arg_strs = [str(arg) for arg in choices]
    parsers = [_get_type_parser(arg_type) for arg_type in map(type, choices)]

    # noinspection PyBroadException
    @functools.wraps(literal_type)
    def __literal_wrapper(val):
        for arg, arg_str, arg_parser in zip(choices, arg_strs, parsers):
            try:
                if val == arg_str or val == arg or arg_parser(val) == arg:
                    return arg
            except ValueError:
                pass

        if not raise_error:
            return val

        raise ValueError(f"{val} cannot be interpreted as {name}.")

    __literal_wrapper.__name__ = name
    return __literal_wrapper


def _is_type(type_obj, parent_type_obj) -> bool:
    return isinstance(type_obj, type) and issubclass(type_obj, parent_type_obj)


def _is_any_type(type_obj) -> bool:
    return type_obj in [Any, Optional, object, ..., "typing.Any", "", None]


def _is_container_type(type_obj) -> bool:
    return type_obj in (list, tuple, set)


def _is_enum_type(type_obj) -> bool:
    return _is_type(type_obj, enum.Enum)


def _is_bool_type(type_obj) -> bool:
    return _is_type(type_obj, bool)


def _is_str_type(type_obj) -> bool:
    return _is_type(type_obj, str)


def _is_none_type(type_obj) -> bool:
    return type_obj is None or _is_type(type_obj, type(None))


def _is_literal_type(type_obj) -> bool:
    return typing.get_origin(type_obj) is Literal


def _get_type_parser(type_obj):
    if _is_bool_type(type_obj):
        return __parse_bool
    if _is_enum_type(type_obj):
        return _make_enum_parser(type_obj)
    if _is_literal_type(type_obj):
        return _make_literal_parser(type_obj)
    return type_obj


def _wrap_union(union_type, arg_set: List[type]):
    name = repr(union_type)
    has_str = any(map(_is_str_type, arg_set))
    parsers = [_get_type_parser(arg_type) for arg_type in arg_set if not _is_str_type(arg_type)]

    # noinspection PyBroadException
    @functools.wraps(union_type)
    def __union_wrapper__(val):
        e_list = []
        for arg_parser in parsers:
            try:
                return arg_parser(val)
            except ValueError as exp:
                e_list.append(f"{arg_parser}: {exp}")

        if has_str and isinstance(val, str):
            return val

        raise ValueError(f"{val} cannot be interpreted as {name}: {', '.join(e_list)}.")

    __union_wrapper__.__name__ = name
    return __union_wrapper__


def _make_metavar(obj: Any) -> str:
    if isinstance(obj, enum.Enum):
        return f"{obj.name}/{obj.value}"
    return str(obj)


def _make_metavar_string(choices: List) -> str:
    metavar = ",".join(map(_make_metavar, choices))
    return f"{{{metavar}}}"


class _Argument:
    args: Dict[str, Any]
    update_count: int
    type: Optional[Type]
    type_origin: Optional[Type]
    type_args: Tuple[Type[Any], ...]
    have_nested_type: bool

    def __init__(self, argument_args: Dict[str, Any]):
        self.args = argument_args
        self.update_count = 0

    def update_type(self):
        """Update the type information"""
        self.type = self.args.get("type", None)
        self.type_origin = typing.get_origin(self.type)
        self.type_args = typing.get_args(self.type)
        self.have_nested_type = False
        self.update_count += 1

    def update_any(self):
        """Any/Optional annotation without a type"""
        self.args.pop("type", None)

    def update_union(self):
        """Optional annotation with a type (interpreted as a Union), Union"""
        arg_set = [t for t in self.type_args if not _is_none_type(t)]
        if len(arg_set) > 1:
            self.args["type"] = _wrap_union(self.type, arg_set)
        else:
            # For union of one type (other than None), we support further inspection of the type
            self.args["type"] = self.type_args[0]
            self.have_nested_type = True

    def update_nargs(self):
        """
        List/Tuple/Set type/annotation is used to define a repeated argument.
        Tuple annotation is used to define a fixed length repeated argument
        """
        type_args = tuple(self.type_args)
        n_args: Union[int, str] = "+"
        if self.type_origin is tuple and len(type_args) > 0:
            if self.type_args[-1] == Ellipsis:
                # Tuple[T, ...] ==> List/Set[T] ==> nargs="+"
                type_args = type_args[:-1]
            else:
                # Tuple[T1, T2, Tn] ==> nargs=n
                n_args = len(type_args)

        self.args.setdefault("nargs", n_args)

        if len(type_args) > 0:
            self.args["type"] = Union[type_args]
            self.have_nested_type = True
        else:
            self.update_any()

    def update_enum(self):
        """Enum type is used to define a typed choice argument"""
        assert self.type is not None
        assert issubclass(self.type, enum.Enum)
        choices = list(self.type)
        self.args["choices"] = choices
        self.args["metavar"] = _make_metavar_string(choices)
        cur_default = self.args.get("default", None)
        if isinstance(cur_default, enum.Enum):
            # Change default to string for readability
            self.args["default"] = cur_default.name
        self.args["type"] = _make_enum_parser(self.type)

    def update_literal(self):
        """Literal type is used to define an untyped choice argument"""
        choices = list(self.type_args)
        assert len(choices) > 0, "'Literal' must have at least one parameter."
        choices_types = set(map(type, self.type_args))

        self.args["choices"] = choices
        self.args["metavar"] = _make_metavar_string(choices)

        if len(choices_types) > 1:
            self.args["type"] = _make_literal_parser(self.type, raise_error=False)
        else:
            self.args["type"] = list(choices_types)[0]
            self.have_nested_type = True

    def update_bool(self):
        """bool type is used to define a BooleanOptionalAction argument"""
        if hasattr(argparse, "BooleanOptionalAction"):
            self.args["action"] = argparse.BooleanOptionalAction
        else:
            self.args["action"] = "store_true"
            del self.args["type"]

    def _update_field_type_internal(self):
        self.update_type()

        if _is_any_type(self.type):
            self.update_any()
        elif self.type_origin is Union:
            self.update_union()
        elif _is_container_type(self.type) or _is_container_type(self.type_origin):
            self.update_nargs()
        elif _is_enum_type(self.type):
            self.update_enum()
        elif _is_literal_type(self.type):
            self.update_literal()
        elif _is_bool_type(self.type):
            self.update_bool()

    def update_field_type(self) -> bool:
        """Return `True` if the type was reassigned, and it requires to inspect it again"""
        self._update_field_type_internal()
        return self.have_nested_type and self.update_count < _TYPE_RECURSION_LIMIT


def update_field_type(argument_args: Dict[str, Any]):
    """Update argument kwargs to work well with argparse"""
    arg = _Argument(argument_args)

    # Some types are recursive, so we iterate until no update is needed
    while arg.update_field_type():
        pass

    arg.update_type()
    return arg.type


def obj_to_yaml_dict(obj):
    """Covert a python dict/object to a native YAML object"""
    if isinstance(obj, dict):
        return {k: obj_to_yaml_dict(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [obj_to_yaml_dict(v) for v in obj]
    if isinstance(obj, enum.Enum):
        return obj.name
    if isinstance(obj, (int, float, bool, str)) or obj is None:
        return obj
    return str(obj)


StrToType = Callable[[str], Any]
StrToTypeOrDict = Union[StrToType, Dict[str, "StrToTypeOrDict"], None]


def yaml_dict_to_obj(obj, value_type: StrToTypeOrDict):
    """Convert back a dict that was generated via obj_to_yaml_dict()"""
    if isinstance(obj, dict):
        assert isinstance(value_type, dict)
        return {k: yaml_dict_to_obj(v, value_type.get(k, None)) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [yaml_dict_to_obj(v, value_type) for v in obj]
    if callable(value_type) and isinstance(obj, str):
        return value_type(obj)
    return obj

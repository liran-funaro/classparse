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
import enum
import functools
import itertools
import typing
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union

_TYPE_RECURSION_LIMIT = 1024


@functools.wraps(bool)
def __parse_bool(x):
    _x = str(x).lower().strip()
    if _x in ("t", "true", "y", "yes"):
        return True
    elif _x in ("f", "false", "n", "no"):
        return False

    raise TypeError(f"{x} cannot be parsed as boolean.")


def __make_enum_parser(enum_type):
    # noinspection PyBroadException
    @functools.wraps(enum_type)
    def __enum_wrapper__(x):
        try:
            x = int(x)
        except Exception:
            pass

        if isinstance(x, int):
            return enum_type(x)

        try:
            return enum_type[x]
        except Exception:
            return enum_type(x)

    return __enum_wrapper__


def __make_literal_parser(literal_type, raise_error=True):
    name = repr(literal_type)
    choices = list(typing.get_args(literal_type))
    arg_strs = [str(arg) for arg in choices]
    parsers = [__get_type_parser(arg_type) for arg_type in map(type, choices)]

    # noinspection PyBroadException
    @functools.wraps(literal_type)
    def __literal_wrapper(x):
        for arg, arg_str, arg_parser in zip(choices, arg_strs, parsers):
            try:
                if x == arg_str or x == arg or arg_parser(x) == arg:
                    return arg
            except Exception:
                pass

        if raise_error:
            raise TypeError(f"{x} cannot be interpreted as {name}.")
        else:
            return x

    __literal_wrapper.__name__ = name
    return __literal_wrapper


def _is_type(t, type_obj):
    return isinstance(t, type) and issubclass(t, type_obj)


def _is_enum_type(t):
    return _is_type(t, enum.Enum)


def _is_bool_type(t):
    return _is_type(t, bool)


def _is_str_type(t):
    return _is_type(t, str)


def _is_none_type(t):
    return t is None or _is_type(t, type(None))


def _is_literal_type(t):
    return typing.get_origin(t) is Literal


def __get_type_parser(t):
    if _is_bool_type(t):
        return __parse_bool
    elif _is_enum_type(t):
        return __make_enum_parser(t)
    elif _is_literal_type(t):
        return __make_literal_parser(t)
    else:
        return t


def __wrap_union(union_type, arg_set: List[type]):
    name = repr(union_type)
    has_str = any(map(_is_str_type, arg_set))
    parsers = [__get_type_parser(arg_type) for arg_type in arg_set if not _is_str_type(arg_type)]

    # noinspection PyBroadException
    @functools.wraps(union_type)
    def __union_wrapper__(x):
        e_list = []
        for arg_parser in parsers:
            try:
                return arg_parser(x)
            except Exception as e:
                e_list.append(f"{arg_parser}: {e}")

        if has_str and isinstance(x, str):
            return x
        else:
            raise TypeError(f"{x} cannot be interpreted as {name}: {', '.join(e_list)}.")

    __union_wrapper__.__name__ = name
    return __union_wrapper__


class Argument:
    args: Dict[str, Any]
    type: Optional[Type]
    type_origin: Optional[Type]
    type_args: Tuple[Type]

    def __init__(self, argument_args: Dict[str, Any]):
        self.args = argument_args
        self.update_type()

    def update_type(self):
        self.type = self.args.get("type", None)
        self.type_origin = typing.get_origin(self.type)
        self.type_args: tuple = typing.get_args(self.type)


def _update_optional(a: Argument) -> bool:
    """Optional annotation without a type"""
    del a.args["type"]
    return False


def _update_union(a: Argument) -> bool:
    """Optional annotation with a type (interpreted as a Union), Union"""
    arg_set = [t for t in a.type_args if not _is_none_type(t)]
    if len(arg_set) == 1:
        # For union of one type (other than None), we support further inspection of the type
        a.args["type"] = a.type_args[0]
        return True
    else:
        a.args["type"] = __wrap_union(a.type, arg_set)
        return False


def _update_nargs(a: Argument) -> bool:
    """
    List/Tuple/Set type/annotation is used to define a repeated argument.
    Tuple annotation is used to define a fixed length repeated argument
    """
    a.args.setdefault("nargs", len(a.type_args) if a.type_origin is tuple else "+")

    if len(a.type_args) > 0:
        a.args["type"] = Union[tuple(a.type_args)]
        return True
    else:
        del a.args["type"]
        return False


def _make_metavar(o: Any) -> str:
    if isinstance(o, enum.Enum):
        return f"{o.name}/{o.value}"
    else:
        return str(o)


def _update_enum(a: Argument) -> bool:
    """Enum type is used to define a typed choice argument"""
    assert issubclass(a.type, enum.Enum)
    choices = list(a.type)
    a.args["choices"] = choices
    a.args["metavar"] = "{%s}" % ",".join(map(_make_metavar, choices))
    cur_default = a.args.get("default", None)
    if isinstance(cur_default, enum.Enum):
        a.args["default"] = cur_default.name
    a.args["type"] = __make_enum_parser(a.type)
    return False


def _update_literal(a: Argument) -> bool:
    """Literal type is used to define an untyped choice argument"""
    choices = list(a.type_args)
    assert len(choices) > 0, "'Literal' must have at least one parameter."
    choices_types = set(map(type, a.type_args))

    a.args["choices"] = choices
    a.args["metavar"] = "{%s}" % ",".join(map(_make_metavar, choices))

    if len(choices_types) == 1:
        a.args["type"] = list(choices_types)[0]
        return True
    else:
        a.args["type"] = __make_literal_parser(a.type, raise_error=False)
        return False


def _update_bool(a: Argument) -> bool:
    """bool type is used to define a BooleanOptionalAction argument"""
    if hasattr(argparse, "BooleanOptionalAction"):
        a.args["action"] = argparse.BooleanOptionalAction
    else:
        a.args["action"] = "store_true"
        del a.args["type"]
    return False


def _update_field_type_internal(a: Argument) -> bool:
    """Return `True` if the type was reassigned, and it requires to inspect it again"""
    if a.type is Optional:
        return _update_optional(a)

    if a.type_origin is Union:
        return _update_union(a)

    if a.type in (list, tuple, set) or a.type_origin in (list, tuple, set):
        return _update_nargs(a)

    if _is_enum_type(a.type):
        return _update_enum(a)

    if _is_literal_type(a.type):
        return _update_literal(a)

    if _is_bool_type(a.type):
        return _update_bool(a)

    return False


def _update_field_type(argument_args: Dict[str, Any]):
    a = Argument(argument_args)
    iter_count = itertools.count()
    # Some types are recursive, so we iterate until no special type is matched
    while _update_field_type_internal(a) and next(iter_count) < _TYPE_RECURSION_LIMIT:
        a.update_type()


def _obj_to_yaml_dict(o):
    if isinstance(o, dict):
        return {k: _obj_to_yaml_dict(v) for k, v in o.items()}
    if isinstance(o, (tuple, list)):
        return [_obj_to_yaml_dict(v) for v in o]
    if isinstance(o, enum.Enum):
        return o.name
    if isinstance(o, (int, float, bool)) or o is None:
        return o
    else:
        return str(o)


def _yaml_dict_to_obj(o, value_type: Union[Callable, Dict[str, Callable]]):
    if isinstance(o, dict):
        return {k: _yaml_dict_to_obj(v, value_type.get(k, None)) for k, v in o.items()}
    if isinstance(o, (tuple, list)):
        return [_yaml_dict_to_obj(v, value_type) for v in o]
    if callable(value_type) and isinstance(o, str):
        return value_type(o)
    else:
        return o

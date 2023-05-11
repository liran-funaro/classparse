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
import itertools
import typing
from typing import Any, Dict, List, Literal, Optional, Tuple, Type, Union

_TYPE_RECURSION_LIMIT = 1024


def __wrap_enum(enum_type):
    # noinspection PyBroadException
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

    __enum_wrapper__.__name__ = enum_type.__name__
    return __enum_wrapper__


def __wrap_union(union: Union, arg_set: List[type]):
    name = repr(union)

    # noinspection PyBroadException
    def __union_wrapper__(x):
        e_list = []
        for arg_type in arg_set:
            try:
                return arg_type(x)
            except Exception as e:
                e_list.append(f"{arg_type}: {e}")

        raise TypeError(f"Could not apply any of the types in {name}: {', '.join(e_list)}.")

    __union_wrapper__.__name__ = name
    return __union_wrapper__


class _Argument:
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


def _update_optional(a: _Argument) -> bool:
    """Optional annotation without a type"""
    del a.args["type"]
    return False


def _update_union(a: _Argument) -> bool:
    """Optional annotation with a type (interpreted as a Union), Union"""
    arg_set = [v for v in a.type_args if not issubclass(v, type(None)) and v is not None]
    if len(arg_set) == 1:
        # For union of one type (other than None), we support further inspection of the type
        a.args["type"] = a.type_args[0]
        return True
    else:
        a.args["type"] = __wrap_union(a.type, arg_set)
        return False


def _update_nargs(a: _Argument) -> bool:
    arg_set = list(set(a.type_args))
    assert len(arg_set) <= 1, "All args must be of the same type"

    if a.type in (list, tuple) or a.type_origin is list:
        # List/Tuple type/annotation is used to define a repeated argument
        a.args.setdefault("nargs", "+")
        if len(a.type_args) > 0:
            a.args["type"] = a.type_args[0]
            return True
        else:
            del a.args["type"]
            return False

    # Tuple annotation is used to define a fixed length repeated argument
    a.args.setdefault("nargs", len(a.type_args))
    a.args["type"] = a.type_args[0]
    return True


def _update_enum(a: _Argument) -> bool:
    """Enum type is used to define a typed choice argument"""
    assert issubclass(a.type, enum.Enum)
    choices = list(a.type)
    a.args["choices"] = choices
    a.args["metavar"] = "{%s}" % ",".join([f"{c.name}/{c.value}" for c in choices])
    cur_default = a.args.get("default", None)
    if isinstance(cur_default, enum.Enum):
        a.args["default"] = cur_default.name
    a.args["type"] = __wrap_enum(a.type)
    return False


def _update_literal(a: _Argument) -> bool:
    """Literal type is used to define an untyped choice argument"""
    a.args["choices"] = list(a.type_args)
    cur_types = list({type(a) for a in a.type_args})
    assert len(cur_types) == 1, "All literals must be of the same type"
    a.args["type"] = cur_types[0]
    return True


def _update_bool(a: _Argument) -> bool:
    """bool type is used to define a store_true argument"""
    if hasattr(argparse, "BooleanOptionalAction"):
        a.args["action"] = argparse.BooleanOptionalAction
    else:
        a.args["action"] = "store_true"
        del a.args["type"]
    return False


def _update_field_type_internal(a: _Argument) -> bool:
    """Return `True` if the type was reassigned, and it requires to inspect it again"""
    if a.type is Optional:
        return _update_optional(a)

    if a.type_origin is Union:
        return _update_union(a)

    if a.type in (list, tuple) or a.type_origin in (list, tuple):
        return _update_nargs(a)

    if isinstance(a.type, type) and issubclass(a.type, enum.Enum):
        return _update_enum(a)

    if a.type_origin is Literal:
        return _update_literal(a)

    if isinstance(a.type, type) and issubclass(a.type, bool):
        return _update_bool(a)

    return False


def _update_field_type(argument_args: Dict[str, Any]):
    a = _Argument(argument_args)
    iter_count = itertools.count()
    # Some types are recursive, so we iterate until no special type is matched
    while _update_field_type_internal(a) and next(iter_count) < _TYPE_RECURSION_LIMIT:
        a.update_type()

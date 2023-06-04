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
import sys
from typing import Any, Callable, Dict, Optional, Sequence, Type, TypeVar, Union, overload

from classparse.analyze import NAME_OR_FLAG, NO_ARG, POS_ARG
from classparse.proto import DataclassParserType
from classparse.transform import DataclassParserMaker, _transform_dataclass_parser

__version__ = "0.1.4"


def _field(**kwargs):
    if "kw_only" in kwargs and sys.version_info.major <= 3 and sys.version_info.minor <= 10:
        del kwargs["kw_only"]
    return dataclasses.field(**kwargs)


# noinspection PyShadowingBuiltins
def arg(
    *name_or_flag,
    default=dataclasses.MISSING,
    default_factory=dataclasses.MISSING,
    init=True,
    repr=True,  # pylint: disable=redefined-builtin
    hash=None,  # pylint: disable=redefined-builtin
    compare=True,
    kw_only=dataclasses.MISSING,
    **metadata,
):
    """
    Allow adding parameters to a named argument.
    See `argparse.add_argument()`.
    """
    if len(name_or_flag) > 0:
        metadata.update({NAME_OR_FLAG: name_or_flag})

    # Non positional fields must have a default value
    if default is dataclasses.MISSING and default_factory is dataclasses.MISSING:
        default = None

    return _field(
        default=default,
        default_factory=default_factory,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        kw_only=kw_only,
        metadata=metadata,
    )


# noinspection PyShadowingBuiltins
def pos_arg(
    default=dataclasses.MISSING,
    *,
    default_factory=dataclasses.MISSING,
    init=True,
    repr=True,  # pylint: disable=redefined-builtin
    hash=None,  # pylint: disable=redefined-builtin
    compare=True,
    kw_only=dataclasses.MISSING,
    **metadata,
):
    """
    Allow adding parameters to a positional argument.
    See `argparse.add_argument()`.
    """
    metadata.update({POS_ARG: True})
    return _field(
        default=default,
        default_factory=default_factory,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        kw_only=kw_only,
        metadata=metadata,
    )


# noinspection PyShadowingBuiltins
def no_arg(
    default=dataclasses.MISSING,
    *,
    default_factory=dataclasses.MISSING,
    init=True,
    repr=True,  # pylint: disable=redefined-builtin
    hash=None,  # pylint: disable=redefined-builtin
    compare=True,
    kw_only=dataclasses.MISSING,
    metadata=None,
):
    """Set dataclass field as non argparse argument"""
    no_arg_meta = {NO_ARG: True}
    if metadata is None:
        metadata = no_arg_meta
    else:
        metadata.update(no_arg_meta)
    return _field(
        default=default,
        default_factory=default_factory,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        kw_only=kw_only,
        metadata=metadata,
    )


_T = TypeVar("_T", bound=object)
InstanceOrClass = Union[Type[_T], _T]
DataClass = TypeVar("DataClass", bound=object)


def get_parser(
    instance_or_cls: InstanceOrClass[DataClass],
    *,
    default_argument_args: Optional[Dict[str, Any]] = None,
    load_defaults_from_file: bool = False,
    **parser_args,
) -> argparse.ArgumentParser:
    """See `DataclassParser.get_parser()`"""
    parser_maker = DataclassParserMaker(instance_or_cls, default_argument_args, load_defaults_from_file, **parser_args)
    return parser_maker.main_parser


def parse_args(
    instance_or_cls: InstanceOrClass[DataClass],
    args: Optional[Sequence[str]] = None,
    *,
    default_argument_args: Optional[Dict[str, Any]] = None,
    load_defaults_from_file: bool = False,
    **parser_args,
) -> DataClass:
    """See `DataclassParser.parse_args()`"""
    parser_maker = DataclassParserMaker(instance_or_cls, default_argument_args, load_defaults_from_file, **parser_args)
    return parser_maker.parse_args(instance_or_cls, args=args)


@overload
def classparser(
    cls: None = None, *, default_argument_args=None, load_defaults_from_file=False, **parser_args
) -> Callable[[Type[DataClass]], DataclassParserType[DataClass]]:
    ...  # pragma: no cover


@overload
def classparser(cls: Type[DataClass]) -> DataclassParserType[DataClass]:
    ...  # pragma: no cover


def classparser(cls=None, /, **kwargs):
    """Decorator that adds `DataclassParser` methods to the dataclass"""
    if cls is None:
        # The method is called with parentheses: @classparser().
        return functools.partial(_transform_dataclass_parser, kwargs=kwargs)

    # The method is called without parentheses: @classparser.
    return _transform_dataclass_parser(cls, kwargs)

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
from typing import Callable, Optional, Sequence, Type, TypeVar, Union, overload

from classparse.analyze import NO_ARG, POS_ARG
from classparse.proto import DataclassParser, DataclassParserType
from classparse.transform import DataclassParserMaker, _transform_dataclass_parser

__version__ = "0.1.4"


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


_T = TypeVar("_T", bound=object)
InstanceOrClass = Union[Type[_T], _T]
DataClass = TypeVar("DataClass", bound=object)


def make_parser(
    instance_or_cls: InstanceOrClass[DataClass], default_argument_args: Optional[dict] = None, **parser_args
) -> argparse.ArgumentParser:
    """Make an ArgumentParser from a dataclass"""
    return DataclassParserMaker(instance_or_cls, default_argument_args, **parser_args).main_parser


def parse_to(
    instance_or_cls: InstanceOrClass[DataClass],
    args: Optional[Sequence[str]] = None,
    default_argument_args: Optional[dict] = None,
    **parser_args,
) -> DataclassParser[DataClass]:
    """Parse arguments to a dataclass"""
    parser_maker = DataclassParserMaker(instance_or_cls, default_argument_args=default_argument_args, **parser_args)
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

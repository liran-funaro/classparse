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
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple, Type, TypeVar, Union

_T_co = TypeVar("_T_co", bound=object, covariant=True)


class DataclassParserProto(Protocol[_T_co]):  # pragma: no cover
    """
    This protocol describes the methods that are added to a dataclass that is decorated with @classparser.

    Note that all the below methods can be acted upon the class, or the class instance.
    The only difference between these two cases are the default values that are used.

    Default Values Policy:
        * If a method is called on the class: the class defaults will be used.
        * If a method is called on an instance: the instance values will be used as defaults.
    """

    def __new__(cls) -> "DataclassParser[_T_co]":  # type: ignore
        ...

    @classmethod
    def get_vars(cls) -> Dict[str, Any]:
        """
        Returns the variables of the class/instance as a dict, where the keys are represented in
        literal notation with words separated by underscores.
        """

    @classmethod
    def asdict(cls) -> Dict[str, Any]:
        """
        Returns the variables of the class/instance as a dict, where the keys are represented in
        argument notation with words separated by dashes.
        """

    @classmethod
    def from_dict(cls, namespace: Any) -> "DataclassParser[_T_co]":
        """
        Translate dict/object to this dataclass.
        The dict/object does not have to contain all the fields, and it may contain redundant fields.
        In such case, the redundant fields are ignored, and the missing fields are filled by their default values.
        See the "Default Values Policy" in this class description.
        """

    @classmethod
    def dump_yaml(cls, stream=None, sort_keys=False, **kwargs) -> Optional[str]:
        """Translates this class/instance into YAML. See `yaml.safe_dump()` for more information."""

    @classmethod
    def load_yaml(cls, stream) -> "DataclassParser[_T_co]":
        """
        Loads a YAML file and translate it to this dataclass.
        The dict/object does not have to contain all the fields, and it may contain redundant fields.
        In such case, the redundant fields are ignored, and the missing fields are filled by their default values.
        See the "Default Values Policy" in this class description.
        """

    @classmethod
    def get_parser(cls) -> argparse.ArgumentParser:
        """
        Returns an ArgumentParser representing this class/instance.
        The parser default values will be defined according to the "Default Values Policy" in this class description.
        Note that this parser output will be a usual Namespace object, not a dataclass.
        """

    @classmethod
    def format_help(cls) -> str:
        """Equivalent to `self.get_parser().format_help()`"""

    @classmethod
    def format_usage(cls) -> str:
        """Equivalent to `self.get_parser().format_usage()`"""

    @classmethod
    def print_help(cls, file=None):
        """Equivalent to `self.get_parser().print_help()`"""

    @classmethod
    def print_usage(cls, file=None):
        """Equivalent to `self.get_parser().print_usage()`"""

    @classmethod
    def parse_args(cls, args: Optional[Sequence[str]] = None) -> "DataclassParser[_T_co]":
        """
        Parses the arguments into a dataclass.
        The default values will be defined according to the "Default Values Policy" in this class description.
        See `argparse.ArgumentParser.parse_args()` for more information.
        """

    @classmethod
    def parse_intermixed_args(cls, args: Optional[Sequence[str]] = None) -> "DataclassParser[_T_co]":
        """
        Parses the arguments into a dataclass.
        The default values will be defined according to the "Default Values Policy" in this class description.
        See `argparse.ArgumentParser.parse_intermixed_args()` for more information.
        """

    @classmethod
    def parse_known_args(cls, args: Optional[Sequence[str]] = None) -> Tuple["DataclassParser[_T_co]", List[str]]:
        """
        Parses the arguments into a dataclass.
        The default values will be defined according to the "Default Values Policy" in this class description.
        See `argparse.ArgumentParser.parse_known_args()` for more information.
        """

    @classmethod
    def parse_known_intermixed_args(
        cls, args: Optional[Sequence[str]] = None
    ) -> Tuple["DataclassParser[_T_co]", List[str]]:
        """
        Parses the arguments into a dataclass.
        The default values will be defined according to the "Default Values Policy" in this class description.
        See `argparse.ArgumentParser.parse_known_intermixed_args()` for more information.
        """


DataclassParser = Union[_T_co, DataclassParserProto[_T_co]]
DataclassParserType = Union[Type[_T_co], Type[DataclassParserProto[_T_co]]]
DataclassParserInstanceOrClass = Union[DataclassParserType, DataclassParser]

dataclass_parser_methods: Tuple[str, ...] = tuple(
    method_name for method_name, method in vars(DataclassParserProto).items() if isinstance(method, classmethod)
)

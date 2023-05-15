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
import dataclasses
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, Literal, Optional, Tuple, Union

from classparse import arg, as_parser, no_arg, pos_arg, to_arg_name, to_var_name


class Action(Enum):
    Initialize = "init"
    Execute = "exec"


class Animal(Enum):
    Cat = auto()
    Dog = auto()


@as_parser(
    prog="my_program.py",  # Keyword arguments are passed to the parser init.
    default_argument_args=dict(help="(type: %(type)s)"),  # Set default arguments for each call of add_argument().
)
@dataclass(frozen=True)
class AllOptions:
    """
    Class doc string ==> parser description.
    The fields' inline comment ==> argument's help.
    """

    pos_arg_1: str  # Field with no explicit default ==> positional arguments (default=%(default)s)
    pos_arg_2: int = pos_arg(
        5,
        nargs="?",
        help=(
            "pos_arg() is a wrapper around dataclasses.field()."
            "The first argument (optional) is the argument default (default=%(default)s)."
            "The following keyword arguments can be any argparse.add_argument() parameter."
        ),
    )  # When the help field is specified explicitly, the inline comment is ignored
    int_arg: int = 1  # Field's type and default are applied to the parser (type=%(type)s, default=%(default)s)
    str_enum_choice_arg: Action = Action.Initialize  # StrEnum ==> choice argument (type=%(type)s, default=%(default)s)
    int_enum_choice_arg: Animal = Animal.Cat  # IntEnum ==> choice argument (type=%(type)s, default=%(default)s)
    literal_arg: Literal["a", "b", "c"] = None  # Literal ==> choice argument (type=%(type)s, default=%(default)s)
    literal_int_arg: Literal[1, 2, 3] = None  # Literal's type is automatically inferred (type=%(type)s)
    mixed_literal: Literal[1, 2, "3", "4", True, Animal.Cat] = None  # We can mix multiple literal types (type=%(type)s)
    optional_arg: Optional[int] = None  # Optional can be used for type hinting (type=%(type)s)
    just_optional_arg: Optional = None  # Bare optional also works (type=%(type)s)
    optional_choice_arg: Optional[Action] = None  # Nested types are supported (type=%(type)s)
    union_arg: Union[int, float, bool] = None  # Tries to convert to type in order until first success (type=%(type)s)
    path_arg: Path = None
    flag_arg: int = arg(
        "-f",
        help=(
            "arg() is a wrapper around dataclasses.field()."
            "The first argument (optional) is the short argument name."
            "The following keyword arguments can be any argparse.add_argument() parameter."
        ),
        default=1,
    )
    required_arg: float = arg("-r", required=True)  # E.g., required=%(required)s
    metavar_arg: str = arg(metavar="M")  # E.g., metavar=%(metavar)s
    int_list: List[int] = (1,)  # List type hint ==> nargs="+" (type=%(type)s)
    int_2_list: Tuple[int, int] = (1, 2)  # Tuple type hint ==> nargs=<tuple length> (nargs=%(nargs)s, type=%(type)s)
    multi_type_tuple: Tuple[int, float, str] = (1, 1e-3, "a")  # We can use multiple types (type=%(type)s)
    actions: List[Action] = ()  # List[Enum] ==> choices with nargs="+" (nargs=%(nargs)s, type=%(type)s)
    animals: List[Animal] = ()  # List[Enum] ==> choices with nargs="+" (nargs=%(nargs)s, type=%(type)s)
    literal_list: List[Literal["aa", "bb", 11, 22, Animal.Cat]] = ("aa",)  # List[Literal] ==> choices with nargs="+"
    union_list: List[Union[int, float, str, bool]] = ()
    union_with_literal: List[Union[Literal["a", "b", 1, 2], float, bool]] = ()
    typeless_list: list = ()  # If list type is unspecified, then it uses argparse default (type=%(type)s)
    typeless_typing_list: List = ()  # typing.List or list are supported
    none_bool_arg: bool = None  # boolean args ==> argparse.BooleanOptionalAction (type=%(type)s)
    true_bool_arg: bool = True  # We can set any default value
    false_bool_arg: bool = False
    complex_arg: complex = complex(1, -1)

    # no_arg() is used to not include this argument in the parser.
    # The first argument (optional) sets the default value.
    # The following keyword arguments is forwarded to the dataclasses.field() method.
    no_arg: int = no_arg(0)

    # We used this argument for the README example.
    # Note that comments above the arg are also included in the help of the argument.
    # This is a convenient way to include long help messages.
    show: List[str] = arg("-s", default=())

    def __repr__(self):
        """Print only the specified fields"""
        fields = self.show or list(dataclasses.asdict(self))
        return "\n".join([f"{to_arg_name(k)}: {getattr(self, to_var_name(k))}" for k in fields])


if __name__ == "__main__":
    print(AllOptions.parse_args())

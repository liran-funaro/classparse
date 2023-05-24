<!---
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
--->

# classparse

[![Coverage Status](https://coveralls.io/repos/github/liran-funaro/classparse/badge.svg?branch=main)](https://coveralls.io/github/liran-funaro/classparse?branch=main)

Declarative `ArgumentParser` definition with `dataclass` notation.
 - No `ArgumentParser` boilerplate code
 - IDE autocompletion and type hints

# Install
```bash
pip install classparse==0.1.4
```

# Simple Example
This is a simple example of the most basic usage of this library.
<!-- embed: examples/simple.py -->

```python
# examples/simple.py
from dataclasses import dataclass

from classparse import classparser

@classparser
@dataclass
class SimpleArgs:
    """My simple program's arguments"""

    retries: int = 5  # number of retries
    eps: float = 1e-3  # epsilon

if __name__ == "__main__":
    print(SimpleArgs.parse_args())
```

<!-- execute: python examples/simple.py --help -->
```bash
$ python examples/simple.py --help
usage: simple.py [-h] [--retries RETRIES] [--eps EPS]

My simple program's arguments

options:
  -h, --help         show this help message and exit
  --retries RETRIES  number of retries
  --eps EPS          epsilon
```

<!-- execute: python examples/simple.py --retries 10 --eps 1e-6 -->
```text
$ python examples/simple.py --retries 10 --eps 1e-6
SimpleArgs(retries=10, eps=1e-06)
```

# Exhaustive Usage Example
This example demonstrates all the usage scenarios of this library.
<!-- embed: examples/usage.py -->

```python
# examples/usage.py
import dataclasses
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, Literal, Optional, Tuple, Union

from classparse import arg, classparser, no_arg, pos_arg, to_arg_name, to_var_name

class Action(Enum):
    Initialize = "init"
    Execute = "exec"

class Animal(Enum):
    Cat = auto()
    Dog = auto()

@classparser(
    prog="my_program.py",  # Keyword arguments are passed to the parser init.
    default_argument_args=dict(help="(type: %(type)s)"),  # Set default arguments for each call of add_argument().
)
@dataclass(frozen=True)
class AllOptions:
    """
    Class doc string ==> parser description.
    The fields' inline/above comment ==> argument's help.
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
```

<!-- execute: python examples/usage.py --help -->
```text
$ python examples/usage.py --help
usage: my_program.py [-h] [--int-arg INT_ARG]
                     [--str-enum-choice-arg {Initialize/init,Execute/exec}]
                     [--int-enum-choice-arg {Cat/1,Dog/2}]
                     [--literal-arg {a,b,c}] [--literal-int-arg {1,2,3}]
                     [--mixed-literal {1,2,3,4,True,Cat/1}]
                     [--optional-arg OPTIONAL_ARG]
                     [--just-optional-arg JUST_OPTIONAL_ARG]
                     [--optional-choice-arg {Initialize/init,Execute/exec}]
                     [--union-arg UNION_ARG] [--path-arg PATH_ARG]
                     [-f FLAG_ARG] -r REQUIRED_ARG [--metavar-arg M]
                     [--int-list INT_LIST [INT_LIST ...]]
                     [--int-2-list INT_2_LIST INT_2_LIST]
                     [--multi-type-tuple MULTI_TYPE_TUPLE MULTI_TYPE_TUPLE MULTI_TYPE_TUPLE]
                     [--actions {Initialize/init,Execute/exec} [{Initialize/init,Execute/exec} ...]]
                     [--animals {Cat/1,Dog/2} [{Cat/1,Dog/2} ...]]
                     [--literal-list {aa,bb,11,22,Cat/1} [{aa,bb,11,22,Cat/1} ...]]
                     [--union-list UNION_LIST [UNION_LIST ...]]
                     [--union-with-literal UNION_WITH_LITERAL [UNION_WITH_LITERAL ...]]
                     [--typeless-list TYPELESS_LIST [TYPELESS_LIST ...]]
                     [--typeless-typing-list TYPELESS_TYPING_LIST [TYPELESS_TYPING_LIST ...]]
                     [--none-bool-arg | --no-none-bool-arg]
                     [--true-bool-arg | --no-true-bool-arg]
                     [--false-bool-arg | --no-false-bool-arg]
                     [--complex-arg COMPLEX_ARG] [-s SHOW [SHOW ...]]
                     pos-arg-1 [pos-arg-2]

Class doc string ==> parser description. The fields' inline/above comment ==>
argument's help.

positional arguments:
  pos-arg-1             Field with no explicit default ==> positional
                        arguments (default=None)
  pos-arg-2             pos_arg() is a wrapper around dataclasses.field().The
                        first argument (optional) is the argument default
                        (default=5).The following keyword arguments can be any
                        argparse.add_argument() parameter.

options:
  -h, --help            show this help message and exit
  --int-arg INT_ARG     Field's type and default are applied to the parser
                        (type=int, default=1)
  --str-enum-choice-arg {Initialize/init,Execute/exec}
                        StrEnum ==> choice argument (type=Action,
                        default=Initialize)
  --int-enum-choice-arg {Cat/1,Dog/2}
                        IntEnum ==> choice argument (type=Animal, default=Cat)
  --literal-arg {a,b,c}
                        Literal ==> choice argument (type=str, default=None)
  --literal-int-arg {1,2,3}
                        Literal's type is automatically inferred (type=int)
  --mixed-literal {1,2,3,4,True,Cat/1}
                        We can mix multiple literal types
                        (type=typing.Literal[1, 2, '3', '4', True,
                        <Animal.Cat: 1>])
  --optional-arg OPTIONAL_ARG
                        Optional can be used for type hinting (type=int)
  --just-optional-arg JUST_OPTIONAL_ARG
                        Bare optional also works (type=None)
  --optional-choice-arg {Initialize/init,Execute/exec}
                        Nested types are supported (type=Action)
  --union-arg UNION_ARG
                        Tries to convert to type in order until first success
                        (type=typing.Union[int, float, bool])
  --path-arg PATH_ARG   (type: Path)
  -f FLAG_ARG, --flag-arg FLAG_ARG
                        arg() is a wrapper around dataclasses.field().The
                        first argument (optional) is the short argument
                        name.The following keyword arguments can be any
                        argparse.add_argument() parameter.
  -r REQUIRED_ARG, --required-arg REQUIRED_ARG
                        E.g., required=True
  --metavar-arg M       E.g., metavar=M
  --int-list INT_LIST [INT_LIST ...]
                        List type hint ==> nargs="+" (type=int)
  --int-2-list INT_2_LIST INT_2_LIST
                        Tuple type hint ==> nargs=<tuple length> (nargs=2,
                        type=int)
  --multi-type-tuple MULTI_TYPE_TUPLE MULTI_TYPE_TUPLE MULTI_TYPE_TUPLE
                        We can use multiple types (type=typing.Union[int,
                        float, str])
  --actions {Initialize/init,Execute/exec} [{Initialize/init,Execute/exec} ...]
                        List[Enum] ==> choices with nargs="+" (nargs=+,
                        type=Action)
  --animals {Cat/1,Dog/2} [{Cat/1,Dog/2} ...]
                        List[Enum] ==> choices with nargs="+" (nargs=+,
                        type=Animal)
  --literal-list {aa,bb,11,22,Cat/1} [{aa,bb,11,22,Cat/1} ...]
                        List[Literal] ==> choices with nargs="+"
  --union-list UNION_LIST [UNION_LIST ...]
                        (type: typing.Union[int, float, str, bool])
  --union-with-literal UNION_WITH_LITERAL [UNION_WITH_LITERAL ...]
                        (type: typing.Union[typing.Literal['a', 'b', 1, 2],
                        float, bool])
  --typeless-list TYPELESS_LIST [TYPELESS_LIST ...]
                        If list type is unspecified, then it uses argparse
                        default (type=None)
  --typeless-typing-list TYPELESS_TYPING_LIST [TYPELESS_TYPING_LIST ...]
                        typing.List or list are supported
  --none-bool-arg, --no-none-bool-arg
                        boolean args ==> argparse.BooleanOptionalAction
                        (type=bool)
  --true-bool-arg, --no-true-bool-arg
                        We can set any default value (default: True)
  --false-bool-arg, --no-false-bool-arg
                        (type: bool) (default: False)
  --complex-arg COMPLEX_ARG
                        (type: complex)
  -s SHOW [SHOW ...], --show SHOW [SHOW ...]
                        We used this argument for the README example. Note
                        that comments above the arg are also included in the
                        help of the argument. This is a convenient way to
                        include long help messages.
```

Note that for Enums, we can use either the enum name or its value.
<!-- execute: python examples/usage.py str-choices --actions Initialize init Execute exec -r1 -s actions -->
```text
$ python examples/usage.py str-choices --actions Initialize init Execute exec -r1 -s actions
actions: [<Action.Initialize: 'init'>, <Action.Initialize: 'init'>, <Action.Execute: 'exec'>, <Action.Execute: 'exec'>]
```
<!-- execute: python examples/usage.py int-choices --animals Cat 1 Dog 2 -r1 -s animals -->
```text
$ python examples/usage.py int-choices --animals Cat 1 Dog 2 -r1 -s animals
animals: [<Animal.Cat: 1>, <Animal.Cat: 1>, <Animal.Dog: 2>, <Animal.Dog: 2>]
```

# Alternatives

#### [mivade/argparse_dataclass](https://github.com/mivade/argparse_dataclass)
  - Allow transforming dataclass to `ArgumentParser`.
  - Missing features:
    - `Enum` support
    - `arg/pos_arg/no_arg` functionality
    - Implicit positional argument
    - `nargs` support

#### [lebrice/simple-parsing](https://github.com/lebrice/SimpleParsing)
  - Allow adding dataclass to `ArgumentParser` by using `parser.add_arguments()`
  - Requires boilerplate code to create the parser
  - Positional arguments
  - `nargs` support

### [swansonk14/typed-argument-parser](https://github.com/swansonk14/typed-argument-parser)
  - Creating argument parser from classes and functions
  - Rich functionality
  - Post-processing of arguments
  - Save/load arguments
  - Load from dict

# License

[BSD-3](LICENSE)

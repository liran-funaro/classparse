"""
Unittests for `classparse`.

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
import sys

import pytest
import contextlib
import dataclasses
import enum
import io
from dataclasses import dataclass

from examples.usage import AllOptions, Action, Animal
from examples.test_one_arg import SimpleTestClass
from examples.no_source import NoSourceTestClass
from classparse import parse_to


# class DefaultsAndTypesHelpFormatter(argparse.HelpFormatter):
#     """
#     Taken from https://stackoverflow.com/questions/26479254/argparse-include-default-value-and-type-in-help
#     """
#
#     def _get_help_string(self, action):
#         help_str = action.help
#
#         if '%(default)' not in help_str and action.default is not argparse.SUPPRESS:
#             help_str += ' (default: %(default)s)'
#
#         if '%(type)s' not in help_str and action.type is not argparse.SUPPRESS:
#             help_str += ' (type: %(type)s)'
#
#         return help_str


def value_to_str(value):
    if isinstance(value, enum.Enum):
        return str(value.value)
    else:
        return str(value)


def name_to_str(value):
    if isinstance(value, enum.Enum):
        return str(value.name)
    else:
        return str(value)


def no_bool_support():
    return sys.version_info.major >= 3 and sys.version_info.minor >= 9


def dataclass_to_args(d: dataclass, enum_value_func=value_to_str):
    args = []
    for k, v in vars(d).items():
        if "pos" in k:
            args.append(enum_value_func(v))

    for k, v in vars(d).items():
        if k == 'no_arg' or 'pos' in k or v is None:
            continue
        field = k.replace("_", "-")
        if isinstance(v, (list, tuple)):
            if len(v) > 0:
                args.extend([f'--{field}', *map(enum_value_func, v)])
        elif isinstance(v, bool):
            if v:
                args.append(f'--{field}')
            elif no_bool_support():
                args.append(f'--no-{field}')
        else:
            args.extend([f'--{field}', enum_value_func(v)])
    return args


@pytest.mark.parametrize("uut", [AllOptions('a'), NoSourceTestClass('a')], ids=['AllOptions', 'NoSourceTestClass'])
def test_show_test_class(uut: dataclasses.dataclass):
    print()
    print(uut.__class__.__name__)
    for k, v in dataclasses.asdict(uut).items():
        print(f"{k:>20s}: {v}")


@pytest.mark.parametrize("uut", [AllOptions, NoSourceTestClass])
def test_help(uut: dataclasses.dataclass):
    with io.StringIO() as f:
        with pytest.raises(SystemExit) as cm:
            with contextlib.redirect_stdout(f):
                uut.parse_args(args=['--help'])
        out = str(f.getvalue())

    print()
    print(out)
    assert cm.value.code == 0
    assert uut.__doc__.strip().splitlines()[0].strip() in out


def test_default_parameters():
    # noinspection PyTypeChecker
    expected_params = AllOptions('a', required_arg=1e-6)
    p = AllOptions.parse_args(args=['a', '--required-arg', '1e-6'])
    assert expected_params == p


@pytest.mark.parametrize("enum_value_func", [value_to_str, name_to_str])
def test_all_parameters(enum_value_func):
    # noinspection PyTypeChecker
    expected_params = AllOptions(
        pos_arg_1="a",
        pos_arg_2=300,
        int_arg=10,
        str_enum_choice_arg=Action.Execute,
        int_enum_choice_arg=Animal.Dog,
        literal_arg='b',
        literal_int_arg=2,
        just_optional_arg="test-opt",
        optional_arg=100,
        optional_choice_arg=Action.Initialize,
        union_arg=1e-3,
        union_list=[500, 1e-8, 'test-union'],
        flag_arg=20,
        required_arg=1e-6,
        int_list=[30, 40],
        int_2_list=[5, 6],
        actions=[Action.Initialize, Action.Execute],
        animals=[Animal.Cat, Animal.Dog],
        literal_list=['bb', 'bb', 'aa'],
        typeless_list=["a", "b"],
        typeless_typing_list=["c", "d"],
        none_bool_arg=True,
        true_bool_arg=not no_bool_support(),
        false_bool_arg=True,
    )
    args = dataclass_to_args(expected_params, enum_value_func=enum_value_func)
    print(args)
    p = AllOptions.parse_args(args=args)
    assert expected_params == p


def test_simple_all_parameters():
    expected_params = SimpleTestClass(one_arg="test")
    p = SimpleTestClass.parse_args(args=dataclass_to_args(expected_params))
    assert expected_params == p


def test_simple_no_decorator():
    expected_params = SimpleTestClass(one_arg="test")
    p = parse_to(SimpleTestClass, args=dataclass_to_args(expected_params))
    assert expected_params == p


def test_bad_union_type():
    with pytest.raises(SystemExit) as cm:
        AllOptions.parse_args(args=['--union-arg', 'not-number'])


def test_non_dataclass():
    class Fake:
        pass

    with pytest.raises(TypeError) as cm:
        parse_to(Fake)

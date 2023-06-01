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
import argparse
import contextlib
import dataclasses
import enum
import io
import sys
from pathlib import Path
from typing import Type, Union

import pytest

import classparse
import classparse.analyze
from classparse import DataclassParser, make_parser, parse_to
from classparse.transform import DataclassNamespace
from examples.load_defaults import SimpleLoadDefaults
from examples.no_source import NoSourceTestClass
from examples.one_arg import OneArgClass, OneArgNoParserClass
from examples.simple import SimpleArgs
from examples.usage import Action, AllOptions, Animal, Child, SubChild


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


def convert_tuple_to_list(d):
    return dataclasses.replace(d, **{k: list(v) for k, v in vars(d).items() if isinstance(v, tuple)})


def key_value_to_args(k: str, v, enum_value_func=value_to_str, prefix=""):
    if k == "no_arg" or "pos" in k or v is None:
        return
    field = prefix + k.replace("_", "-")

    if isinstance(v, dict) or dataclasses.is_dataclass(v):
        yield from dataclass_to_args(v, enum_value_func=enum_value_func, prefix=f"{field}.")
    elif isinstance(v, (list, tuple)):
        if len(v) > 0:
            yield f"--{field}"
            yield from map(enum_value_func, v)
    elif isinstance(v, bool):
        if v:
            yield f"--{field}"
        elif no_bool_support():
            yield f"--no-{field}"
    else:
        yield f"--{field}"
        yield enum_value_func(v)


def dataclass_to_args(instance_or_cls, enum_value_func=value_to_str, prefix=""):
    if dataclasses.is_dataclass(instance_or_cls):
        dct = dataclasses.asdict(instance_or_cls)
    else:
        assert isinstance(instance_or_cls, dict)
        dct = instance_or_cls

    args = []

    for k, v in dct.items():
        if "pos" in k:
            args.append(enum_value_func(v))

    for k, v in dct.items():
        args.extend(key_value_to_args(k, v, enum_value_func=enum_value_func, prefix=prefix))

    return args


AllOptionsAllSet = AllOptions(
    pos_arg_1="a",
    pos_arg_2=300,
    int_arg=10,
    str_enum_choice_arg=Action.Execute,
    int_enum_choice_arg=Animal.Dog,
    literal_arg="b",
    literal_int_arg=2,
    mixed_literal=2,
    just_optional_arg="test-opt",
    optional_arg=100,
    optional_choice_arg=Action.Initialize,
    union_arg=1e-3,
    union_list=[500, 1e-8, "test-union", False, True],
    flag_arg=20,
    required_arg=1e-6,
    int_list=[30, 40],
    int_2_list=[5, 6],
    multi_type_tuple=[100, 1e-10, "test"],
    actions=[Action.Initialize, Action.Execute],
    animals=[Animal.Cat, Animal.Dog],
    literal_list=["bb", "bb", "aa", 22, Animal.Cat],
    typeless_list=["a", "b"],
    typeless_typing_list=["c", "d"],
    none_bool_arg=True,
    true_bool_arg=not no_bool_support(),
    false_bool_arg=True,
    path_arg=Path("/a/b"),
    complex_arg=complex(-1, 2),
    union_with_literal=["a", "b", 2, 1],
    group_arg=Child(str_arg="abc", child_arg=SubChild(str_arg="efg")),
    default_child_arg=Child(str_arg="def-abc", child_arg=SubChild(str_arg="def-efg")),
)

AllOptionsJustRequired = AllOptions("a", required_arg=1e-6)

OPTIONS = [AllOptions, AllOptionsAllSet, AllOptionsJustRequired, NoSourceTestClass("a"), SimpleArgs()]
IDS = ["AllOptions class", "AllOptionsAllSet", "AllOptionsJustRequired", "NoSourceTestClass", "SimpleArgs"]


@pytest.mark.parametrize("uut", OPTIONS, ids=IDS)
def test_show_test_class(uut: DataclassParser):
    print()
    print(uut.__class__.__name__)
    for k, v in uut.asdict().items():
        print(f"{k:>20s}: {v}")


@pytest.mark.parametrize("uut", [AllOptions, SimpleArgs, SimpleLoadDefaults, OneArgClass, NoSourceTestClass])
def test_help(uut: DataclassParser):
    expected_in_help = uut.__doc__.strip().splitlines()[0].strip()
    expected_in_usage = "usage:"
    help_str = uut.format_help()
    print()
    print(help_str)
    assert expected_in_help in help_str

    with io.StringIO() as f:
        uut.print_help(file=f)
        help_str = str(f.getvalue())
    assert expected_in_help in help_str

    with io.StringIO() as f:
        with pytest.raises(SystemExit) as cm:
            with contextlib.redirect_stdout(f):
                uut.parse_args(args=["--help"])
        help_str = str(f.getvalue())

    assert cm.value.code == 0
    assert expected_in_help in help_str

    usage_str = uut.format_usage()
    assert expected_in_usage in usage_str

    with io.StringIO() as f:
        uut.print_usage(file=f)
        usage_str = str(f.getvalue())
    assert expected_in_usage in usage_str


@pytest.mark.parametrize("uut", OPTIONS, ids=IDS)
def test_transformers(uut: Union[DataclassParser, Type[DataclassParser]]):
    if isinstance(uut, type):
        try:
            expected_params = uut()
        except TypeError:
            expected_params = uut(None)
        actor = [uut, expected_params]
    else:
        expected_params = uut
        actor = [type(uut), expected_params]

    for act in actor:
        dict_obj = uut.asdict()
        p = act.from_dict(dict_obj)
        assert expected_params == p

        dict_obj = uut.get_vars()
        p = act.from_dict(dict_obj)
        assert expected_params == p

        p = act.from_dict(expected_params)
        assert expected_params == p

        yaml_str = uut.dump_yaml()
        p = act.load_yaml(yaml_str)
        assert convert_tuple_to_list(expected_params) == p


def test_default_parameters():
    expected_params = AllOptions("a", required_arg=1e-6)
    p = AllOptions.parse_args(args=["a", "--required-arg", "1e-6"])
    assert expected_params == p


@pytest.mark.parametrize("enum_value_func", [value_to_str, name_to_str])
def test_all_parameters(enum_value_func):
    expected_params = AllOptionsAllSet
    args = dataclass_to_args(expected_params, enum_value_func=enum_value_func)
    print()
    print(args)
    p1 = AllOptions.parse_args(args=args)
    print(p1)
    assert isinstance(p1, AllOptions)
    assert expected_params == p1

    expected_params2 = dataclasses.replace(p1, pos_arg_1="b", required_arg=1e-7, int_arg=1_000, show=["a", "b", "c"])
    args = ["b", "-r", "1e-7", "--int-arg", "1_000", "--show", "a", "b", "c"]

    unknown_args = ["--fake-arg", "5"]
    parse_known_funcs = "parse_known_args", "parse_known_intermixed_args"
    parse_funcs = "parse_args", "parse_intermixed_args"
    uuts = p1, expected_params, expected_params2
    for u in uuts:
        for func_name in parse_funcs:
            func = getattr(u, func_name)
            p2 = func(args=args)
            assert isinstance(p2, AllOptions), f"Func: {func_name}"
            assert expected_params2 == p2, f"Func: {func_name}"

        for func_name in parse_known_funcs:
            func = getattr(u, func_name)
            p2, a = func(args=[*args, *unknown_args])
            assert isinstance(p2, AllOptions), f"Func: {func_name}"
            assert expected_params2 == p2, f"Func: {func_name}"
            assert a == unknown_args, f"Func: {func_name}"

        u_parser = u.get_parser()
        assert isinstance(u_parser, argparse.ArgumentParser)
        for func_name in parse_funcs:
            func = getattr(u_parser, func_name)
            # noinspection PyArgumentList
            namespace = func(args=args)
            res_vars = classparse.analyze.namespace_to_vars(vars(namespace))
            p2_vars = expected_params2.get_vars()
            del p2_vars["no_arg"]
            assert res_vars == p2_vars

        for func_name in parse_known_funcs:
            func = getattr(u_parser, func_name)
            # noinspection PyArgumentList
            namespace, a = func(args=[*args, *unknown_args])
            assert a == unknown_args
            res_vars = classparse.analyze.namespace_to_vars(vars(namespace))
            p2_vars = expected_params2.get_vars()
            del p2_vars["no_arg"]
            assert res_vars == p2_vars


def test_simple_all_parameters():
    expected_params = OneArgClass(one_arg="test")
    p = OneArgClass.parse_args(args=dataclass_to_args(expected_params))
    assert expected_params == p


@pytest.mark.parametrize(
    "uut",
    [OneArgNoParserClass, OneArgNoParserClass(), OneArgNoParserClass(one_arg="test")],
    ids=["OneArgNoParserClass class", "OneArgNoParserClass empty init", "OneArgNoParserClass with init"],
)
def test_simple_no_decorator(uut):
    expected_params = OneArgNoParserClass(one_arg="exp-test")
    args = dataclass_to_args(expected_params)

    p = parse_to(uut, args=args)
    assert expected_params == p

    parser = make_parser(uut)
    namespace = parser.parse_args(args=args)
    res_dict = {k: v for k, v in vars(namespace).items()}
    p_dict = dataclasses.asdict(expected_params)
    assert res_dict == p_dict


def test_bad_union_type():
    with pytest.raises(SystemExit):
        AllOptions.parse_args(args=["--union-arg", "not-number"])


def test_bad_literal():
    with pytest.raises(SystemExit):
        AllOptions.parse_args(args=["--mixed-literal", "invalid"])


def test_bad_literal_in_union():
    with pytest.raises(SystemExit):
        AllOptions.parse_args(args=["--union-with-literal", "invalid"])


def test_non_dataclass():
    class Fake:
        pass

    with pytest.raises(TypeError):
        parse_to(Fake)


def test_load_defaults(tmpdir):
    defaults = SimpleLoadDefaults(retries=10, eps=1e-10)
    defaults_yaml = tmpdir.join("defaults.yaml")
    with defaults_yaml.open("w") as f:
        defaults.dump_yaml(f)

    expected_params = SimpleLoadDefaults(retries=10, eps=1e-9)
    p0 = SimpleLoadDefaults.parse_args(["--retries", "10", "--eps", "1e-9"])
    assert p0 == expected_params

    p1 = SimpleLoadDefaults.parse_args(["--load-defaults", str(defaults_yaml), "--eps", "1e-9"])
    assert p1 == expected_params

    p2 = defaults.parse_args(["--eps", "1e-9"])
    assert p2 == expected_params

    with io.StringIO() as f:
        with pytest.raises(SystemExit) as cm:
            with contextlib.redirect_stderr(f):
                SimpleLoadDefaults.parse_args(["--load-defaults", "/bad/path", "--eps", "1e-9"])
        help_str = str(f.getvalue())

    print()
    print(help_str)
    assert cm.value.code == 2
    assert "[--load-defaults PATH]" in help_str
    assert "[--load-defaults PATH]" in help_str
    assert "[--eps EPS]" in help_str

    # Make sure we allow showing help after we load the defaults from the YAML file
    with io.StringIO() as f:
        with pytest.raises(SystemExit) as cm:
            with contextlib.redirect_stdout(f):
                SimpleLoadDefaults.parse_args(args=["--load-defaults", str(defaults_yaml), "--help"])
        help_str = str(f.getvalue())

    print()
    print(help_str)
    assert cm.value.code == 0
    assert "[--load-defaults PATH]" in help_str
    assert "[--load-defaults PATH]" in help_str
    assert "[--eps EPS]" in help_str
    assert "retries-default: 10" in help_str
    assert "eps-default: 1e-10" in help_str


def test_dataclass_namespace():
    c = DataclassNamespace({"a", "b"})
    assert hasattr(c, "a")
    assert hasattr(c, "b")
    assert not hasattr(c, "c")
    assert not isinstance(c.a, str)
    assert not isinstance(c.b, str)

    c.c = "c-test"
    assert hasattr(c, "c")
    assert c.c == "c-test"

    c.b = "b-test"
    assert hasattr(c, "b")
    assert c.b == "b-test"

    c_str = str(c)
    print(c_str)
    assert "c='c-test'" in c_str
    assert "b='b-test'" in c_str
    assert "a=" not in c_str

    assert "a" in c
    assert "b" in c
    assert "c" in c

    c1 = DataclassNamespace({"a", "b"})
    assert c != c1
    c1.b = "b-test"
    c1.c = "c-test"
    assert c == c1

    assert c != "string"

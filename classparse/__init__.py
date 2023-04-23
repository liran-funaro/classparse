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
import enum
import inspect
import itertools
import tokenize
import typing
import io

__version__ = "0.1.0"

NO_ARG = '__no_arg__'
POS_ARG = '__pos_arg__'
__TYPE_RECURSION_LIMIT = 1024


def arg(flag=None, default=None, **metadata):
    """
    Allow adding parameters to a named argument.
    See `argparse.add_argument()`.
    """
    if flag is not None:
        metadata.update(flag=flag)
    return dataclasses.field(default=default, metadata=metadata)


def pos_arg(default=dataclasses.MISSING, **metadata):
    """
    Allow adding parameters to a positional argument.
    See `argparse.add_argument()`.
    """
    return dataclasses.field(default=default, metadata={POS_ARG: True, **metadata})


def no_arg(default=None, **kwargs):
    """ Set dataclass field as non argparse argument """
    metadata = kwargs.setdefault('metadata', {})
    metadata[NO_ARG] = True
    return dataclasses.field(default=default, **kwargs)


def _name_or_flags_arg(arg_name: str, flag: typing.Optional[str] = None,
                       positional: bool = False) -> typing.Iterable[str]:
    arg_name = arg_name.replace('_', '-')
    if positional:
        assert flag is None, "Flag is not supported for positional argument"
        return [arg_name]
    return filter(None, [flag, f"--{arg_name}"])


def _is_missing_default(default_value) -> bool:
    return default_value is dataclasses.MISSING


def __wrap_enum(enum_type):
    # noinspection PyBroadException
    def __enum_wrapper__(x):
        try:
            return enum_type(int(x))
        except Exception:
            pass

        try:
            return enum_type(x)
        except Exception:
            return enum_type[x]

    __enum_wrapper__.__name__ = enum_type.__name__
    return __enum_wrapper__


def __wrap_union(union: typing.Union, arg_set: typing.List[type]):
    name = repr(union)

    # noinspection PyBroadException
    def __union_wrapper__(x):
        e_list = []
        for arg_type in arg_set:
            try:
                return arg_type(x)
            except Exception as e:
                e_list.append(f'{arg_type}: {e}')

        raise TypeError(f"Could not apply any of the types in {name}: {', '.join(e_list)}.")

    __union_wrapper__.__name__ = name
    return __union_wrapper__


def _update_field_type(argument_args: dict) -> bool:
    """ Return `True` if the type was reassigned, and it requires to inspect it again """
    cur_type = argument_args.get('type', None)
    cur_origin = typing.get_origin(cur_type)
    cur_args: tuple = typing.get_args(cur_type)

    if cur_type is typing.Optional:
        # Optional annotation without a type
        del argument_args['type']
        return False

    if cur_origin is typing.Union:
        # Optional annotation with a type (interpreted as a Union), Union
        arg_set = [v for v in cur_args if not issubclass(v, type(None)) and v is not None]
        if len(arg_set) == 1:
            # For union of one type (other than None), we support further inspection of the type
            argument_args['type'] = cur_args[0]
            return True
        else:
            argument_args['type'] = __wrap_union(cur_type, arg_set)
            return False

    if cur_type in (list, tuple) or cur_origin is list:
        # List/Tuple type/annotation is used to define a repeated argument
        argument_args.setdefault('nargs', '+')
        if len(cur_args) > 0:
            arg_set = list(set(cur_args))
            assert len(arg_set) == 1, "All args must be of the same type"
            argument_args['type'] = cur_args[0]
            return True
        else:
            del argument_args['type']
            return False

    if cur_origin is tuple:
        # Tuple annotation is used to define a fixed length repeated argument
        argument_args.setdefault('nargs', len(cur_args))
        arg_set = list(set(cur_args))
        assert len(arg_set) == 1, "All args must be of the same type"
        argument_args['type'] = cur_args[0]
        return True

    if isinstance(cur_type, type) and issubclass(cur_type, enum.Enum):
        # Enum type is used to define a typed choice argument
        choices = list(cur_type)
        argument_args['choices'] = choices
        argument_args['metavar'] = '{%s}' % ",".join([f'{c.name}/{c.value}' for c in choices])
        cur_default = argument_args.get('default', None)
        if isinstance(cur_default, enum.Enum):
            argument_args['default'] = cur_default.name
        argument_args['type'] = __wrap_enum(cur_type)
        return False

    if cur_origin is typing.Literal:
        # Literal type is used to define an untyped choice argument
        argument_args['choices'] = list(cur_args)
        cur_types = list({type(a) for a in cur_args})
        assert len(cur_types) == 1, "All literals must be of the same type"
        argument_args['type'] = cur_types[0]
        return True

    if isinstance(cur_type, type) and issubclass(cur_type, bool):
        # bool type is used to define a store_true argument
        if hasattr(argparse, 'BooleanOptionalAction'):
            argument_args['action'] = argparse.BooleanOptionalAction
        else:
            argument_args['action'] = 'store_true'
            del argument_args['type']
        return False

    return False


def _add_argument_from_field(parser: argparse.ArgumentParser, field: dataclasses.Field, docs: typing.Dict[str, str],
                             **default_argument_args):
    # Override default arguments by explicit field arguments
    argument_args = dict(default_argument_args)
    argument_args.update(field.metadata)
    flag = argument_args.pop('flag', None)
    is_no_arg = argument_args.pop(NO_ARG, False)
    is_positional = argument_args.pop(POS_ARG, False)
    if is_no_arg:
        return

    # Override type unless set explicitly
    if 'type' not in field.metadata:
        argument_args['type'] = field.type

    # Override help unless set explicitly
    field_doc = docs.get(field.name, None)
    if 'help' not in field.metadata and field_doc is not None:
        argument_args['help'] = field_doc

    # Override default unless set explicitly
    no_default = _is_missing_default(field.default)
    if 'default' not in field.metadata and not no_default:
        argument_args['default'] = field.default

    # Some types are recursive, so we iterate until no special type is matched
    iter_count = itertools.count()
    while _update_field_type(argument_args) and next(iter_count) < __TYPE_RECURSION_LIMIT:
        pass

    is_positional |= no_default
    parser.add_argument(*_name_or_flags_arg(field.name, flag, is_positional), **argument_args)


def _tokenize_fields(container_class: dataclasses.dataclass) -> typing.List[typing.List[tokenize.TokenInfo]]:
    lines = [[]]
    # noinspection PyBroadException
    try:
        source = inspect.getsource(container_class)
        with io.StringIO(source) as f:
            for t in tokenize.generate_tokens(f.readline):
                if t.type == tokenize.NEWLINE:
                    lines.append([])
                else:
                    lines[-1].append(t)
    except Exception:
        pass

    return list(filter(lambda x: len(x) > 0, lines))


def _iter_valid_tok(line):
    for t in line:
        if t.type not in [tokenize.COMMENT, tokenize.NL, tokenize.INDENT]:
            yield t


def _iter_comment_tok(line):
    for t in line:
        if t.type != tokenize.COMMENT:
            continue
        c = t.string
        if c.startswith("#"):
            c = c[1:]
        yield c.strip()


def _get_argument_docs(container_class: dataclasses.dataclass) -> typing.Dict[str, str]:
    lines = _tokenize_fields(container_class)

    docs = {}
    for line in lines:
        iter_tok = _iter_valid_tok(line)
        try:
            name_tok, op_tok = next(iter_tok), next(iter_tok)
        except StopIteration:
            continue
        if name_tok.type != tokenize.NAME or op_tok.type != tokenize.OP or op_tok.string != ":":
            continue

        comment = "\n".join(_iter_comment_tok(line))
        if comment:
            docs[name_tok.string] = comment

    return docs


def make_parser(container_class: dataclasses.dataclass, default_argument_args=None,
                **parser_args) -> argparse.ArgumentParser:
    """ Create parser from a dataclass """
    if not dataclasses.is_dataclass(container_class):
        raise TypeError("Cannot operate on a non-dataclass object.")

    docs = _get_argument_docs(container_class)

    parser_args.setdefault('description', container_class.__doc__)
    parser = argparse.ArgumentParser(**parser_args)

    if default_argument_args is None:
        default_argument_args = {}

    for field in dataclasses.fields(container_class):
        _add_argument_from_field(parser, field, docs, **default_argument_args)

    return parser


def parse_args_to_class(container_class: dataclasses.dataclass,
                        parser: argparse.ArgumentParser, args=None) -> dataclasses.dataclass:
    arg_namespace = parser.parse_args(args=args)
    return container_class(**{k.replace("-", "_"): v for k, v in vars(arg_namespace).items()})


def parse_to(container_class: dataclasses.dataclass, args=None,
             default_argument_args: dict = None, **parser_args) -> dataclasses.dataclass:
    """ Parse arguments to a dataclass """
    parser = make_parser(container_class, default_argument_args=default_argument_args, **parser_args)
    return parse_args_to_class(container_class, parser, args=args)


def as_parser(cls=None, /, **defined_kwargs):
    """ Decorator that adds `parse_args()` method to dataclass, that parse arguments into this dataclass """

    def decorator(container_class) -> typing.Union[argparse.ArgumentParser, dataclasses.dataclass]:
        parser = make_parser(container_class, **defined_kwargs)

        def parse_args(args=None) -> container_class:
            return parse_args_to_class(container_class, parser, args=args)

        setattr(container_class, 'parse_args', parse_args)
        return container_class

    if cls is not None:
        return decorator(cls)
    else:
        return decorator

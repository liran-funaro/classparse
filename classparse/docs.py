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
import inspect
import io
import tokenize
import typing


def _tokenize_fields(
    container_class: dataclasses.dataclass,
) -> typing.List[typing.List[tokenize.TokenInfo]]:
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


def get_argument_docs(container_class: dataclasses.dataclass) -> typing.Dict[str, str]:
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

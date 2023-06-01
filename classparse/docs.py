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
import inspect
import io
import tokenize
import typing


def _tokenize_fields(
    container_class: type,
) -> typing.List[typing.List[tokenize.TokenInfo]]:
    lines: typing.List[typing.List[tokenize.TokenInfo]] = [[]]
    # noinspection PyBroadException
    # pylint: disable=broad-exception-caught
    # Failing to fetch the source code should never block user.
    # So we want to catch any unexpected exception here.
    try:
        source = inspect.getsource(container_class)
        with io.StringIO(source) as source_io:
            for tok in tokenize.generate_tokens(source_io.readline):
                if tok.type == tokenize.NEWLINE:
                    lines.append([])
                else:
                    lines[-1].append(tok)
    except Exception:
        pass

    return list(filter(lambda x: len(x) > 0, lines))


def _iter_valid_tok(line):
    for tok in line:
        if tok.type not in [tokenize.COMMENT, tokenize.NL, tokenize.INDENT]:
            yield tok


def _iter_comment_tok(line):
    for tok in line:
        if tok.type != tokenize.COMMENT:
            continue
        comment = tok.string
        if comment.startswith("#"):
            comment = comment[1:]
        yield comment.strip()


def get_argument_docs(container_class: type) -> typing.Dict[str, str]:
    """Returns the comments of all the fields of the dataclass"""
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

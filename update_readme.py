#!/bin/env python3
import difflib
import os
import subprocess
import re
import sys
from dataclasses import dataclass

from classparse import as_parser, arg

embed_pattern = re.compile((
    r'<!--\s*embed\s*:\s*(?P<file_name>[a-zA-Z0-9/\\._-]+)\s*-->\n'
    r'(?:\s*\n)*'
    r'```[a-z-_]*\n'
    r'(?P<replace_content>(.*\n)*?)'
    r'```\n'
), re.MULTILINE)
init_doc_pattern = re.compile(r'^"""[\s\S]*?"""\n', re.MULTILINE)
multi_break_pattern = re.compile(r'\n{2,}', re.MULTILINE)

execute_pattern = re.compile((
    r'<!--\s*execute\s*:\s*(?P<cmd>.*?)\s*-->\n'
    r'(?:\s*\n)*'
    r'```[a-z-_]*\n'
    r'(?P<replace_content>(.*\n)*?)'
    r'```\n'
), re.MULTILINE)


@as_parser
@dataclass(frozen=True)
class UpdateArgs:
    verify: bool = arg('-v', False)  # Verifies the output matches
    input: str = arg('-i', "README.md")
    output: str = arg('-o', "stdout")


def read_file(file_path: str) -> str:
    with open(file_path, 'r') as f:
        content = f.read()

    m = init_doc_pattern.search(content)
    if m is not None:
        content = content[m.end():]

    return multi_break_pattern.sub("\n\n", content)


def make_readme():
    args = UpdateArgs.parse_args()
    with open(args.input, 'r') as f:
        source_readme_content = f.read()

    readme_content = source_readme_content

    i = 0
    readme_output = []
    for m in embed_pattern.finditer(readme_content):
        file_name = m.group("file_name").strip()
        embed = read_file(file_name)
        embed_start, embed_end = m.span("replace_content")
        readme_output.append(readme_content[i:embed_start])
        readme_output.append(f"# {file_name}\n")
        readme_output.append(embed)
        i = embed_end

    readme_output.append(readme_content[i:])
    readme_content = "".join(readme_output)

    i = 0
    readme_output = []
    for m in execute_pattern.finditer(readme_content):
        cmd = m.group("cmd").strip()
        env = dict(os.environ, PYTHONPATH='.')
        r = subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        embed_start, embed_end = m.span("replace_content")
        readme_output.append(readme_content[i:embed_start])
        readme_output.append(f"$ {cmd}\n")
        readme_output.append(r.stdout)
        i = embed_end

    readme_output.append(readme_content[i:])
    readme_content = "".join(readme_output)

    if args.verify:
        if args.output == 'stdout':
            compare_to = source_readme_content
        else:
            with open(args.output, 'r') as f:
                compare_to = f.read()

        diff = difflib.unified_diff(
            compare_to.splitlines(keepends=True),
            readme_content.splitlines(keepends=True),
            fromfile='source', tofile='generated'
        )
        diff = "".join(diff).strip()
        if diff:
            print(diff, file=sys.stderr)
            exit(1)
    elif args.output == 'stdout':
        print(readme_content)
    else:
        with open(args.output, 'w') as f:
            f.write(readme_content)


if __name__ == '__main__':
    make_readme()

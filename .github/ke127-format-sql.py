"""Verification-branch-only formatting; not included in the product tree."""
import ast
import io
import textwrap
import tokenize
from pathlib import Path

for name in (
    'server/src/ontology_map/db/model_tasks.py',
    'server/tests/test_provider_call_slots_postgres.py',
):
    path = Path(name)
    source = path.read_text()
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    changes = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.STRING or token.string[0].lower() == 'f':
            continue
        value = ast.literal_eval(token.string)
        if not isinstance(value, str):
            continue
        if '\n' in token.string:
            if not any(len(line) > 88 for line in token.string.splitlines()):
                continue
            replacement = '\n'.join(
                '\n'.join(textwrap.wrap(line, width=84, subsequent_indent='            ', break_long_words=False, break_on_hyphens=False, replace_whitespace=False))
                if len(line) > 88 else line
                for line in token.string.split('\n')
            )
            assert ast.literal_eval(replacement).split() == value.split()
        elif len(value) > 65:
            chunks = textwrap.wrap(value, width=60, break_long_words=False, break_on_hyphens=False, drop_whitespace=False, replace_whitespace=False)
            assert ''.join(chunks) == value
            replacement = '(\n' + ''.join('                ' + repr(part) + '\n' for part in chunks) + ')'
            assert ast.literal_eval(replacement) == value
        else:
            continue
        changes.append((offsets[token.start[0]-1]+token.start[1], offsets[token.end[0]-1]+token.end[1], replacement))
    for start, end, replacement in reversed(changes):
        source = source[:start] + replacement + source[end:]
    ast.parse(source)
    path.write_text(source)

#!/usr/bin/env python3
"""Expose compiler errors in annotations when full log downloads are unavailable."""
from collections import deque
from pathlib import Path
import re
import sys

ERROR = re.compile(r'(?:^|\s)(?:error:|fatal error|undefined reference|no such file|'
                   r'no space left|killed\b|Error [0-9]+|FAILED:|cannot find|'
                   r'command not found)|^\s*(?:Patch failed!|Hunk #\d+ FAILED|'
                   r'\d+ out of \d+ hunks? FAILED)', re.I)


def error_summary(lines):
    matches = deque(maxlen=30)
    tail = deque(maxlen=15)
    for line in lines:
        line = line.rstrip()
        tail.append(line[:500])
        if ERROR.search(line):
            matches.append(line[:500])
    return '\n'.join(matches or tail)[-6000:]


def annotation(message):
    escaped = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    return '::error title=Firmware compiler errors::' + escaped


def main():
    log = Path(sys.argv[1])
    if not log.is_file():
        print(annotation('Compiler log is missing; inspect the Compile the firmware step.'))
        return
    with log.open(errors='replace') as lines:
        print(annotation(error_summary(lines) or 'Compiler log is empty.'))


if __name__ == '__main__':
    main()

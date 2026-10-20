#!/usr/bin/env python3
"""Generate act-compatible workflows without downgrading GitHub's Node runtime."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def render(text):
    text = re.sub(r'(uses: actions/upload-artifact@)v6\b', r'\g<1>v5', text)
    return re.sub(r'(uses: actions/download-artifact@)v7\b', r'\g<1>v6', text)


def main():
    destination = ROOT / '.act/workflows'
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('immortalwrt.yml', 'checks.yml'):
        (destination / name).write_text(render((ROOT / '.github/workflows' / name).read_text()))
    print(f'Local act workflows: {destination}')


if __name__ == '__main__':
    main()

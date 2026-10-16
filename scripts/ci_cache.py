#!/usr/bin/env python3
"""Configure OpenWrt caches and cap persisted data after compilation stops."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from build_inputs import fingerprint

MIB = 1024 * 1024


def configure(root, cache):
    config = root / '.config'
    values = {
        'DEVEL': 'y',
        'CCACHE': 'y', 'CCACHE_DIR': json.dumps(str(cache / 'ccache')),
        'GOLANG_BUILD_CACHE_DIR': json.dumps(str(cache / 'go')),
        'RUST_SCCACHE': 'y', 'RUST_SCCACHE_DIR': json.dumps(str(cache / 'sccache')),
    }
    text = config.read_text()
    for name, value in values.items():
        text = re.sub(rf'^(?:CONFIG_{name}=.*|# CONFIG_{name} is not set)\n?', '', text, flags=re.M)
        text += f'CONFIG_{name}={value}\n'
    config.write_text(text)
    for name in ('ccache', 'go', 'sccache'):
        (cache / name).mkdir(parents=True, exist_ok=True)
    (root / 'dl').mkdir(exist_ok=True)


def scope(root, lock):
    # Keep caches across unrelated source updates, but never across compiler recipes.
    trees = subprocess.check_output(['git', '-C', str(root), 'ls-tree', 'HEAD',
                                     'toolchain', 'tools', 'include', 'rules.mk'], text=True)
    host = subprocess.check_output(['gcc', '-dumpfullversion'], text=True).strip()
    rust = root / 'feeds/packages/lang/rust'
    recipes = {str(p.relative_to(rust)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(rust.rglob('*')) if p.is_file() and not p.is_symlink()}
    if not recipes:
        raise ValueError('Rust compiler recipes are missing')
    data = {
        'config': hashlib.sha256((root / '.config').read_bytes()).hexdigest(),
        'trees': trees, 'host_gcc': host,
        'golang': lock['repositories']['golang']['commit'],
        'rust_recipe': recipes,
        'cache_version': 1,
    }
    return fingerprint(data)


def regular_files(directory):
    if directory.is_symlink():
        raise ValueError(f'Refusing symlink cache directory: {directory}')
    return [p for p in directory.rglob('*') if not p.is_symlink() and p.is_file()]


def trim(directory, limit, whole_entries=False):
    files = regular_files(directory)
    total = sum(p.stat().st_size for p in files)
    # Download directories such as go-mod-cache must be evicted as complete units.
    entries = list(directory.iterdir()) if whole_entries else files
    candidates = []
    for entry in entries:
        if entry.is_symlink():
            continue
        members = regular_files(entry) if entry.is_dir() else [entry]
        if members:
            stats = [p.stat() for p in members]
            candidates.append((max(s.st_atime for s in stats), sum(s.st_size for s in stats), entry))
    for _, size, entry in sorted(candidates):
        if total <= limit:
            break
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
        total -= size
    print(f'{directory}: {total / MIB:.1f} MiB retained (limit {limit / MIB:.0f} MiB)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['configure', 'scope', 'trim'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=Path('/workdir/cache'))
    parser.add_argument('--lock', type=Path)
    args = parser.parse_args()
    if args.command == 'configure':
        configure(args.root, args.cache)
    elif args.command == 'scope':
        print(scope(args.root, json.loads(args.lock.read_text())))
    else:
        for name, size in [('ccache', 768), ('go', 256), ('sccache', 128)]:
            trim(args.cache / name, size * MIB)
        trim(args.root / 'dl', 1024 * MIB, whole_entries=True)


if __name__ == '__main__':
    main()

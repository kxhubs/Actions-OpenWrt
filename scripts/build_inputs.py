#!/usr/bin/env python3
"""Resolve and share immutable source inputs across both firmware architectures."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_lock(lock, sources):
    if not isinstance(lock, dict) or lock.get('schema') != 1:
        raise ValueError('Unsupported source lock')
    if set(lock) != {'schema', 'repositories', 'feeds'}:
        raise ValueError('Unexpected source lock fields')
    for group in ('repositories', 'feeds'):
        if not isinstance(lock[group], dict) or set(lock[group]) != set(sources[group]):
            raise ValueError(f'Mismatched {group}')
        for name, spec in sources[group].items():
            actual = lock[group][name]
            if not isinstance(actual, dict) or set(actual) != {'url', 'ref', 'commit'}:
                raise ValueError(f'Invalid entry: {name}')
            if any(actual[k] != spec[k] for k in ('url', 'ref')):
                raise ValueError(f'Unexpected repository/ref: {name}')
            if not re.fullmatch(r'[0-9a-f]{40}', actual['commit']):
                raise ValueError(f'Invalid commit: {name}')
    return lock


def resolve_one(spec):
    if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', spec['url']):
        raise ValueError('Only configured GitHub HTTPS repositories are supported')
    ref = 'HEAD' if spec['ref'] == 'HEAD' else 'refs/heads/' + spec['ref']
    for attempt in range(3):
        try:
            result = subprocess.run(['git', 'ls-remote', '--exit-code', spec['url'], ref],
                                    check=True, capture_output=True, text=True, timeout=60)
            rows = [row.split() for row in result.stdout.splitlines()]
            commits = [sha for sha, remote_ref in rows if remote_ref == ref]
            if len(commits) != 1 or not re.fullmatch('[0-9a-f]{40}', commits[0]):
                raise ValueError(f'Cannot resolve {spec["url"]} {ref}')
            return {**spec, 'commit': commits[0]}
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt == 2:
                raise


def resolve(sources):
    lock = {'schema': 1, 'repositories': {}, 'feeds': {}}
    entries = [(group, name, spec) for group in ('repositories', 'feeds')
               for name, spec in sources[group].items()]
    with ThreadPoolExecutor(max_workers=6) as pool:
        values = pool.map(resolve_one, [entry[2] for entry in entries])
        for (group, name, _), value in zip(entries, values):
            lock[group][name] = value
    return validate_lock(lock, sources)


def checkout(spec, destination):
    # Never reset a pre-existing checkout or overwrite local files.
    destination = Path(destination)
    if destination.exists():
        raise ValueError(f'Checkout already exists: {destination}')
    destination.mkdir(parents=True)
    subprocess.run(['git', 'init', '-q', str(destination)], check=True)
    subprocess.run(['git', '-C', str(destination), 'remote', 'add', 'origin', spec['url']], check=True)
    subprocess.run(['git', '-C', str(destination), 'fetch', '--depth=1', 'origin', spec['commit']], check=True)
    subprocess.run(['git', '-C', str(destination), 'checkout', '--detach', 'FETCH_HEAD'], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, default=ROOT / 'config/build-sources.json')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('resolve')
    p.add_argument('--event', type=Path)
    p.add_argument('--output', type=Path, required=True)
    for command in ('feeds', 'checkout'):
        p = sub.add_parser(command)
        p.add_argument('--lock', type=Path, required=True)
        if command == 'checkout':
            p.add_argument('name', choices=['immortalwrt', 'golang', 'theme'])
            p.add_argument('destination')
    args = parser.parse_args()
    sources = json.loads(args.sources.read_text())
    if args.command == 'resolve':
        event = json.loads(args.event.read_text()) if args.event else {}
        supplied = event.get('client_payload', {}).get('lock')
        lock = validate_lock(supplied, sources) if supplied is not None else resolve(sources)
        args.output.write_text(json.dumps(lock, indent=2) + '\n')
        print(fingerprint(lock))
    else:
        lock = validate_lock(json.loads(args.lock.read_text()), sources)
        if args.command == 'feeds':
            for name, spec in lock['feeds'].items():
                print(f'src-git {name} {spec["url"]}^{spec["commit"]}')
        else:
            checkout(lock['repositories'][args.name], args.destination)


if __name__ == '__main__':
    main()

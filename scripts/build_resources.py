#!/usr/bin/env python3
"""Budget compilation against available RAM/cgroups and record a heartbeat."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import time

GIB = 1024 ** 3


def number(path):
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def memory_info(proc=Path('/proc'), cgroup=Path('/sys/fs/cgroup')):
    fields = {}
    for line in (proc / 'meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        fields[key] = int(value.split()[0]) * 1024
    available = fields['MemAvailable']
    for limit_path, used_path in [('memory.max', 'memory.current'),
                                  ('memory/memory.limit_in_bytes', 'memory/memory.usage_in_bytes')]:
        limit = number(cgroup / limit_path)
        used = number(cgroup / used_path)
        if limit is not None and used is not None:
            available = min(available, max(0, limit - used))
    return {'available': available, 'swap_free': fields.get('SwapFree', 0)}


def cpu_count(cgroup=Path('/sys/fs/cgroup')):
    count = len(os.sched_getaffinity(0))
    try:
        quota, period = (cgroup / 'cpu.max').read_text().split()
        if quota != 'max':
            count = min(count, max(1, int(quota) // int(period)))
    except (OSError, ValueError):
        quota = number(cgroup / 'cpu/cpu.cfs_quota_us')
        period = number(cgroup / 'cpu/cpu.cfs_period_us')
        if quota is not None and quota > 0 and period:
            count = min(count, max(1, quota // period))
    return max(1, count)


def build_jobs(cpus, available):
    # Leave 3 GiB for the Actions runner, OS, caches and linker peaks.
    return max(1, min(cpus, (available - 3 * GIB) // (3 * GIB)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['jobs', 'monitor'])
    parser.add_argument('--directory', type=Path, default=Path('/workdir'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'jobs':
        info = memory_info()
        cpus = cpu_count()
        jobs = build_jobs(cpus, info['available'])
        print(f'BUILD_JOBS={jobs}\nDOWNLOAD_JOBS={min(cpus, 8)}')
        print(f'GOMAXPROCS={jobs}\nCARGO_BUILD_JOBS={jobs}')
    else:
        while True:
            sample = {'time': datetime.now(timezone.utc).isoformat(), **memory_info(),
                      'disk_free': shutil.disk_usage(args.directory).free,
                      'load': os.getloadavg()}
            events = Path('/sys/fs/cgroup/memory.events')
            if events.exists():
                sample['memory_events'] = events.read_text().strip()
            line = json.dumps(sample)
            if args.output:
                with args.output.open('a') as output:
                    output.write(line + '\n')
            print('Build resources: ' + line, flush=True)
            time.sleep(60)


if __name__ == '__main__':
    main()

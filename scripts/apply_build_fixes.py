#!/usr/bin/env python3
"""Apply narrowly scoped compatibility fixes before feed packages are installed."""
import argparse
import hashlib
from pathlib import Path
import re

ROCKCHIP_PATCH_DIR = 'target/linux/rockchip/patches-6.12'
ROCKCHIP_PATCHES = {
    '041-30-v6.15-drm-rockchip-vop2-Consistently-use-dev_err_probe.patch':
        'af8cccc1e0eea0b8977cf8a0deed041d3f0396eaf6a9f5d317d3abcac0974f86',
    '041-38-v6.15-drm-rockchip-vop2-Register-the-primary-plane-and-overlay.patch':
        '5a149ddd384e412b4250186bdb38a8a3a5e1f726c574920424b171601d17b7c8',
}


def fix_rockchip(root):
    version = root / 'target/linux/generic/kernel-6.12'
    if not version.is_file():
        return
    if not re.search(r'^LINUX_VERSION-6\.12\s*=\s*\.116\s*$',
                     version.read_text(), re.M):
        return
    # Linux 6.12.116 already contains both changes. Verify every duplicate
    # before removing any, so an upstream edit is left intact for review.
    duplicates = []
    for name, digest in ROCKCHIP_PATCHES.items():
        patch = root / ROCKCHIP_PATCH_DIR / name
        if not patch.is_file():
            continue
        if hashlib.sha256(patch.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Rockchip patch changed; review the 6.12.116 fix: {patch}')
        duplicates.append(patch)
    for patch in duplicates:
        patch.unlink()
        print(f'Linux 6.12.116: removed duplicate Rockchip backport {patch.name}')


def fix_smartdns(root):
    recipe = root / 'feeds/kenzo/smartdns/Makefile'
    if not recipe.is_file():
        return
    text = recipe.read_text()
    version = 'PKG_VERSION:=48.5-RC1\n'
    if version not in text:
        return
    # Preserve the archive, URL, extracted directory and compiled version string.
    # Only the package version changes to APK's release-candidate syntax.
    if text.count('$(PKG_VERSION)') != 4:
        raise ValueError(f'SmartDNS recipe changed; review its version references: {recipe}')
    text = text.replace('$(PKG_VERSION)', '$(PKG_UPSTREAM_VERSION)')
    text = text.replace(version, 'PKG_UPSTREAM_VERSION:=48.5-RC1\nPKG_VERSION:=48.5_rc1\n')
    recipe.write_text(text)
    print('SmartDNS: normalized APK version to 48.5_rc1, preserving Release48.5-RC1 sources')


def fix_rust(root):
    recipe = root / 'feeds/packages/lang/rust/Makefile'
    if not recipe.is_file():
        return
    text = recipe.read_text()
    if not re.search(r'^PKG_VERSION:=1\.96\.0$', text, re.M):
        return
    option = '--set=llvm.download-ci-llvm=true'
    if option not in text:
        return
    if text.count(option) != 1:
        raise ValueError(f'Rust LLVM configuration changed; review the recipe: {recipe}')
    # Rust CI artifacts expire. Build the LLVM sources from the checksummed
    # Rust release, with only the backends used by this repository and its hosts.
    replacement = ' \\\n\t'.join([
        '--set=llvm.download-ci-llvm=false',
        '--set=llvm.targets="AArch64;X86"',
        '--set=llvm.experimental-targets=',
        '--set=llvm.link-jobs=1',
        '--set=build.jobs=$(if $(BUILD_JOBS),$(BUILD_JOBS),2)',
    ])
    recipe.write_text(text.replace(option, replacement))
    print('Rust 1.96.0: build LLVM from release sources instead of expired CI artifacts')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    fix_rockchip(args.root)
    fix_smartdns(args.root)
    fix_rust(args.root)


if __name__ == '__main__':
    main()

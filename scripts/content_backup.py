#!/usr/bin/env python3
"""Create, verify, and restore-test private clinic content snapshots."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import uuid


def inspect_archive(path):
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive paths')
        for member in members:
            name = PurePosixPath(member.name)
            if not member.isfile() or name.is_absolute() or '..' in name.parts:
                raise ValueError('Unsafe archive member')
        inventory = json.load(archive.extractfile('backup-inventory.json'))
        if set(names) != set(inventory) | {'backup-inventory.json'}:
            raise ValueError('Inventory does not match archive')
        for name, expected in inventory.items():
            actual = hashlib.sha256(archive.extractfile(name).read()).hexdigest()
            if actual != expected:
                raise ValueError('Checksum mismatch')
            if name.endswith('.json'):
                json.load(archive.extractfile(name))
    return inventory


def create_snapshot(data, output):
    data, output = data.resolve(), output.resolve()
    if output == data or data in output.parents:
        raise ValueError('Backup output must be outside the content directory')
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = output / ('content-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex[:8] + '.tar.gz')
    inventory = {}
    with ExitStack() as stack:
        for name in ('manifest', 'articles'):
            handle = stack.enter_context((data / (name + '.lock')).open('a'))
            fcntl.flock(handle, fcntl.LOCK_EX)
        with target.open('xb') as handle:
            os.chmod(target, 0o600)
            with tarfile.open(fileobj=handle, mode='w:gz') as archive:
                paths = [data / name for name in ('manifest.json', 'articles.json')]
                for folder in ('optimized', 'deleted-images'):
                    if (data / folder).exists():
                        paths.extend(sorted((data / folder).rglob('*')))
                for path in paths:
                    if path.is_symlink():
                        raise ValueError('Symlink in content store')
                    if not path.is_file():
                        continue
                    content = path.read_bytes()
                    if path.suffix == '.json':
                        json.loads(content)
                    name = path.relative_to(data).as_posix()
                    inventory[name] = hashlib.sha256(content).hexdigest()
                    info = tarfile.TarInfo(name)
                    info.size = len(content)
                    info.mode = 0o600
                    archive.addfile(info, io.BytesIO(content))
                content = json.dumps(inventory, sort_keys=True).encode()
                info = tarfile.TarInfo('backup-inventory.json')
                info.size = len(content)
                info.mode = 0o600
                archive.addfile(info, io.BytesIO(content))
            handle.flush()
            os.fsync(handle.fileno())
    inspect_archive(target)
    return target


def restore_test(archive_path, destination):
    inventory = inspect_archive(archive_path)
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    with tarfile.open(archive_path, 'r:gz') as archive:
        for name in inventory:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open('xb') as handle:
                os.chmod(target, 0o600)
                handle.write(archive.extractfile(name).read())
            if hashlib.sha256(target.read_bytes()).hexdigest() != inventory[name]:
                raise ValueError('Restore verification failed')
    return len(inventory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create', 'verify', 'restore-test'])
    parser.add_argument('--data-dir', type=Path, default=Path('/var/lib/zahnarzt'))
    parser.add_argument('--output-dir', type=Path, default=Path('/var/backups/zahnarzt'))
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.action == 'create':
        print(create_snapshot(args.data_dir, args.output_dir))
    elif args.action == 'verify':
        print('Verified files:', len(inspect_archive(args.archive)))
    else:
        print('Restored and verified files:', restore_test(args.archive, args.destination))


if __name__ == '__main__':
    main()

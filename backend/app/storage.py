"""Private, durable JSON storage with serialized, atomic updates."""
import fcntl
import json
import logging
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

DATA_DIR = Path(os.getenv("ZAHNARZT_DATA_DIR", "/var/lib/zahnarzt"))
OPTIMIZED_DIR = DATA_DIR / "optimized"
MANIFEST_PATH = DATA_DIR / "manifest.json"
ARTICLES_PATH = DATA_DIR / "articles.json"
logger = logging.getLogger(__name__)


class StorageError(RuntimeError):
    pass


def initialize():
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o750)
    OPTIMIZED_DIR.mkdir(exist_ok=True, mode=0o750)
    (DATA_DIR / "backups").mkdir(exist_ok=True, mode=0o700)


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (ValueError, OSError) as exc:
        logger.error("Cannot read content store %s (%s)", path.name, type(exc).__name__)
        raise StorageError("Content storage is unavailable") from exc


@contextmanager
def locked(name):
    # Lock the entire read/modify/write operation, across threads and processes.
    with (DATA_DIR / (name + ".lock")).open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def serialized(name):
    def decorate(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            with locked(name):
                return func(*args, **kwargs)
        return wrapped
    return decorate


def write_json(path, data):
    """Call while holding the corresponding store lock; retain prior versions."""
    encoded = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    if path.exists():
        # Refuse to replace an unreadable store with an apparently empty one.
        read_json(path, None)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = DATA_DIR / "backups" / f"{path.stem}-{stamp}-{uuid.uuid4().hex}.json"
        with path.open("rb") as source, backup.open("xb") as target:
            os.chmod(backup, 0o600)
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as target:
            target.write(encoded)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

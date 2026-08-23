"""Platform-standard paths and secure atomic writes."""

import os
import tempfile
from pathlib import Path

from platformdirs import user_config_path

CONFIG_DIR = Path(user_config_path("svenskalag-cli", appauthor=False))
CONFIG_FILE = CONFIG_DIR / "config.env"
SESSION_FILE = CONFIG_DIR / "session.json"
STATE_FILE = CONFIG_DIR / "state.json"


def atomic_write_text(path, content):
    """Write text atomically and enforce private file permissions."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise

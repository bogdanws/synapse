"""taskiq broker and task module.

Importing this package has two side effects:

1. The broker singleton (`broker`) is constructed.
2. Task modules are imported so their `@broker.task` decorators register.

Both the API process and the worker process import this package; the worker
CLI then dispatches messages to the registered tasks. The worker entry point
referenced from docker-compose is `app.tasks:broker`.
"""

from __future__ import annotations

# Import task modules so their @broker.task decorators run at module import. The worker also discovers them via --fs-discover, but explicit import keeps the API process registry consistent regardless of CWD.
from app.tasks import research as _research  # noqa: F401
from app.tasks.broker import broker

__all__ = ["broker"]

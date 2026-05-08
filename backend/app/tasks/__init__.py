"""taskiq broker and task module.

Importing this package has two side effects:

1. The broker singleton (`broker`) is constructed.
2. Task modules are imported so their `@broker.task` decorators register.

Both the API process and the worker process import this package; the worker
CLI then dispatches messages to the registered tasks. The worker entry point
referenced from docker-compose is `app.tasks:broker`.
"""

from __future__ import annotations

# Import task modules here so their @broker.task decorators register on every importer (the API process when it enqueues, the worker when it loads `app.tasks:broker`).
# Avoids relying on taskiq's `--fs-discover`, which walks the working tree and chokes on the project venv when it gets bind-mounted in.
from app.tasks import research as _research  # noqa: F401
from app.tasks.broker import broker

__all__ = ["broker"]

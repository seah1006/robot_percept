"""Explicit ABI workaround for pure-Python torchvision transforms/models only."""
from contextlib import contextmanager
import os
import warnings


@contextmanager
def torchvision_import():
    if os.environ.get("M2A_TORCHVISION_PYTHON_ONLY") != "1":
        yield
        return
    import torch
    original = torch.library.register_fake

    def register(op, *args, **kwargs):
        if op == "torchvision::nms":
            # No fake schema, fake result, or NMS kernel is installed; use of NMS still errors.
            warnings.warn("Skipping unavailable torchvision::nms fake registration; no NMS is used", stacklevel=2)
            return lambda fn: fn
        return original(op, *args, **kwargs)

    torch.library.register_fake = register
    try:
        import torchvision  # noqa: F401
    finally:
        torch.library.register_fake = original
    yield
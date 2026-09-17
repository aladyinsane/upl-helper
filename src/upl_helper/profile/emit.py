"""Serializing a descriptor.

Keys are sorted so that two descriptors of different template versions diff
cleanly. A CMS revision should read as a short diff, not a reshuffle.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import yaml

from upl_helper.profile.models import WorkbookDescriptor


def descriptor_to_dict(descriptor: WorkbookDescriptor) -> dict[str, Any]:
    return dataclasses.asdict(descriptor)


def render(descriptor: WorkbookDescriptor, fmt: str = "yaml") -> str:
    payload = descriptor_to_dict(descriptor)
    if fmt == "json":
        return json.dumps(payload, sort_keys=True, indent=2, default=str) + "\n"
    if fmt == "yaml":
        return yaml.safe_dump(
            payload, sort_keys=True, default_flow_style=False, allow_unicode=True
        )
    raise ValueError(f"unknown format {fmt!r}")


def write_descriptor(
    descriptor: WorkbookDescriptor, path: str | Path, fmt: str = "yaml"
) -> Path:
    path = Path(path)
    path.write_text(render(descriptor, fmt), encoding="utf-8")
    return path

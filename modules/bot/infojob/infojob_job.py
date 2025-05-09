from dataclasses import dataclass
from typing import Any

from modules.core import Job


@dataclass
class InfoJobJob(Job):
    type: str = None
    salary: str = None
    details: dict[str, Any] = None

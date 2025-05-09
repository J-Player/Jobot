from dataclasses import dataclass
from typing import Any

from modules.core import Job


@dataclass
class LinkedinJob(Job):
    easy_application: bool = None
    details: dict[str, Any] = None

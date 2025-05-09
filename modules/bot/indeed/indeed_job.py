from dataclasses import dataclass

from modules.core import Job


@dataclass
class IndeedJob(Job):
    benefits: str = None
    easy_application: bool = None
    details: dict[str, str] = None

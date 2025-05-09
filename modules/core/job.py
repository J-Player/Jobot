from dataclasses import dataclass
from datetime import datetime


@dataclass
class Job:
    id: str
    url: str = None
    title: str = None
    description: str = None
    location: str = None
    company: str = None
    posted_at: datetime = None

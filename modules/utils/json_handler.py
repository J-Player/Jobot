import json
from dataclasses import asdict, is_dataclass


def save_json(filepath: str, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, default=default_serializer, indent=4, ensure_ascii=False)


def load_json(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def default_serializer(obj):
    if is_dataclass(obj):
        return asdict(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

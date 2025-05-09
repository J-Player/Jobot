import re
import unicodedata


def normalize_string(text: str):
    # Normalize the string to remove inconsistencies in character representation
    normalized_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    return normalized_text


def camel_case_split(str):
    return re.findall(r"[A-Z](?:[a-z]+|[A-Z]*(?=[A-Z]|$))", str)

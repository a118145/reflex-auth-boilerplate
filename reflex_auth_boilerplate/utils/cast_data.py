from typing import Callable, Any
from datetime import datetime

def to_string(val: str) -> str:
    return str(val)


def to_int(val: str) -> int:
    if val == "":
        val = "0"
    return int(val)


def to_datetime(val: str) -> datetime:
    if len(val.split(":")) == 2:
        val = val + ":00"
    return datetime.strptime(val, "%Y-%m-%d %H:%M:%S")


def datetime_to_parts(val: datetime) -> tuple[str, str]:
    """Returns (date, time) as strings."""
    return (
        f"{val.year}-{val.month:02}-{val.day:02}",
        f"{val.hour:02}:{val.minute:02}:{val.second:02}",
    )


def cast_form_data(form_data: dict[str, Any], type_map: dict[str, Callable]) -> dict[str, Any]:
    """
    Converts form strings to typed values.
    type_map: {"fieldname": cast_function, ...}
    Fields not in type_map are left unchanged.
    """
    return {k: type_map[k](v) if k in type_map else v for k, v in form_data.items()}
"""Explicit process runtime modes shared by service entrypoints."""

from enum import StrEnum


class RuntimeMode(StrEnum):
    PRODUCTION = "production"
    DEMO = "demo"
    TEST = "test"

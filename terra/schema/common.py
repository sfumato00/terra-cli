from enum import StrEnum


class Action(StrEnum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    NO_OP = "no-op"


class Mode(StrEnum):
    MANAGED = "managed"
    DATA = "data"

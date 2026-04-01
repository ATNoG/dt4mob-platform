from enum import Enum

class Action(str, Enum):
    MODIFIED = "modified"
    CREATE = "created"
    DELETE = "deleted"
    MERGED = "merged"

from enum import Enum

class SignalDirection(Enum):
    RISE = "RISE"
    FALL = "FALL"
    INDEFINIDO = "INDEFINIDO"

    def __str__(self):
        return self.value

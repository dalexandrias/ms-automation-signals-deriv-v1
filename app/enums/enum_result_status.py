from enum import Enum

class ResultStatusEnum(Enum):
    WIN = 'WIN'
    LOSS = 'LOSS'

    def __str__(self):
        return self.value
from enum import Enum

class GaleEnum(Enum):
    G1 = 'G1'
    G2 = 'G2'
    G3 = 'G3'

    def __str__(self):
        return self.value
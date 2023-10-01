from enum import Enum


class Faces(Enum):
    FRONT = [0, 0, 1]
    BACK = [0, 0, -1]
    UP = [0, 1, 0]
    DOWN = [0, -1, 0]
    LEFT = [-1, 0, 0]
    RIGHT = [1, 0, 0]


pieces = {
    # TODO: decide on how to store pieces
}

tetris_default = {
    "board": [
        [0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0] 
    ],
    "game_over": False,
    "current_piece": {
        "type": None,
        "rotation": 0,
        "position": {
            "x": 0,
            "y": 0
        }
    },
    "hold_piece": None,
    "next_piece": None,
    "score": 0,
    "level": 1,
    "lines_cleared": 0,
    "inputs": {
        "left": False,
        "right": False,
        "rotate": False,
        "down": False,
        "drop": False,
        "hold": False
    }
}

class Tetris():
    def __init__(self):
        pass #TODO: make tetris
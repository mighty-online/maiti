import console_game
import tempest
import numpy as np


def ismcts_agent(iterations):
    def agent(perspective):
        return tempest.ismcts(perspective, itermax=iterations, verbose=False)

    return agent


dumb_player = console_game.random_random_player
weak_player = ismcts_agent(10)
strong_player = ismcts_agent(50)
stronger_player = ismcts_agent(100)
bighead = ismcts_agent(200)

ai_players = [weak_player] * 4 + [strong_player]

total = np.zeros(5)
for i in range(100):
    print(f"{i=}")
    wins, gamepoints = console_game.play_game(ai_player_functions=ai_players, verbose=1)
    total += np.array(wins)
    print(total)

total /= 100
print(total)


"""The AI worker module of Tranquil Tempest, the Mighty AI

This module contains the ISMCTS-based AI algorithm for the game of Mighty.
This module has been written in mind of being called from tranquil.py, the front-end of Tranquil Tempest.

Development started 2019/06/15
"""

from game_logic import game
from random import shuffle

__author__ = "Jake Hyun (SyphonArch)"
__copyright__ = "Copyright 2019, The Mighty-Online Team"
__credits__ = ["Jake Hyun (SyphonArch)"]
__license__ = "MIT"
__version__ = "0.1.0"
__maintainer__ = "Jake Hyun (SyphonArch)"
__email__ = "jake.hyun@hotmail.com"
__status__ = "Development"


class GameState:
    """The class for a state of the Mighty game, in its 'play' stage.

    This class is not meant to cover the early stages of the game before the tricks."""

    # If 'point_cards' is left as None, it will automatically be constructed.
    # If 'inferences' is left as None, it will automatically be constructed.
    def __init__(self, hands, tricks, previous_suit_leds, suit_led, setup, kitty, point_cards=None, inferences=None):
        self.hands = hands
        self.tricks = tricks
        self.previous_suit_leds = previous_suit_leds
        self.suit_led = suit_led

        self.setup = setup
        self.declarer, self.trump, self.bid, self.friend_card, self.friend = self.setup  # unpacking setup

        self.kitty = kitty

        # Constructing 'point_cards' from the information given
        if point_cards is None:
            point_cards = [[] for _ in range(5)]
            for trick_number in range(len(self.tricks)):
                trick = self.tricks[trick_number]
                if len(trick) == 5:  # i.e. a completed trick
                    trick_winner = game.trick_winner(trick_number, trick, self.trump)
                    point_cards = [c for c in [play[1] for play in trick] if game.is_pointcard(c)]
                    point_cards[trick_winner] += point_cards

        self.point_cards = point_cards

        # TODO: construct inferences from info, and assign

        self.inferences = inferences

        raise NotImplementedError


# This should be all the inferences for all the players grouped adequately
class Inferences:
    """Contains the inferences for all 5 players for a given perspective."""

    def __init__(self, perspective: game.Perspective):
        self.perspective = perspective
        self.inferences = [[Inference(p, True, CardSet()), Inference(p, False, CardSet())] for p in range(5)]

        self.inferences[self.perspective.player][0] += Inference(self.perspective.player, True,
                                                                 CardSet(', '.join(self.perspective.hand)))

        # The loop below creates inferences from the previous gameplay
        for trick_num in range(len(perspective.tricks)):
            trick = perspective.tricks[trick_num]

            # The block below adequately finds the suit_led for the trick
            if trick_num < len(perspective.previous_suit_leds):
                suit_led = perspective.previous_suit_leds[trick_num]
            else:
                suit_led = perspective.suit_led

            for play in trick:
                player, card = play
                if card[0] in game.suits and card[0] != suit_led:
                    self.inferences[player][1] += Inference(player, False, CardSet(suit_led))

    def __repr__(self):
        r_str = []
        for player_infs in self.inferences:
            for inf in player_infs:
                r_str.append(repr(inf))
        return '\n'.join(r_str)


class Inference:
    def __init__(self, player, has: bool, cardset):
        self.player = player
        self.has = has
        self.cardset = cardset

    def __add__(self, other):
        assert self.player == other.player  # Can only add Inferences if the 'player' attributes are equal.
        assert self.has == other.has  # Can only add Inferences if the 'has' attributes are equal.

        return Inference(self.player, self.has, self.cardset + other.cardset)

    def __iadd__(self, other):
        assert self.player == other.player  # Can only add Inferences if the 'player' attributes are equal.
        assert self.has == other.has  # Can only add Inferences if the 'has' attributes are equal.
        self.cardset = self.cardset + other.cardset
        return self

    def __repr__(self):
        return "Inference: Player {} {} {}".format(self.player, "has" if self.has else "doesn't have",
                                                   self.cardset.cards)


class CardSet:
    """A class to represent a set of cards."""

    def __init__(self, info_string=None):
        self.cards = set()

        if info_string is not None:
            # If a single card is specified
            if info_string in game.cards:
                self.cards.add(info_string)
            # If a suit is specified
            elif info_string in game.suits:
                self.cards = set([c for c in game.cards if c[0] == info_string])
            # If a rank is specified
            elif info_string in game.ranks:
                self.cards = set([c for c in game.cards if c[1] == info_string])
            else:
                cards = info_string.split(', ')  # Mind the whitespace
                cards = set(cards)
                assert all(c in game.cards for c in cards)
                self.cards = cards

    def includes(self, card):
        """Returns whether card is in CardSet"""
        return card in self.cards

    def __add__(self, other):
        new_set = CardSet()
        new_set.cards = self.cards.union(other.cards)
        return new_set

    def __repr__(self):
        return 'CardSet object: {' + ', '.join(self.cards) + '}'


def determinize(perspective: game.Perspective, biased=False) -> GameState:
    """Determinize the given perspective into a deterministic state.

    If the 'biased' argument is set to False, determinization will be completely random.
    Else, if the 'biased' argument is set to True, determinization will be biased adequately.
    """
    if biased:
        raise NotImplementedError
    else:
        # TODO: implement determinization, and return GameState
        raise NotImplementedError


def copy_list(original: list) -> list:
    """Recursively copies n-dimensional list and returns the copy.

    Slower than list slicing, faster than copy.deepcopy.
    """
    copied = []
    for x in original:
        if not isinstance(x, list):
            copied.append(x)
        else:
            copied.append(copy_list(x))
    return copied

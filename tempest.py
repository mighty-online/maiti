"""The AI worker module of Tranquil Tempest, the Mighty AI

This module contains the ISMCTS-based AI algorithm for the game of Mighty.
This module has been written in mind of being called from tranquil.py, the front-end of Tranquil Tempest.

Development started 2019/06/15
"""

from game_logic import engine, cards, constructs
from math import sqrt, log


class GameState(engine.GameEngine):
    """The class for a state of the Mighty game, in its 'play' stage.

    This class is not meant to cover the early stages of the game before the tricks."""

    def __init__(self, hands, kitty, point_cards, completed_tricks, trick_winners, current_trick, previous_suit_leds,
                 suit_led, setup: constructs.Setup):
        super().__init__()

        self.hands = hands
        self.kitty = kitty
        self.point_cards = point_cards

        # Play related variables
        self.completed_tricks = completed_tricks
        self.trick_winners = trick_winners
        self.current_trick = current_trick
        self.previous_suit_leds = previous_suit_leds
        self.suit_led = suit_led

        # Unpacking setup
        self.declarer = setup.declarer
        self.trump = setup.trump
        self.bid = setup.bid
        self.friend = setup.friend
        self.friend_card = setup.friend_card

        # Mighty and Ripper cards
        self.mighty = constructs.trump_to_mighty(self.trump)
        self.ripper = constructs.trump_to_ripper(self.trump)

        if len(self.completed_tricks) < 10:
            self.next_call = engine.CallType('play')
        else:
            self.next_call = engine.CallType('game over')

        if len(self.completed_tricks) == 0:
            self.leader = self.declarer
        else:
            self.leader = self.trick_winners[-1]

    def next_player(self):
        if len(self.current_trick) == 0:
            return self.leader
        else:
            return constructs.next_player(self.current_trick[-1].player)

    def legal_plays(self):
        return constructs.legal_plays(self.perspective(self.next_player()))


# This should be all the inferences for all the players grouped adequately
class Inferences:
    """Contains the inferences for all 5 players for a given perspective."""

    def __init__(self, perspective: game.Perspective):
        self.perspective = perspective
        self.inferences = [[Inference(p, True, CardSet()), Inference(p, False, CardSet())] for p in range(5)]

        self.inferences[self.perspective.player][0] += Inference(self.perspective.player, True,
                                                                 CardSet(', '.join(map(str, self.perspective.hand))))
        self.inferences[self.perspective.player][1] += Inference(self.perspective.player, False,
                                                                 CardSet(', '.join(map(str, self.perspective.hand)),
                                                                         complement=True))

        # The loop below creates inferences from the previous gameplay
        tricks = perspective.completed_tricks + [perspective.current_trick]
        for trick_num in range(len(tricks)):
            trick = tricks[trick_num]

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

    def __init__(self, info_string=None, complement=False):
        self.cards = set()

        if info_string is not None and info_string != '':
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
                try:
                    assert all(c in game.cards for c in cards)
                except AssertionError:
                    raise AssertionError("Invalid card in {}".format(cards))

                self.cards = cards

        # If complement, complements the set.
        if complement:
            comp_set = set()
            for card in game.cards:
                if card not in self.cards:
                    comp_set.add(card)
            self.cards = comp_set

    def includes(self, card):
        """Returns whether card is in CardSet"""
        return card in self.cards

    def __add__(self, other):
        new_set = CardSet()
        new_set.cards = self.cards.union(other.cards)
        return new_set

    def __repr__(self):
        return 'CardSet object: {' + ', '.join(self.cards) + '}'


class InfoSet:
    """The Information Set class, used as the nodes in the ISMCTS game tree."""

    def __init__(self, parent=None, player=None, move=None):
        self.parent = parent
        self.player = player
        self.move = move
        self.children = []
        self._move_to_children = {}  # dictionary to map moves to children

        self.reward_sum = 0
        self.visits = 0
        self.avails = 1

        self._tried_moves = set()

    def untried_moves(self, legal_moves):
        """Returns the elements of legal_moves for which this node has no children."""
        return [move for move in legal_moves if move not in self._tried_moves]

    def ucb_child_select(self, legal_moves, exploration=0.7):
        """Uses the UCB1 formula to select a child node, filtered by the legal_moves."""
        legal_children = [self._move_to_children[move] for move in legal_moves]

        # Select child with highest UCB score
        selected = max(legal_children,
                       key=lambda c: c.reward_sum / c.visits + exploration * sqrt(log(c.avails) / c.visits))

        # Update availability counts
        for child in legal_children:
            child.avails += 1

        return selected

    def add_child(self, player: int, move: str):
        """Add child to node and return child."""
        child = InfoSet(self, player, move)

        self.children.append(child)
        self._move_to_children[move] = child
        self._tried_moves.add(move)

        return child

    def update(self, rewards: list):
        """Update this node's reward_sum and visit count based on the rewards of a rollout."""
        self.visits += 1
        if self.player is not None:
            self.reward_sum += rewards[self.player]

    def __repr__(self):
        return "[Move:{} R/V/A: {}/{}/{}]".format(self.move, self.reward_sum, self.visits, self.avails)

    def _tree_info(self):
        """Data for tree_info."""
        depths = [[]]
        depths[0].append(len(self.children))
        for child in self.children:
            child_d = child._tree_info()
            for i in range(len(child_d)):
                while i + 1 >= len(depths):
                    depths.append([])
                depths[i + 1] += child_d[i]
        return depths

    def tree_info(self):
        """Visualize the tree structure and size."""
        visual_str = []
        depths = self._tree_info()
        for depth in depths:
            visual_str.append(' '.join([str(x) for x in depth]))

        print('\n'.join(visual_str))


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


def ismcts(perspective: game.Perspective, itermax: int, verbose=False, biased=False):
    """Performs an ISMCTS search from the given perspective and returns the best move after itermax iterations."""

    root_node = InfoSet()
    for i in range(itermax):
        node_head = root_node

        # Determinization
        determinized_state = determinize(perspective, biased)

        # Selection
        # while determinized_state.legal_moves()

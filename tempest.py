"""The AI worker module of Tranquil Tempest, the Mighty AI

This module contains the ISMCTS-based AI algorithm for the game of Mighty.
This module has been written in mind of being called from tranquil.py, the front-end of Tranquil Tempest.

Development started 2019/06/15
"""

from game_logic import engine
from game_logic import constructs as cs
from game_logic.cards import Card, Suit, Rank
from math import sqrt, log


class GameState(engine.GameEngine):
    """The class for a state of the Mighty game, in its 'play' stage.

    This class is not meant to cover the early stages of the game before the tricks."""

    def __init__(self, hands, kitty, point_cards, completed_tricks, trick_winners, current_trick, previous_suit_leds,
                 suit_led, setup: cs.Setup):
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
        self.friend_call = setup.friend_call

        # Mighty and Ripper cards
        self.mighty = setup.mighty
        self.ripper = setup.ripper

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
            return cs.next_player(self.current_trick[-1].player)

    def legal_plays(self):
        return cs.legal_plays(self.perspective(self.next_player()))


# This should be all the inferences for all the players grouped adequately
class Inferences:
    """Contains the inferences for all 5 players for a given perspective."""

    def __init__(self, perspective: cs.Perspective):
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
                player, card = play.player, play.card
                if not card.suit.is_nosuit() and card != perspective.setup.mighty and card.suit != suit_led:
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
        self.cards_set = set()
        if info_string is not None and info_string != '':
            # If a single card is specified
            if Card.is_cardstr(info_string):
                self.cards_set.add(Card.str_to_card(info_string))
            # If a suit is specified
            elif Suit.is_suitstr(info_string):
                self.cards_set = set(Card.suit_iter(Suit.str_to_suit(info_string)))
            # If a rank is specified
            elif Rank.is_rankstr(info_string):
                self.cards_set = set(Card.rank_iter(Rank.str_to_rank(info_string)))
            else:
                card_strings = info_string.split(', ')  # Mind the whitespace
                self.cards_set = set([Card.str_to_card(card_string) for card_string in card_strings])

        # If complement, complements the set.
        if complement:
            comp_set = set()
            for card in Card.iter():
                if card not in self.cards_set:
                    comp_set.add(card)
            self.cards_set = comp_set

    def includes(self, card):
        """Returns whether card is in CardSet"""
        return card in self.cards_set

    def __add__(self, other):
        new_set = CardSet()
        new_set.cards_set = self.cards_set.union(other.cards)
        return new_set

    def __repr__(self):
        return 'CardSet object: {' + ', '.join(self.cards_set) + '}'


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

    def raw_tree_info(self):
        """Data for tree_info.

        For public use outside of class, use tree_info instead.
        """
        depths = [[]]
        depths[0].append(len(self.children))
        for child in self.children:
            child_d = child.raw_tree_info()
            for i in range(len(child_d)):
                while i + 1 >= len(depths):
                    depths.append([])
                depths[i + 1] += child_d[i]
        return depths

    def tree_info(self):
        """Visualize the tree structure and size."""
        visual_str = []
        depths = self.raw_tree_info()
        for depth in depths:
            visual_str.append(' '.join([str(x) for x in depth]))

        print('\n'.join(visual_str))


def determinize(perspective: cs.Perspective, biased=False) -> GameState:
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


def ismcts(perspective: cs.Perspective, itermax: int, verbose=False, biased=False):
    """Performs an ISMCTS search from the given perspective and returns the best move after itermax iterations."""

    root_node = InfoSet()
    for i in range(itermax):
        node_head = root_node

        # Determinization
        determinized_state = determinize(perspective, biased)

        # Selection
        # while determinized_state.legal_moves()

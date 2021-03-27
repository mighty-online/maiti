"""The AI worker module of Tranquil Tempest, the Mighty AI

This module contains the ISMCTS-based AI algorithm for the game of Mighty.
This module has been written in mind of being called from tranquil.py, the front-end of Tranquil Tempest.

Development started 2019/06/15
"""
from typing import List

from game_logic import engine
from game_logic import constructs as cs
from game_logic.cards import Card, Suit, Rank
from math import sqrt, log
from copy import deepcopy
import random
from functools import reduce
import sys


# TODO: Make use of inferences
# TODO: Make inference from friend call
# TODO: implement statistics based bidder/exchanger


class GameState(engine.GameEngine):
    """The class for a state of the Mighty game, in its 'play' stage.

    This class is not meant to cover the early stages of the game before the tricks."""

    def __init__(self, hands, kitty, point_cards, completed_tricks, trick_winners, current_trick,
                 declarer, trump, bid, friend, called_friend, friend_just_revealed):
        super().__init__()

        self.hands = hands
        self.kitty = kitty
        self.point_cards = point_cards

        # Play related variables
        self.completed_tricks = completed_tricks
        self.trick_winners = trick_winners
        self.current_trick = current_trick

        self.declarer = declarer
        self.trump = trump
        self.bid = bid
        self.friend = friend
        self.called_friend = called_friend

        self.friend_just_revealed = friend_just_revealed

        # Mighty and Ripper cards
        self.mighty = cs.trump_to_mighty(trump)
        self.ripper = cs.trump_to_ripper(trump)

        if len(self.completed_tricks) < 10:
            self.next_calltype = cs.CallType.PLAY
        else:
            self.next_calltype = cs.CallType.GAME_OVER

        if len(self.completed_tricks) == 0:
            self.leader = self.declarer
        else:
            self.leader = self.trick_winners[-1]

    @classmethod
    def from_perspective(cls, perspective, hands, kitty):
        hands_copy = deepcopy(hands)
        kitty_copy = deepcopy(kitty)
        return cls(hands_copy, kitty_copy, deepcopy(perspective.point_cards), deepcopy(perspective.completed_tricks),
                   perspective.trick_winners[:], deepcopy(perspective.current_trick),
                   perspective.declarer,
                   deepcopy(perspective.trump), perspective.bid, perspective.friend,
                   deepcopy(perspective.called_friend), perspective.friend_just_revealed)


# This should be all the inferences for all the players grouped adequately
class Inferences:
    """Contains the inferences for all 5 players for a given perspective."""

    def __init__(self, pers: cs.Perspective):
        self.perspective = pers
        self.inferences = [[Inference(p, True, CardSet()), Inference(p, False, CardSet())] for p in range(5)]

        self.inferences[self.perspective.player][0] += Inference(self.perspective.player, True,
                                                                 CardSet(', '.join(map(str, self.perspective.hand))))
        self.inferences[self.perspective.player][1] += Inference(self.perspective.player, False,
                                                                 CardSet(', '.join(map(str, self.perspective.hand)),
                                                                         complement=True))

        # The loop below creates inferences from the previous gameplay
        tricks = pers.completed_tricks + [pers.current_trick]
        for trick_num in range(len(tricks)):
            trick = tricks[trick_num]

            # The block below adequately finds the suit_led for the trick
            if trick_num < len(pers.completed_tricks):
                suit_led = pers.completed_tricks[trick_num][0].suit_led
            else:
                suit_led = pers.current_trick.suit_led

            for play in trick:
                player, card = play.player, play.card
                if not card.suit.is_nosuit() and card != pers.mighty and not card.is_joker() and card.suit != suit_led:
                    self.inferences[player][1] += Inference(player, False, CardSet(suit_led))

    def player_inference(self, player):
        """Returns the inferences for a certain player."""
        return self.inferences[player]

    def __repr__(self):
        r_str = []
        for player_infs in self.inferences:
            for inf in player_infs:
                r_str.append(repr(inf))
        return '\n'.join(r_str)


class Inference:
    """An inference for a player."""

    def __init__(self, player, has: bool, cardset):
        self.player = player
        self.has = has  # When True, player has cardset. When false, player does not have cardset.
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

    def __init__(self, parent=None, arriving_play=None):
        self.parent = parent
        self.arriving_play = arriving_play
        self.children = []
        self._play_to_children = {}  # dictionary to map moves to children

        self.reward_sum = 0
        self.visits = 0
        self.avails = 1

        self._tried_plays = set()

    def untried_plays(self, legal_plays):
        """Returns the elements of legal_moves for which this node has no children."""
        return [play for play in legal_plays if play not in self._tried_plays]

    def ucb_child_select(self, legal_plays, exploration=0.7):
        """Uses the UCB1 formula to select a child node, filtered by the legal_moves."""
        legal_children = [self._play_to_children[play] for play in legal_plays]

        # Select child with highest UCB score
        selected = max(legal_children,
                       key=lambda c: c.reward_sum / c.visits + exploration * sqrt(log(c.avails) / c.visits))

        # Update availability counts
        for child in legal_children:
            child.avails += 1

        return selected

    def add_child(self, play: cs.Play):
        """Add child to node and return child."""
        child = InfoSet(self, play)

        self.children.append(child)
        self._play_to_children[play] = child
        self._tried_plays.add(play)

        return child

    def update(self, rewards: list):
        """Update this node's reward_sum and visit count based on the rewards of a rollout."""
        self.visits += 1
        if self.arriving_play is not None:
            self.reward_sum += rewards[self.arriving_play.player]

    def __repr__(self):
        return "[Play:{} R/V/A: {}/{}/{}]".format(self.arriving_play, self.reward_sum, self.visits, self.avails)

    def tree_info_constructor(self):
        if len(self.children) == 0:
            return TreeInfoDataStructure([[self.visits]])
        else:
            tree_info = reduce(lambda x, y: x + y, (child.tree_info_constructor() for child in self.children))
            tree_info.add_parent(self.visits)
            return tree_info

    def tree_info(self):
        header = ' ///// TREE INFO ///////////////////\n'
        play_info_str = ' | '.join(repr(child.arriving_play) for child in self.children)
        tree_info_str = str(self.tree_info_constructor())
        footer = '\n ///////////////////////////////////'
        return header + play_info_str + '\n' + tree_info_str + footer


class TreeInfoDataStructure:
    """Data structure representing a tree_info data."""

    def __init__(self, layers: List[List[int]]):
        """Note: empty nodes must be represented by -1"""
        assert all(len(layer) == len(layers[0]) for layer in layers)
        self.layers = layers

    def depth(self):
        return len(self.layers)

    def width(self):
        return len(self.layers[0])

    def add_parent(self, parent_visits):
        parent_layer = [parent_visits] + [-1] * (self.width() - 1)
        self.layers = [parent_layer] + self.layers

    def __add__(self, other):
        """Adds together the layers, layer by layer."""
        if not isinstance(other, TreeInfoDataStructure):
            raise TypeError("TreeInfoDataStructure can only be added with another of its type")
        layer_count = max(self.depth(), other.depth())
        my_layers = self.layers + [[-1] * self.width() for _ in range(layer_count - self.depth())]
        other_layers = other.layers + [[-1] * other.width() for _ in range(layer_count - other.depth())]
        merged_layers = []
        for i in range(layer_count):
            merged_layers.append(my_layers[i] + other_layers[i])
        return TreeInfoDataStructure(merged_layers)

    def __str__(self):
        def padding(width_location):
            max_digits = 1
            for layer in self.layers:
                value = layer[width_location]
                if value >= 0:
                    max_digits = max(max_digits, len(str(value)))
            return max_digits

        layer_strings = []
        for layer in self.layers:
            layer_string_builder = []
            for i, value in enumerate(layer):
                if value >= 0:
                    layer_string_builder.append(f"{value:<{padding(i)}}")
                else:
                    layer_string_builder.append(' ' * padding(i))
            layer_strings.append(' '.join(layer_string_builder))
        return '\n'.join(layer_strings)


def determinize(perspective: cs.Perspective, mode=0) -> GameState:
    """Determinize the given perspective into a deterministic state.

    The mode parameter determines the way in which determinization happens.
    """
    if mode == 0:
        is_declarer = perspective.player == perspective.declarer

        played_cards = set()
        for trick in perspective.completed_tricks:
            for play in trick:
                played_cards.add(play.card)
        for play in perspective.current_trick:
            played_cards.add(play.card)
        for card in perspective.hand:
            played_cards.add(card)
        if is_declarer:
            for card in perspective.kitty:
                played_cards.add(card)

        unplayed_cards = []
        for card in Card.iter():
            if card not in played_cards:
                unplayed_cards.append(card)
        random.shuffle(unplayed_cards)
        determinized_hands = [[] for _ in range(5)]

        if not is_declarer:
            assert len(unplayed_cards) == sum(perspective.hand_sizes) - len(perspective.hand) + 3
        else:
            assert len(unplayed_cards) == sum(perspective.hand_sizes) - len(perspective.hand)

        for player in range(5):
            if player != perspective.player:
                hand_size = perspective.hand_sizes[player]
                for _ in range(hand_size):
                    determinized_hands[player].append(unplayed_cards.pop())
        determinized_hands[perspective.player] = perspective.hand

        if not is_declarer:
            determinized_kitty = unplayed_cards
        else:
            determinized_kitty = perspective.kitty

        determinized_state = GameState.from_perspective(perspective, determinized_hands, determinized_kitty)
        return determinized_state
    else:
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


def ismcts(perspective: cs.Perspective, itermax: int = 50, verbose=False, biased=False) -> cs.Play:
    """Performs an ISMCTS search from the given perspective and returns the best move after itermax iterations."""

    root_node = InfoSet()
    for i in range(itermax):
        node_head = root_node

        # Determinization
        determinized_state = determinize(perspective, biased)

        # Checking if there's only a single available move
        legal_plays = determinized_state.get_legal_plays()
        if len(legal_plays) == 1:
            if verbose:
                print("Single move found - skipping ISMCTS")
            return legal_plays[0]

        # Selection
        while legal_plays and len(node_head.untried_plays(legal_plays)) == 0:
            # this node is fully expanded and non-terminal
            node_head = node_head.ucb_child_select(legal_plays)
            determinized_state.play(node_head.arriving_play)
            legal_plays = determinized_state.get_legal_plays()

        # Expansion
        untried_plays = node_head.untried_plays(legal_plays)
        if untried_plays:  # if we can expand (i.e. state/node is non-terminal)
            chosen_play = random.choice(untried_plays)
            determinized_state.play(chosen_play)
            node_head = node_head.add_child(chosen_play)  # add child and descend tree

        # Simulation
        while determinized_state.next_calltype == cs.CallType.PLAY:
            legal_plays = determinized_state.get_legal_plays()
            determinized_state.play(random.choice(legal_plays))

        # Backpropagation
        while node_head is not None:
            node_head.update(determinized_state.gamepoints_rewarded)
            node_head = node_head.parent

    if verbose:
        print(root_node.tree_info(), file=sys.stderr)

    best_node = max(root_node.children, key=lambda child: child.visits)
    return best_node.arriving_play

"""The AI worker module of Tranquil Tempest, the Mighty AI

This module contains the ISMCTS-based AI algorithm for the game of Mighty.
This module has been written in mind of being called from tranquil.py, the front-end of Tranquil Tempest.

Development started 2019/06/15
"""

from game_logic import engine
from game_logic import constructs as cs
from game_logic.cards import Card, Suit, Rank
from math import sqrt, log
import random


class GameState(engine.GameEngine):
    """The class for a state of the Mighty game, in its 'play' stage.

    This class is not meant to cover the early stages of the game before the tricks."""

    def __init__(self, hands, kitty, point_cards, completed_tricks, trick_winners, current_trick, previous_suit_leds,
                 suit_led, declarer, trump, bid, friend, called_friend, friend_just_revealed):
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
            if trick_num < len(pers.previous_suit_leds):
                suit_led = pers.previous_suit_leds[trick_num]
            else:
                suit_led = pers.suit_led

            for play in trick:
                player, card = play.player, play.card
                if not card.suit.is_nosuit() and card != pers.mighty and card.suit != suit_led:
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


def ismcts(perspective: cs.Perspective, itermax: int, verbose=False, biased=False) -> cs.Play:
    """Performs an ISMCTS search from the given perspective and returns the best move after itermax iterations."""

    root_node = InfoSet()
    for i in range(itermax):
        node_head = root_node

        # Determinization
        determinized_state = determinize(perspective, biased)

        # Selection
        legal_plays = determinized_state.legal_plays()
        while legal_plays and len(node_head.untried_plays(legal_plays)) == 0:
            # this node is fully expanded and non-terminal
            node_head = node_head.ucb_child_select(legal_plays)
            determinized_state.play(node_head.play)
            legal_plays = determinized_state.legal_plays()

        # Expansion
        untried_plays = node_head.untried_plays(legal_plays)
        if untried_plays:  # if we can expand (i.e. state/node is non-terminal)
            chosen_play = random.choice(untried_plays)
            determinized_state.play(chosen_play)
            node_head = node_head.add_child(chosen_play)  # add child and descend tree

        # Simulation
        while determinized_state.next_call == engine.CallType.PLAY:
            legal_plays = determinized_state.legal_plays()
            determinized_state.play(random.choice(legal_plays))

        # Backpropagation
        while node_head is not None:
            node_head.update(determinized_state.gamepoints_rewarded)

    if verbose:
        print(root_node.tree_info())

    return max(root_node.children, key=lambda child: child.visits).play




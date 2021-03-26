"""A script to play mighty in the console, using the engine.py module."""

import random
from game_logic.cards import *
from game_logic import engine
from game_logic import constructs as cs
from time import time
import tempest

space = 100
card_mode = 0  # 0 for standard card string, 1 for unicode representations


def card_repr(card: Card) -> str:
    if card_mode == 1:
        return card.unicode()
    elif card_mode == 0:
        return card.__repr__()
    else:
        return card.__repr__()


def random_random_player(pers: cs.Perspective) -> cs.Play:
    """A very random AI player of Mighty."""

    valid_moves = cs.legal_plays(pers.player, pers.hand, pers.completed_tricks, pers.current_trick,
                                 pers.suit_led, pers.trump, pers.next_calltype, pers.leader)

    return random.choice(valid_moves)


def random_random_bidder(pers: cs.Perspective) -> tuple:
    hand = pers.hand
    minimum_bid = pers.minimum_bid
    highest_bid = pers.highest_bid
    prev_trump = pers.trump_candidate

    """A very random AI bidder of Mighty"""
    # Note that you can call one less with a no-trump
    suit_counts = {}
    for suit in Suit.iter():
        count = 0
        for card in hand:
            if card.suit == suit:
                count += 1
        suit_counts[suit.val] = count

    maximum_suit_num = max(suit_counts.values())
    trump = None
    for suit_val in suit_counts:
        if suit_counts[suit_val] == maximum_suit_num:
            trump = Suit(suit_val)

    for bid in range(1, 21):
        if cs.is_valid_bid(trump, bid, minimum_bid, prev_trump=prev_trump, highest_bid=highest_bid):
            if random.random() > bid / 21:
                if random.random() > 0.9:
                    trump = Suit(0)
                return trump, bid
            else:
                break

    return None, 0


def imma_call_miss_deal(pers: cs.Perspective) -> bool:
    """Will always call miss-deal. That is, this function simply returns True."""
    hand = pers.hand
    trump = pers.trump
    return True


def random_random_exchanger(pers: cs.Perspective) -> tuple:
    """Returns three cards to discard and the trump to change to, on a very random basis."""
    hand = pers.hand
    trump = pers.trump
    random.shuffle(hand)
    return hand[:3], trump


def mighty_joker_trump_friend_caller(pers: cs.Perspective) -> cs.FriendCall:
    """Calls the friend card, prioritizing the mighty, followed by joker, then a card of the trump suit.

    Doesn't call itself."""
    hand = pers.hand
    kitty = pers.kitty
    trump = pers.trump
    mighty = pers.mighty

    if mighty not in hand + kitty:
        return cs.FriendCall(0, mighty)
    elif not any([c.is_joker() for c in hand + kitty]):
        return cs.FriendCall(0, Card.joker())
    else:
        if not trump.is_nosuit():
            rank_priority_order = [1, 13, 12, 11, 10, 9, 8, 7, 6]
            for rank_val in rank_priority_order:
                card = Card(trump, Rank(rank_val))
                if card not in hand + kitty:
                    return cs.FriendCall(0, card)
            raise RuntimeError("Nope. This can't have happened.")
        else:
            rank_priority_order = [1, 13, 12, 11, 10, 9, 8, 7, 6]
            for rank_val in rank_priority_order:
                for suit in Suit.iter():
                    card = Card(suit, Rank(rank_val))
                    if card not in hand + kitty:
                        return cs.FriendCall(0, card)
            raise RuntimeError("Nope. This can't have happened.")


def introduce_hands(hands: list, players: list) -> None:
    """Introduce the hands of players, revealing and hiding upon Enter."""
    for player in players:
        input("Press Enter to reveal Player {}'s hand.".format(player))
        print(' '.join([card_repr(c) for c in sorted(
            hands[player], key=lambda c: (c.suit.val, c.rank.val))]))
        input("Press Enter to clear screen.")
        print('\n' * space)


################### SETUP ####################

ai_bidders = [random_random_bidder] * 5
ai_miss_deal_callers = [imma_call_miss_deal] * 5
ai_exchangers = [random_random_exchanger] * 5
ai_friend_callers = [mighty_joker_trump_friend_caller] * 5
ai_players = [tempest.ismcts] * 5


##############################################


def play_game(ai_bidder_functions=None,
              ai_miss_deal_caller_functions=None,
              ai_exchanger_functions=None,
              ai_friend_caller_functions=None,
              ai_player_functions=None,
              verbose=2):
    if ai_bidder_functions is None:
        ai_bidder_functions = ai_bidders
    if ai_miss_deal_caller_functions is None:
        ai_miss_deal_caller_functions = ai_miss_deal_callers
    if ai_exchanger_functions is None:
        ai_exchanger_functions = ai_exchangers
    if ai_friend_caller_functions is None:
        ai_friend_caller_functions = ai_friend_callers
    if ai_player_functions is None:
        ai_player_functions = ai_players

    def print2(*args, **kwargs):
        if verbose >= 2:
            print(*args, **kwargs)

    def print1(*args, **kwargs):
        if verbose >= 1:
            print(*args, **kwargs)

    global space
    while True:
        ai_num = '5'
        # ai_num = input("How many AI agents?: ")
        print()
        if ai_num.isdigit() and int(ai_num) in range(6):
            ai_num = int(ai_num)
            break
        print("Invalid input.")

    if ai_num == 5:  # Just to see how long a randomized game lasts.
        start = time()
    else:
        start = None

    ai_players_seed = [True] * ai_num + [False] * (5 - ai_num)
    random.shuffle(ai_players_seed)

    ai_player_numbers = []
    for i in range(len(ai_players_seed)):
        if ai_players_seed[i]:
            ai_player_numbers.append(i)

    human_players = [p for p in range(5) if p not in ai_player_numbers]
    if len(human_players) == 1:
        space = 0

    ai_nums_str = ', '.join([str(x) for x in ai_player_numbers])
    print2('Player numbers {} are AI agents.'.format(ai_nums_str))
    print2()

    # Initiating the game object.
    mighty_game = engine.GameEngine()
    feedback = -1
    final_trump = None

    introduce_hands(mighty_game.hands, human_players)

    # Here starts the game loop.
    while True:
        '''
        ################################### TESTING ############################
        import tempest
        print(repr(tempest.Inferences(mighty_game.perspective(0))))
        input("\nWAITING...")
        ########################################################################
        '''
        call_type = mighty_game.next_calltype
        if call_type == cs.CallType.BID:
            print2("Player {}'s turn to make a bid.".format(mighty_game.next_bidder))

            if mighty_game.highest_bid is None:
                lower_bound = mighty_game.minimum_bid
            else:
                lower_bound = mighty_game.highest_bid + 1

            print2("Bid must be greater or equal to {}.".format(lower_bound))

            if mighty_game.next_bidder in ai_player_numbers:
                trump, bid = ai_bidder_functions[mighty_game.next_bidder](
                    mighty_game.get_perspective(mighty_game.next_bidder))
            else:
                print("To pass, enter 0 for the bid.")
                while True:
                    while True:
                        trump = input("Enter trump(N for no-trump): ")
                        bid = input("Enter bid: ")
                        if (Suit.is_suitstr(trump) and bid.isdigit()) or bid == '0':
                            bid = int(bid)
                            break
                        print('Invalid bid.')
                    if bid == 0:
                        break
                    else:
                        trump = Suit.str_to_suit(trump)
                        if cs.is_valid_bid(trump, bid, mighty_game.minimum_bid,
                                           prev_trump=mighty_game.trump_candidate,
                                           highest_bid=mighty_game.highest_bid):
                            break
                    print("Invalid bid.")

            if bid != 0:
                print2("Player {} bids {} {}.".format(mighty_game.next_bidder, trump.long(), bid))
            else:
                print2("Player {} passes.".format(mighty_game.next_bidder))

            feedback = mighty_game.bidding(mighty_game.next_bidder, trump, bid)

        elif call_type == cs.CallType.EXCHANGE:
            print2('Declarer: {}'.format(mighty_game.declarer))
            print2("Final bid: {} {}".format(
                mighty_game.trump.long(), mighty_game.bid))
            print2("Card exchange in process.")
            if mighty_game.declarer in ai_player_numbers:
                to_discard, final_trump = ai_exchanger_functions[mighty_game.declarer](
                    mighty_game.get_perspective(mighty_game.declarer))
            else:
                input('Player {} - Press Enter to reveal the kitty'.format(mighty_game.declarer))
                print(' '.join([str(c) for c in mighty_game.kitty]))
                while True:
                    to_discard = input("Enter the three cards to discard, space separated: ")
                    to_discard = to_discard.split()
                    if len(to_discard) == 3 and all(
                            [Card.is_cardstr(x) and Card.str_to_card(x) in mighty_game.hands[
                                mighty_game.declarer] + mighty_game.kitty for x in to_discard]):
                        to_discard = [Card.str_to_card(x) for x in to_discard]
                        break
                    print("Invalid input.")

                print('\n' * space)

            print2('Exchange over.')
            feedback = mighty_game.exchange(mighty_game.declarer, to_discard)

        elif call_type == cs.CallType.TRUMP_CHANGE:
            for hand in mighty_game.hands:
                print2(hand)

            prev_trump = mighty_game.trump
            if mighty_game.declarer in human_players:
                while True:
                    final_trump = input("Finalize your trump: ")
                    if Suit.is_suitstr(final_trump):
                        final_trump = Suit.str_to_suit(final_trump)
                        feedback = mighty_game.trump_change(mighty_game.declarer, final_trump)
                        if feedback == 0:
                            break
                    print("Invalid trump.")
            else:
                feedback = mighty_game.trump_change(mighty_game.declarer, final_trump)

            new_trump = mighty_game.trump

            changed_or_fixed = 'changed' if new_trump != prev_trump else 'fixed'

            print2("The trump suit has been {} to {}.".format(
                changed_or_fixed, final_trump.long()))
            print2('The final bid is {} {}.'.format(
                mighty_game.trump.long(), mighty_game.bid))

        elif call_type == cs.CallType.MISS_DEAL_CHECK:
            print2("Miss-deal check in process.")
            deal_miss = [False] * 5
            for player in range(5):
                call_miss_deal = False
                if cs.is_miss_deal(mighty_game.hands[player], mighty_game.mighty):
                    if player in ai_player_numbers:
                        call_miss_deal = ai_miss_deal_caller_functions[player](
                            mighty_game.get_perspective(player))
                    else:
                        yes_or_no = input('Player {} - Call miss-deal?: '.format(player))
                        if yes_or_no.lower() in ('y', 'yes'):
                            call_miss_deal = True
                    if call_miss_deal:
                        print2("Player {} announces miss-deal!".format(player))
                        print2(' '.join([str(c) for c in mighty_game.hands[player]]))
                    deal_miss[player] = call_miss_deal

            for player in range(5):
                feedback = mighty_game.miss_deal_check(player, deal_miss[player])
                if feedback:
                    print('Fuck.')
                    print(feedback)
                    raise RuntimeError
                if mighty_game.next_calltype != cs.CallType.MISS_DEAL_CHECK:
                    print2("Miss-deal check over.")
                    break

        elif call_type == cs.CallType.FRIEND_CALL:
            print2("Friend to be called.")
            if mighty_game.declarer in ai_player_numbers:
                friend_call = ai_friend_caller_functions[mighty_game.declarer](
                    mighty_game.get_perspective(mighty_game.declarer))
            else:
                while True:
                    friend_choice = input("Enter friend card or enter ftw or enter nf: ")
                    if Card.is_cardstr(friend_choice):
                        friend_choice = Card.str_to_card(friend_choice)
                        friend_call = cs.FriendCall(0, friend_choice)
                        break
                    elif friend_choice == 'ftw':
                        friend_call = cs.FriendCall(1)
                        break
                    elif friend_choice == 'nf':
                        friend_call = cs.FriendCall(2)
                        break
                    print("Invalid card.")

            print2("{} called.".format(friend_call))
            feedback = mighty_game.friend_call(mighty_game.declarer, friend_call)

        elif call_type == cs.CallType.REDEAL:
            print2("REDEAL IN PROCESS.")
            mighty_game = engine.GameEngine()
            print2("REDEAL COMPLETE.")
            introduce_hands(mighty_game.hands, human_players)

        elif call_type == cs.CallType.PLAY:

            player = mighty_game.next_player

            if player == mighty_game.leader:
                print2("Trick #{}".format(len(mighty_game.completed_tricks) + 1))
                print2()

            for play in mighty_game.current_trick:
                print2(play)
            print2()
            print2("Player {}'s turn to play.".format(player))
            print2(mighty_game.hands[player])

            perspective = mighty_game.get_perspective(player)

            if player in ai_player_numbers:
                play = ai_player_functions[player](perspective)
            else:
                valid_plays = mighty_game.get_legal_plays()
                print("Choose a play from below by index:")
                for i in range(len(valid_plays)):
                    print(f"{i}: {valid_plays[i]}")
                while True:
                    playnum = input("Player {} - Enter play number: ".format(player))
                    if playnum.isdigit() and 0 <= int(playnum) < len(valid_plays):
                        playnum = int(playnum)
                        play = valid_plays[playnum]
                        break
                    print("Invalid play.")

            print2(play)
            feedback = mighty_game.play(play)

            if mighty_game.friend_just_revealed:
                print2()
                print2("<<Friend revealed!!>>")
                print2("Friend is player {}".format(mighty_game.friend))
                print2()

            if mighty_game.is_trick_complete():
                if ai_num != 5:
                    input()
                print2('-------------------------------')
                print2()
                print2(" === Trick Summary === ")
                for play in mighty_game.completed_tricks[-1]:
                    print2(play)
                print2()

                print2("Trick won by Player {}!".format(mighty_game.trick_winners[-1]))

                for p in range(5):
                    # if p not in (mighty_game.declarer, mighty_game.friend):
                    print2('Player {}: {} points'.format(p, len(mighty_game.point_cards[p])))
                print2()
                print2('-------------------------------')

        elif call_type == cs.CallType.GAME_OVER:
            break

        else:
            raise RuntimeError(
                "CRITICAL: There is no method of handling specified for call type '{}'".format(call_type))

        if feedback:
            raise RuntimeError('Calltype: {}, Error #{}'.format(
                mighty_game.next_calltype, feedback))

        print2('-------------------------------')
        if ai_num != 5:
            input()

    print1("The game is over.")
    print1(f"Declarer: {mighty_game.declarer}, Friend: {mighty_game.friend}")
    print1("The bid was {} {}.".format(mighty_game.trump.long(), mighty_game.bid))
    print1("The Declarer and Friend collected {} points.".format(
        mighty_game.declarer_team_points))
    print1("Did the Declarer win?: {}".format(mighty_game.declarer_won))
    print1("The following gamepoints are rewarded to each player:")
    for player in range(len(mighty_game.gamepoints_rewarded)):
        formated_points = mighty_game.gamepoints_rewarded[player]
        if formated_points > 0:
            formated_points = '+' + str(formated_points)
        else:
            formated_points = str(formated_points)
        print1("Player {}: {} gamepoints".format(player, formated_points))

    if ai_num == 5:
        end = time()
        assert start is not None
        print1(f"The 5 AI game took {end - start} seconds to complete.")
    return mighty_game.gamepoints_rewarded


if __name__ == '__main__':
    play_game(ai_bidders, ai_miss_deal_callers, ai_exchangers, ai_friend_callers, ai_players)

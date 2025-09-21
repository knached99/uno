import collections
import random
from enum import Enum
from typing import Any, Callable, DefaultDict, List, Set, Tuple, Optional

from lib.notification import Notification


class Player:
    def __init__(self, name):
        self.id: str = f'player-{name}'
        self.name: str = name

    def __repr__(self) -> str:
        return f"Player(id={self.id}, name={self.name})"

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, obj) -> bool:
        return isinstance(obj, type(self)) and self.id == obj.id


class Card:
    def __init__(self, color, value):
        self.id: str = f'{value}-{color}'
        self.color: str = color
        self.value: str = value

    def is_special(self) -> bool:
        special_cards = set(Deck.DRAW_TWO_CARDS + Deck.REVERSE_CARDS +
                            Deck.SKIP_CARDS + Deck.DRAW_FOUR_CARDS + Deck.WILD_CARDS)
        return self.value in special_cards or self.color == 'black'

    def is_color_special(self) -> bool:
        special_cards = set(Deck.DRAW_TWO_CARDS + Deck.REVERSE_CARDS + Deck.SKIP_CARDS)
        return self.value in special_cards or self.color != 'black'

    def is_black(self) -> bool:
        return self.color == 'black'

    def is_draw_four(self) -> bool:
        return self.value == 'draw-four'

    def is_wild(self) -> bool:
        return self.value == 'wild'

    def __repr__(self) -> str:
        return f'Card(color={self.color}, value={self.value})'


class Deck:
    SHUFFLE_FREQ = 50
    COLORS = ['red', 'blue', 'green', 'yellow']
    NUMBER_CARDS = [str(i) for i in (list(range(0, 10)) + list(range(1, 10)))]
    DRAW_TWO_CARDS = ['draw-two'] * 2
    REVERSE_CARDS = ['reverse'] * 2
    SKIP_CARDS = ['skip'] * 2

    DRAW_FOUR_CARDS = ['draw-four'] * 4
    WILD_CARDS = ['wild'] * 4
    COLOR_CARDS = NUMBER_CARDS + DRAW_TWO_CARDS + REVERSE_CARDS + SKIP_CARDS

    def __init__(self):
        color_cards = [Card(color, value) for color in self.COLORS for value in self.COLOR_CARDS]
        black_cards = [Card('black', value) for value in (self.DRAW_FOUR_CARDS + self.WILD_CARDS)]

        self.cards: List[Card] = color_cards + black_cards
        self.shuffle()

    def get_cards(self) -> List[Card]:
        return self.cards

    def shuffle(self):
        for _ in range(self.SHUFFLE_FREQ):
            random.shuffle(self.cards)


class GameOverReason(Enum):
    WON = 'won'
    ERROR = 'error'
    INSUFFICIENT_PLAYERS = 'insufficient-players'


class Game:
    MIN_PLAYERS_ALLOWED = 2
    MAX_PLAYERS_ALLOWED = 2

    def __init__(self, room: str, players: Set[Player], hand_size: int):
        self.hands: DefaultDict[Player, List[Card]] = collections.defaultdict(list)
        self.players_list: List[Player] = sorted(list(players), key=lambda p: p.id)
        self.players: Set[Player] = set(self.players_list)
        self.current_index: int = 0
        self.direction: int = 1
        self.current_color: Optional[str] = None
        # Pending draw penalty state (e.g., from +2 / +4)
        self.pending_draw_count: int = 0
        self.pending_draw_for_index: Optional[int] = None
        self.notify = Notification(room)
        self.deck = Deck()

        self.validate_players()

        cards = self.deck.get_cards()
        total_players = len(self.players_list)
        self.remaining_cards: List[Card] = cards[total_players * hand_size:]
        dealt = cards[:total_players * hand_size]

        # Deal round-robin
        i = 0
        while i < len(dealt):
            for p in self.players_list:
                if i >= len(dealt):
                    break
                self.hands[p].append(dealt[i])
                i += 1

        # Start discard with a valid top card and apply start effects
        self.game_stack: List[Card] = []
        self._start_discard_with_valid_card()

    def remove_player(self, player) -> None:
        self.players.remove(player)
        self.players_list = [p for p in self.players_list if p != player]

    def validate_players(self) -> None:
        if len(self.players) < self.MIN_PLAYERS_ALLOWED:
            raise Exception(f"need at least {self.MIN_PLAYERS_ALLOWED} players to start the game")

    def get_state(self) -> Tuple[DefaultDict[Player, List[Card]], Card, str, Optional[str], int, Optional[str]]:
        self.validate_players()
        top_card = self.get_top_card()
        current_player_id = self.players_list[self.current_index].id
        pending_for_id = None
        if self.pending_draw_for_index is not None:
            pending_for_id = self.players_list[self.pending_draw_for_index].id
        return (self.hands, top_card, current_player_id, self.current_color, self.pending_draw_count, pending_for_id)

    def get_top_card(self) -> Card:
        return self.game_stack[-1]

    def transfer_played_cards(self) -> None:
        played_cards = self.game_stack[::]
        played_cards.pop()
        random.shuffle(played_cards)
        self.remaining_cards = played_cards[::]
        self.game_stack = [self.get_top_card()]

    def draw(self, player_id: str) -> None:
        self.validate_players()
        current_player = self.players_list[self.current_index]
        if player_id != current_player.id:
            self.notify.error('not your turn')
            return

        player = self.find_object(self.players, player_id)
        player_cards = self.hands[player]

        if not self.remaining_cards:
            self.transfer_played_cards()
        if not self.remaining_cards:
            self.notify.warn('deck is empty!')
            return

        new_card = self.remaining_cards.pop()
        player_cards.append(new_card)

        # Handle pending draw penalties countdown and turn advance when satisfied
        if self.pending_draw_count > 0 and self.pending_draw_for_index == self.current_index:
            self.pending_draw_count -= 1
            if self.pending_draw_count <= 0:
                # Penalty satisfied: skip this player's turn after drawing required cards
                self.pending_draw_count = 0
                self.pending_draw_for_index = None
                self._advance_turn(1)
        else:
            # Voluntary draw: if the drawn card cannot be played, pass turn immediately
            top_card = self.get_top_card()
            if not self._can_play_card(new_card, top_card):
                self._advance_turn(1)

    def play(self, player_id: str, card_id: str, on_game_over: Callable[[GameOverReason, Any], None], chosen_color: Optional[str] = None, uno_called: bool = False) -> None:
        self.validate_players()
        current_player = self.players_list[self.current_index]
        if player_id != current_player.id:
            self.notify.error('not your turn')
            return

        # If there is a pending draw penalty for the current player, they must draw first
        if self.pending_draw_count > 0 and self.pending_draw_for_index == self.current_index:
            self.notify.error(f'must draw {self.pending_draw_count} card(s) before playing')
            return

        player = self.find_object(self.players, player_id)
        player_cards = self.hands[player]
        card = self.find_object(player_cards, card_id)
        top_card = self.get_top_card()

        if not self._can_play_card(card, top_card):
            self.notify.error('cannot play this card')
            return

        if card.is_draw_four():
            if self.current_color is not None and any(c.color == self.current_color for c in player_cards if not c.is_black()):
                self.notify.error('cannot play draw four when you have a card of the current color')
                return

        # Remove and place on discard
        idx = self.find_object_idx(player_cards, card.id)
        player_cards.pop(idx)
        self.game_stack.append(card)

        # Update current color
        if card.is_black():
            if chosen_color not in Deck.COLORS:
                self.notify.error('please choose a color to play a wild card')
                return
            self.current_color = chosen_color
        else:
            self.current_color = card.color

        # UNO penalty
        if len(player_cards) == 1 and not uno_called:
            self.notify.error(f"{player.name} didn't say UNO! Drawing 2 penalty cards.")
            self._draw_n(player, 2)

        # Win check
        if len(player_cards) == 0:
            score = self._calculate_score(exclude_player=player)
            self.notify.success(f"{player.name} won the game with {score} points!")
            on_game_over(GameOverReason.WON, player)
            return

        # Action effects
        steps = 1
        if card.value == 'skip':
            steps = 2
        elif card.value == 'reverse':
            if len(self.players_list) == 2:
                steps = 2
            else:
                self.direction *= -1
        elif card.value == 'draw-two':
            # Set pending draw for the next player and pass turn to them
            next_idx = self._next_index(1)
            self.pending_draw_count = 2
            self.pending_draw_for_index = next_idx
            steps = 1
        elif card.is_draw_four():
            # Set pending draw for the next player and pass turn to them
            next_idx = self._next_index(1)
            self.pending_draw_count = 4
            self.pending_draw_for_index = next_idx
            steps = 1

        self._advance_turn(steps)

    def find_object(self, objects, obj_id: str):
        objects = list(objects)
        idx = self.find_object_idx(objects, obj_id)
        return objects[idx]

    def find_object_idx(self, objects, obj_id: str):
        return [obj.id for obj in objects].index(obj_id)

    # Helpers
    def _start_discard_with_valid_card(self):
        while True:
            if not self.remaining_cards:
                self.transfer_played_cards()
            card = self.remaining_cards.pop()
            if card.is_draw_four():
                self.remaining_cards.insert(0, card)
                random.shuffle(self.remaining_cards)
                continue
            self.game_stack.append(card)
            if card.is_black():
                self.current_color = random.choice(Deck.COLORS)
            else:
                self.current_color = card.color

            if card.value == 'skip':
                self._advance_turn(2)
            elif card.value == 'reverse':
                if len(self.players_list) == 2:
                    self._advance_turn(2)
                else:
                    self.direction *= -1
            elif card.value == 'draw-two':
                # Do not auto-draw; set pending draw for the next player and move turn to them
                next_idx = self._next_index(1)
                self.pending_draw_count = 2
                self.pending_draw_for_index = next_idx
                self._advance_turn(1)
            break

    def _advance_turn(self, steps: int = 1):
        self.current_index = self._next_index(steps)

    def _next_index(self, steps: int = 1) -> int:
        n = len(self.players_list)
        return (self.current_index + steps * self.direction) % n

    def _draw_n(self, player: Player, n: int):
        for _ in range(n):
            if not self.remaining_cards:
                self.transfer_played_cards()
            if not self.remaining_cards:
                return
            self.hands[player].append(self.remaining_cards.pop())

    def _can_play_card(self, card: Card, top_card: Card) -> bool:
        if self.current_color:
            if card.is_black():
                return True
            return card.color == self.current_color or card.value == top_card.value
        if top_card.is_black():
            return True
        return card.is_black() or card.color == top_card.color or card.value == top_card.value

    def _calculate_score(self, exclude_player: Player) -> int:
        total = 0
        for p in self.players_list:
            if p == exclude_player:
                continue
            for c in self.hands[p]:
                if c.value.isdigit():
                    total += int(c.value)
                elif c.value in ('draw-two', 'reverse', 'skip'):
                    total += 20
                elif c.is_black():
                    total += 50
        return total

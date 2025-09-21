import logging
import pickle
import sqlite3
from typing import Optional, Set, Tuple

from core.uno import Game, Player

log = logging.getLogger('state')
log.setLevel(logging.INFO)

GAME_EXPIRATION_TIME = 86_400  # 1 day
ROOM_EXPIRATION_TIME = 86_400  # 1 day


class State:
    def __init__(self, db_path=':memory:'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS games (
            room TEXT PRIMARY KEY,
            data BLOB,
            expires_at INTEGER
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS players (
            room TEXT PRIMARY KEY,
            data BLOB,
            expires_at INTEGER
        )''')
        self.conn.commit()

    def allow_player(self, action: str, room: str, player: Player) -> Tuple[bool, Optional[str]]:
        # Validate player
        if not player.name or player.name == '':
            return (False, f'name cannot be blank')

        if ' ' in player.name:
            return (False, f'name should not contain white spaces')

        # Validate room
        if room == '':
            return (False, f'room should not be empty')

        if action == "Join":  # Check if room exists
            exists = self._exists_players(room)
            if not exists:
                return (False, f'cannot join game, room {room} does not exist')

        # Validate game
        started = bool(self.get_game_by_room(room))
        players = self.get_players_by_room(room)

        if len(players) == Game.MAX_PLAYERS_ALLOWED:
            return (False, f"room is full, max {Game.MAX_PLAYERS_ALLOWED} players are supported")

        if started:
            if player not in players:
                return (False, f'cannot join, game in the room {room} has already started')
        else:
            if player in players:
                return (False, f"name {player.name} is already taken for this room, try a different name")

        return (True, None)

    def _exists_players(self, room: str) -> bool:
        c = self.conn.cursor()
        c.execute('SELECT 1 FROM players WHERE room=?', (room,))
        return c.fetchone() is not None

    def get_game_by_room(self, room: str) -> Optional[Game]:
        c = self.conn.cursor()
        c.execute('SELECT data FROM games WHERE room=?', (room,))
        row = c.fetchone()
        if not row:
            return None
        return pickle.loads(row[0])

    def add_game_to_room(self, room: str, game: Game) -> None:
        obj = pickle.dumps(game)
        c = self.conn.cursor()
        c.execute('REPLACE INTO games (room, data, expires_at) VALUES (?, ?, ?)',
                  (room, obj, None))
        self.conn.commit()

    def update_game_in_room(self, room: str, game: Game) -> None:
        self.add_game_to_room(room, game)

    def get_players_by_room(self, room: str) -> Set[Player]:
        c = self.conn.cursor()
        c.execute('SELECT data FROM players WHERE room=?', (room,))
        row = c.fetchone()
        if not row:
            return set()
        return pickle.loads(row[0])

    def add_player_to_room(self, room: str, player: Player) -> None:
        log.info(f"adding player {player} to room {room}")
        players = self.get_players_by_room(room)
        players.add(player)
        obj = pickle.dumps(players)
        c = self.conn.cursor()
        c.execute('REPLACE INTO players (room, data, expires_at) VALUES (?, ?, ?)',
                  (room, obj, None))
        self.conn.commit()

    def remove_player_from_room(self, room: str, player: Player) -> None:
        log.info(f"removing player {player} from room {room}")
        players = self.get_players_by_room(room)
        players.remove(player)
        obj = pickle.dumps(players)
        c = self.conn.cursor()
        c.execute('REPLACE INTO players (room, data, expires_at) VALUES (?, ?, ?)',
                  (room, obj, None))
        self.conn.commit()

    def delete_all(self, room: str) -> None:
        self.delete_room(room)
        self.delete_game(room)

    def delete_room(self, room: str) -> None:
        c = self.conn.cursor()
        c.execute('DELETE FROM players WHERE room=?', (room,))
        self.conn.commit()
        log.info(f"deleted {room}")

    def delete_game(self, room: str) -> None:
        c = self.conn.cursor()
        c.execute('DELETE FROM games WHERE room=?', (room,))
        self.conn.commit()
        log.info(f"deleted game for room {room}")

    def list_rooms(self) -> list:
        c = self.conn.cursor()
        c.execute('SELECT room FROM players')
        return [row[0] for row in c.fetchall()]

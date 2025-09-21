import { Card, Hands, Player } from './game';

export type GameStateResponse = {
  hands: Hands;
  top_card: Card;
  current_player_id?: string;
  current_color?: string;
  pending_draw_count?: number;
  pending_for_player_id?: string;
};

export type GameNotifyResponse = {
  type: string;
  message: string;
};

export type GameRoomResponse = {
  players: Player[];
};

export enum GameOverReason {
  Won = 'won',
  Error = 'error',
  InsufficientPlayers = 'insufficient-players',
}

export type GameOverResponse =
  | GameOverWonResponse
  | GameOverErrorResponse
  | GameOverInsufficientPlayersResponse;

type GameOverWonResponse = {
  reason: GameOverReason.Won;
  winner: string;
};

type GameOverErrorResponse = {
  reason: GameOverReason.Error;
};

type GameOverInsufficientPlayersResponse = {
  reason: GameOverReason.InsufficientPlayers;
};

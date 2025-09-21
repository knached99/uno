import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Socket } from 'socket.io-client';
import { GAME_STATE_REFETCH_INTERVAL } from '../config/game';
import { Card, Events, Hands, Player } from '../types/game';
import { Routes } from '../types/routes';
import {
  GameOverReason,
  GameOverResponse,
  GameStateResponse,
} from '../types/ws';
import Avatar from './avatar';
import CardStack from './cards/stack';
import UnoCard from './cards/uno';
import Loader from './loader';

interface GameProps {
  currentPlayer: Player;
  players: Player[];
  socket: Socket;
  started: boolean;
  room: string;
}

function Game(props: GameProps): React.ReactElement {
  const { socket, currentPlayer, players, started, room } = props;
  const navigate = useNavigate();

  const [hands, setHands] = useState<Hands | null>(null);
  const [topCard, setTopCard] = useState<Card | null>(null);
  const [hasDrawn, setHasDrawn] = useState(false);
  const prevPlayerId = useRef<string | null>(null);
  const [currentTurnPlayerId, setCurrentTurnPlayerId] = useState<string | null>(null);
  const [currentColor, setCurrentColor] = useState<string | null>(null);
  const [unoCalled, setUnoCalled] = useState(false);
  const [wildPicker, setWildPicker] = useState<{ visible: boolean; cardId: string | null }>({ visible: false, cardId: null });
  const [pendingDrawCount, setPendingDrawCount] = useState<number>(0);
  const [pendingForPlayerId, setPendingForPlayerId] = useState<string | null>(null);
  const prevMyHandIdsRef = useRef<string[]>([]);
  const [lastDrawnCardId, setLastDrawnCardId] = useState<string | null>(null);
  const [lastDrawnPlayable, setLastDrawnPlayable] = useState<boolean>(false);
  const lastDrawnIdRef = useRef<string | null>(null);

  useEffect(() => {
    const intervalId = setInterval(() => {
      socket.emit(Events.GAME_STATE, { room });
    }, GAME_STATE_REFETCH_INTERVAL);

    return () => {
      clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    function canPlayCard(card: Card, top: Card, color: string | null): boolean {
      if (!card || !top) return false;
      if (color) {
        if (card.color === 'black') return true;
        return card.color === color || card.value === top.value;
      }
      if (top.color === 'black') return true;
      return card.color === top.color || card.value === top.value || card.color === 'black';
    }

  function onGameState(data: GameStateResponse): void {
      setHands(data.hands);
      setTopCard(data.top_card);
      if (data.current_player_id) setCurrentTurnPlayerId(data.current_player_id);
      if (data.current_color) setCurrentColor(data.current_color);
      setPendingDrawCount(data.pending_draw_count ?? 0);
      setPendingForPlayerId(data.pending_for_player_id ?? null);
      // Reset hasDrawn if it's a new turn for this player
      if (data.current_player_id) {
        if (prevPlayerId.current !== data.current_player_id) {
          prevPlayerId.current = data.current_player_id;
          setHasDrawn(false);
          setLastDrawnCardId(null);
          setLastDrawnPlayable(false);
          lastDrawnIdRef.current = null;
          // Reset UNO flag on turn change
          if (data.current_player_id === currentPlayer.id) {
            setUnoCalled(false);
          }
        }
      }

      // Detect newly drawn card for current player and whether it's playable
      try {
        const myHand = data.hands?.[currentPlayer.id] || [];
        const newIds = myHand.map(c => c.id);
        const prevIds = prevMyHandIdsRef.current;
        const addedId = newIds.find(id => !prevIds.includes(id)) || null;
        prevMyHandIdsRef.current = newIds;

    if (addedId && data.current_player_id === currentPlayer.id) {
          const drawn = myHand.find(c => c.id === addedId)!;
          const playable = data.top_card ? canPlayCard(drawn, data.top_card, data.current_color || null) : false;
          setLastDrawnCardId(addedId);
          setLastDrawnPlayable(playable);
          lastDrawnIdRef.current = addedId;
        }
        // If the previously tracked drawn card is no longer in hand, clear the helper
        if (lastDrawnIdRef.current && !newIds.includes(lastDrawnIdRef.current)) {
          setLastDrawnCardId(null);
          setLastDrawnPlayable(false);
          lastDrawnIdRef.current = null;
        }
        // Clear when not my turn or when under penalty
        if (data.current_player_id !== currentPlayer.id || (data.pending_draw_count ?? 0) > 0) {
          setLastDrawnCardId(null);
          setLastDrawnPlayable(false);
          lastDrawnIdRef.current = null;
        }
      } catch {}
    }
    socket.on(Events.GAME_STATE, onGameState);

    function onGameOver(data: GameOverResponse): void {
      const { reason } = data;

      switch (reason) {
        case GameOverReason.Won:
          const { winner } = data;
          navigate(Routes.Won, { state: { winner } });
          break;
        case GameOverReason.InsufficientPlayers:
          setTimeout(() => {
            navigate(0); // Refresh
          }, 5000);
          break;
      }
    }
    socket.on(Events.GAME_OVER, onGameOver);

    return () => {
      socket.off(Events.GAME_STATE, onGameState);
      socket.off(Events.GAME_OVER, onGameState);
    };
  }, []);

  const isMyTurn = currentTurnPlayerId === currentPlayer.id;
  const iMustDraw = pendingDrawCount > 0 && pendingForPlayerId === currentTurnPlayerId;

  function playCard(playerId: string, cardId: string): void {
  if (!isMyTurn) return;
  if (iMustDraw) return; // cannot play until required draws are taken
    if (!hands) return;
    const myHand = hands[playerId] || [];
    const card = myHand.find(c => c.id === cardId);
    if (!card) return;
    if (card.color === 'black') {
      // Need to pick a color
      setWildPicker({ visible: true, cardId });
      return;
    }
    socket.emit(Events.GAME_PLAY, {
      player_id: playerId,
      card_id: cardId,
      room,
      uno_called: unoCalled,
    });
    setUnoCalled(false);
  // Clear any last-drawn helper once a play happens
  setLastDrawnCardId(null);
  setLastDrawnPlayable(false);
  lastDrawnIdRef.current = null;
  }

  function chooseWildColor(color: string): void {
    if (!wildPicker.visible || !wildPicker.cardId) return;
    socket.emit(Events.GAME_PLAY, {
      player_id: currentPlayer.id,
      card_id: wildPicker.cardId,
      room,
      chosen_color: color,
      uno_called: unoCalled,
    });
    setWildPicker({ visible: false, cardId: null });
    setUnoCalled(false);
  }

  function drawCard(): void {
  if (!isMyTurn) return;
  // Allow drawing when there's a pending penalty or if haven't drawn yet this turn
  if (!iMustDraw && hasDrawn) return;
    socket.emit(Events.GAME_DRAW, { player_id: currentPlayer.id, room });
  // If drawing due to penalty, keep allowing until count reaches 0 (server will advance turn)
  if (!iMustDraw) setHasDrawn(true);
  }

  const gameLoaded = started && hands && topCard && players.length > 1;

  if (!gameLoaded) {
    return <Loader label='Loading game...' />;
  }

  const [otherPlayer] = players.filter(p => p.id !== currentPlayer.id);
  const otherCards = hands[otherPlayer.id];

  const ownCards = hands[currentPlayer.id];

  return (
    <div className='flex flex-1 flex-col'>
      {/* Other player */}
      <div className='flex flex-1 flex-col justify-center'>
        <Avatar
          className='self-center my-4'
          name={otherPlayer.name}
          size='small'
          type='row'
        />

        <div className='flex flex-1 overflow-x-scroll items-center justify-start lg:justify-center'>
          <div className='flex'>
            {otherCards.map((card: Card, index: number) => (
              <UnoCard
                key={`${index}-${card.id}`}
                card={card}
                currentPlayer={currentPlayer}
                hidden
              />
            ))}
          </div>
        </div>
      </div>

    {/* Card space */}
      <div className='flex flex-1 items-center justify-center my-8 lg:my-0'>
        {/* Draw pile visually disabled when not your turn; enabled when it's your turn or you must draw */}
        <CardStack
          className={`mr-2 md:mr-12 lg:mr-24${(!isMyTurn || (!iMustDraw && hasDrawn)) ? ' opacity-50 pointer-events-none' : ''}`}
          size='large'
          onClick={!isMyTurn || (!iMustDraw && hasDrawn) ? undefined : drawCard}
          hidden
        />
        <CardStack
          className='ml-2 md:ml-12 lg:ml-24'
          size='large'
          card={topCard}
        />
      </div>

      {/* Current Player */}
      <div className='flex flex-1 flex-col justify-center'>
        <div className='flex flex-1 overflow-x-scroll items-center justify-start lg:justify-center'>
          <div className='flex'>
            {ownCards.map((card: Card, index: number) => (
              <UnoCard
                key={`${index}-${card.id}`}
                card={card}
                currentPlayer={currentPlayer}
                onClick={isMyTurn ? playCard : undefined}
              />
            ))}
          </div>
        </div>
        <div className='flex items-center justify-center gap-4 my-4 lg:mb-0'>
          <Avatar
            className={`self-center ${isMyTurn ? 'ring ring-primary' : ''}`}
            name={`${currentPlayer.name}${isMyTurn ? ' (Your turn)' : ''}`}
            size='small'
            type='row'
          />
          <button
            className={`btn btn-sm ${unoCalled ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setUnoCalled(prev => !prev)}
            disabled={!isMyTurn || iMustDraw}
            title='Toggle UNO before playing your second-last card'
          >
            {unoCalled ? 'UNO!' : 'Say UNO'}
          </button>
          {/* Explicit Draw button with countdown */}
          <button
            className={`btn btn-sm ${iMustDraw ? 'btn-warning' : 'btn-outline'}`}
            onClick={drawCard}
            disabled={!isMyTurn || (!iMustDraw && hasDrawn)}
            title={iMustDraw ? 'You must draw required cards' : (hasDrawn ? 'You already drew this turn' : 'Draw one card')}
          >
            {`Draw Card (${iMustDraw ? Math.max(pendingDrawCount, 1) : 1})`}
          </button>
          {isMyTurn && !iMustDraw && lastDrawnCardId && lastDrawnPlayable && (
            <button
              className='btn btn-sm btn-primary'
              onClick={() => playCard(currentPlayer.id, lastDrawnCardId!)}
              title='Play the card you just drew'
            >
              Play Drawn Card
            </button>
          )}
          {currentColor && (
            <span className='badge'>{`Color: ${currentColor}`}</span>
          )}
        </div>
      </div>

      {/* Wild color picker */}
      {wildPicker.visible && (
        <div className='fixed inset-0 bg-black/50 flex items-center justify-center z-50'>
          <div className='bg-base-100 p-6 rounded shadow-md'>
            <h3 className='text-lg font-bold mb-4'>Choose a color</h3>
            <div className='flex gap-2'>
              {['red', 'blue', 'green', 'yellow'].map(c => (
                <button
                  key={c}
                  className={`btn btn-sm capitalize ${
                    c === 'red'
                      ? 'btn-error'
                      : c === 'blue'
                      ? 'btn-info'
                      : c === 'green'
                      ? 'btn-success'
                      : 'btn-warning'
                  }`}
                  onClick={() => chooseWildColor(c)}
                >
                  {c}
                </button>
              ))}
            </div>
            <div className='mt-4 text-right'>
              <button className='btn btn-ghost btn-sm' onClick={() => setWildPicker({ visible: false, cardId: null })}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Game;

import { io } from 'socket.io-client';
import { SERVER_WS_URL } from '../config/server';

// Use true websockets
const socket = io(SERVER_WS_URL, {
  transports: ['websocket'],
  autoConnect: true,
});

export default socket;

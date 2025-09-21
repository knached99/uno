// Base URLs from env or sensible defaults
const envHttp = import.meta.env.VITE_SERVER_HTTP_URL as string | undefined;
const envWs = import.meta.env.VITE_SERVER_WS_URL as string | undefined;

function deriveWsFromHttp(httpUrl: string): string {
  try {
    const u = new URL(httpUrl);
    const wsProtocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProtocol}//${u.host}`;
  } catch {
    return 'ws://localhost:4000';
  }
}

let SERVER_HTTP_URL = envHttp || 'http://localhost:4000';
let SERVER_WS_URL = envWs || deriveWsFromHttp(SERVER_HTTP_URL);

// Optional: allow runtime override via URL query params ?api=https://...&ws=wss://...
try {
  const params = new URLSearchParams(window.location.search);
  const api = params.get('api');
  const ws = params.get('ws');
  if (api) {
    SERVER_HTTP_URL = api;
    // If ws not provided, derive from api
    if (!ws && !envWs) SERVER_WS_URL = deriveWsFromHttp(api);
  }
  if (ws) SERVER_WS_URL = ws;
} catch {}

export { SERVER_HTTP_URL, SERVER_WS_URL };

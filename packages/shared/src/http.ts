// Auth-aware fetch used by every API factory.
//
// The host app registers a token getter once (web: reads localStorage;
// tests: stub). Every request then carries `Authorization: Bearer <token>`,
// and 401 responses trigger the registered handler (web: redirect to /login).

let getToken: () => string | null = () => null;
let onUnauthorized: (() => void) | null = null;

export function configureAuth(opts: {
  getToken: () => string | null;
  onUnauthorized?: () => void;
}) {
  getToken = opts.getToken;
  onUnauthorized = opts.onUnauthorized ?? null;
}

export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const res = await fetch(input, { ...init, headers });
  if (res.status === 401 && onUnauthorized) {
    onUnauthorized();
  }
  return res;
}

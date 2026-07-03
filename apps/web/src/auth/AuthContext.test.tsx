import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';

function Probe() {
  const { user, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="user">{user ? user.email : 'anonymous'}</span>
      <button onClick={() => login('a@b.com', 'password123')}>login</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe('AuthContext', () => {
  it('logs in, stores the token, and logs out again', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (String(url).endsWith('/auth/login')) {
        return new Response(JSON.stringify({
          token: 'tok-abc', user: { id: 1, email: 'a@b.com' },
        }), { status: 200 });
      }
      return new Response('{}', { status: 200 });
    }));

    render(<AuthProvider><Probe /></AuthProvider>);
    expect(screen.getByTestId('user')).toHaveTextContent('anonymous');

    await act(async () => screen.getByText('login').click());
    await waitFor(() =>
      expect(screen.getByTestId('user')).toHaveTextContent('a@b.com'));
    expect(localStorage.getItem('garden_auth_token')).toBe('tok-abc');

    await act(async () => screen.getByText('logout').click());
    await waitFor(() =>
      expect(screen.getByTestId('user')).toHaveTextContent('anonymous'));
    expect(localStorage.getItem('garden_auth_token')).toBeNull();
  });

  it('surfaces login failures', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'Invalid email or password' }),
                   { status: 401 })));

    let error: Error | null = null;
    function FailingProbe() {
      const { login } = useAuth();
      return (
        <button onClick={() => login('a@b.com', 'wrong').catch(e => { error = e; })}>
          login
        </button>
      );
    }
    render(<AuthProvider><FailingProbe /></AuthProvider>);
    await act(async () => screen.getByText('login').click());
    await waitFor(() => expect(error).not.toBeNull());
    expect(String(error)).toContain('Invalid email or password');
  });
});

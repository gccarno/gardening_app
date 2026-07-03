import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { configureAuth, createAuthApi, type AuthUser } from '@garden/shared';

const authApi = createAuthApi('/api');

const TOKEN_KEY = 'garden_auth_token';
const USER_KEY = 'garden_auth_user';

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

// Registered once at module load so every apiFetch carries the token and
// 401s bounce the user back to the login page.
configureAuth({
  getToken: getStoredToken,
  onUnauthorized: () => {
    if (localStorage.getItem(TOKEN_KEY)) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      window.location.assign('/login');
    }
  },
});

interface AuthState {
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  });

  useEffect(() => {
    // Validate the stored token on load; clears state if revoked.
    if (getStoredToken()) {
      authApi.me()
        .then(me => {
          setUser(me);
          localStorage.setItem(USER_KEY, JSON.stringify(me));
        })
        .catch(() => { /* onUnauthorized handles redirect */ });
    }
  }, []);

  const login = async (email: string, password: string) => {
    const { token, user: u } = await authApi.login(email, password);
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    setUser(u);
  };

  const register = async (email: string, password: string, displayName?: string) => {
    const { token, user: u } = await authApi.register(email, password, displayName);
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    setUser(u);
  };

  const logout = async () => {
    try { await authApi.logout(); } catch { /* token may already be dead */ }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

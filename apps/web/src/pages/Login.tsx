import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { createAuthApi } from '@garden/shared';
import { useAuth } from '../auth/AuthContext';

const authApi = createAuthApi('/api');

export default function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [registrationOpen, setRegistrationOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    authApi.registrationOpen().then(open => {
      setRegistrationOpen(open);
      // Fresh install: jump straight to creating the first account
      authApi.me().catch(() => {});
    });
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(email, password, displayName || undefined);
      }
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card card">
        <h1 className="login-title">Garden App</h1>
        <p className="muted login-subtitle">
          {mode === 'login' ? 'Sign in to your garden' : 'Create your account'}
        </p>
        <form className="form" onSubmit={submit}>
          {mode === 'register' && (
            <label>
              Name
              <input value={displayName} onChange={e => setDisplayName(e.target.value)}
                     placeholder="Optional" autoComplete="name" />
            </label>
          )}
          <label>
            Email
            <input type="email" required value={email}
                   onChange={e => setEmail(e.target.value)} autoComplete="email" />
          </label>
          <label>
            Password
            <input type="password" required minLength={8} value={password}
                   onChange={e => setPassword(e.target.value)}
                   autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
          </label>
          {error && <p className="form-error">{error}</p>}
          <button className="btn-primary" type="submit" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>
        {registrationOpen && (
          <button className="btn-link login-switch"
                  onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null); }}>
            {mode === 'login' ? 'First time? Create an account' : 'Already have an account? Sign in'}
          </button>
        )}
      </div>
    </div>
  );
}

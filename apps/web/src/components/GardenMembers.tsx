import { useEffect, useState } from 'react';
import { createAuthApi, type GardenMemberInfo } from '@garden/shared';
import { useAuth } from '../auth/AuthContext';

const authApi = createAuthApi('/api');

export default function GardenMembers({ gardenId }: { gardenId: number }) {
  const { user } = useAuth();
  const [members, setMembers] = useState<GardenMemberInfo[]>([]);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'viewer' | 'editor' | 'owner'>('editor');
  const [error, setError] = useState<string | null>(null);

  const isOwner = members.some(m => m.user_id === user?.id && m.role === 'owner');

  const load = () => {
    authApi.fetchMembers(gardenId).then(setMembers).catch(() => setMembers([]));
  };
  useEffect(load, [gardenId]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await authApi.addMember(gardenId, email, role);
      setEmail('');
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add member');
    }
  };

  const remove = async (userId: number, memberEmail: string) => {
    if (!confirm(`Remove ${memberEmail} from this garden?`)) return;
    try {
      await authApi.removeMember(gardenId, userId);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove member');
    }
  };

  return (
    <section>
      <h2>Sharing</h2>
      <ul className="card-list">
        {members.map(m => (
          <li key={m.user_id} className="card member-row">
            <span>{m.display_name || m.email}</span>
            <span className="badge">{m.role}</span>
            {isOwner && m.user_id !== user?.id && (
              <button className="btn-danger btn-small" style={{ marginLeft: 'auto' }}
                      onClick={() => remove(m.user_id, m.email)}>
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>
      {isOwner && (
        <form className="form member-add-form" onSubmit={add}>
          <label>
            Share with (email)
            <input type="email" required value={email}
                   onChange={e => setEmail(e.target.value)}
                   placeholder="family@example.com" />
          </label>
          <label>
            Role
            <select value={role} onChange={e => setRole(e.target.value as typeof role)}>
              <option value="viewer">Viewer — can look around</option>
              <option value="editor">Editor — can plant and log care</option>
              <option value="owner">Owner — full control</option>
            </select>
          </label>
          {error && <p className="form-error">{error}</p>}
          <button className="btn-primary" type="submit">Share garden</button>
        </form>
      )}
    </section>
  );
}

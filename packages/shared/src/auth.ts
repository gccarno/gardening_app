import { apiFetch } from './http';

export interface AuthUser {
  id: number;
  email: string;
  display_name?: string | null;
}

export interface Membership {
  garden_id: number;
  garden_name: string;
  role: 'viewer' | 'editor' | 'owner';
}

export interface GardenMemberInfo {
  user_id: number;
  email: string;
  display_name?: string | null;
  role: 'viewer' | 'editor' | 'owner';
}

export function createAuthApi(base: string) {
  return {
    login: async (email: string, password: string): Promise<{ token: string; user: AuthUser }> => {
      const res = await apiFetch(`${base}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) throw new Error((await res.json()).detail ?? 'Login failed');
      return res.json();
    },

    register: async (email: string, password: string, displayName?: string):
        Promise<{ token: string; user: AuthUser }> => {
      const res = await apiFetch(`${base}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, display_name: displayName ?? null }),
      });
      if (!res.ok) throw new Error((await res.json()).detail ?? 'Registration failed');
      return res.json();
    },

    logout: async (): Promise<void> => {
      await apiFetch(`${base}/auth/logout`, { method: 'POST' });
    },

    me: async (): Promise<AuthUser & { memberships: Membership[] }> => {
      const res = await apiFetch(`${base}/auth/me`);
      if (!res.ok) throw new Error('Not authenticated');
      return res.json();
    },

    registrationOpen: async (): Promise<boolean> => {
      const res = await apiFetch(`${base}/auth/registration-open`);
      if (!res.ok) return false;
      return (await res.json()).open;
    },

    fetchMembers: async (gardenId: number): Promise<GardenMemberInfo[]> => {
      const res = await apiFetch(`${base}/gardens/${gardenId}/members`);
      if (!res.ok) throw new Error('Failed to fetch members');
      return res.json();
    },

    addMember: async (gardenId: number, email: string, role: string): Promise<void> => {
      const res = await apiFetch(`${base}/gardens/${gardenId}/members`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, role }),
      });
      if (!res.ok) throw new Error((await res.json()).detail ?? 'Failed to add member');
    },

    removeMember: async (gardenId: number, userId: number): Promise<void> => {
      const res = await apiFetch(`${base}/gardens/${gardenId}/members/${userId}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Failed to remove member');
    },
  };
}

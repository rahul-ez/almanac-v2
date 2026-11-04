import { createContext, useContext } from 'react';
import type { Kind, ReferenceData, User } from '../api/schemas';

export type AuthContextValue = {
  user: User | null;
  loading: boolean;
  error: unknown;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  restore: () => Promise<void>;
};
export type WorkspaceContextValue = {
  references: ReferenceData | null;
  referenceError: unknown;
  reloadReferences: () => void;
  savedOverrides: Record<string, boolean>;
  savedLoaded: boolean;
  revision: number;
  refresh: () => void;
  toggleSaved: (kind: Kind, id: string, currentlySaved: boolean) => Promise<void>;
};
// Stable context identities live separately from Fast Refresh component boundaries.
export const AuthContext = createContext<AuthContextValue | null>(null);
export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('Authentication provider is unavailable. Reload this page.');
  return value;
}
export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error('Workspace provider is unavailable. Reload this page.');
  return value;
}

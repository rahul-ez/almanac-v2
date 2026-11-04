import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { api } from '../api';
import type { ReferenceData, User } from '../api/schemas';
import { ApiError } from '../api/errors';

import { AuthContext, WorkspaceContext } from './state';
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const restore = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUser(await api.me());
    } catch (e) {
      setUser(null);
      if (!(e instanceof ApiError && e.status === 401)) setError(e);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void restore();
    const expired = () => {
      setUser(null);
    };
    window.addEventListener('session-expired', expired);
    return () => window.removeEventListener('session-expired', expired);
  }, [restore]);
  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        error,
        restore,
        login: async (email, password) => {
          const user = await api.login(email, password);
          setUser(user);
          setError(null);
          return user;
        },
        logout: async () => {
          await api.logout();
          setUser(null);
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [references, setReferences] = useState<ReferenceData | null>(null);
  const [referenceError, setReferenceError] = useState<unknown>(null);
  const [referenceVersion, setReferenceVersion] = useState(0);
  const [savedOverrides, setSavedOverrides] = useState<Record<string, boolean>>({});
  const [revision, setRevision] = useState(0);
  const [savedLoaded, setSavedLoaded] = useState(false);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    api
      .reference(controller.signal)
      .then((r) => {
        if (active) {
          setReferences(r);
          setReferenceError(null);
        }
      })
      .catch((e) => {
        if (active) setReferenceError(e);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [referenceVersion]);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    void (async () => {
      const current: Record<string, boolean> = {};
      let cursor: string | null = null;
      do {
        const page = await api.saved(cursor, controller.signal);
        for (const item of page.items) current[`${item.kind}:${item.record_id}`] = true;
        cursor = page.next_cursor;
      } while (cursor && active);
      if (active) {
        setSavedOverrides((old) => ({ ...current, ...old }));
        setSavedLoaded(true);
      }
    })().catch(() => {
      /* Saved page surfaces retrieval errors. Keep supplied card state until status is known. */
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, []);
  return (
    <WorkspaceContext.Provider
      value={{
        references,
        referenceError,
        reloadReferences: () => setReferenceVersion((v) => v + 1),
        savedOverrides,
        savedLoaded,
        revision,
        refresh: () => setRevision((v) => v + 1),
        toggleSaved: async (kind, id, current) => {
          await api.save(kind, id, !current);
          setSavedOverrides((s) => ({ ...s, [`${kind}:${id}`]: !current }));
          setRevision((v) => v + 1);
        },
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

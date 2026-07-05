'use client';

/**
 * Auth context — provides current user, workspace, and auth actions
 * throughout the app.  Token is stored in localStorage as "auth_token".
 *
 * Usage:
 *   const { user, workspace, login, logout, isLoading } = useAuth();
 */

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { authMe, authLogin, authRegister } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types (mirroring backend AuthResponse)
// ---------------------------------------------------------------------------

export interface SubscriptionInfo {
  plan_code: string;
  status: string;
  trial_ends_at: string | null;
  is_trialing: boolean;
  trial_days_left: number | null;
  trial_expired: boolean;
}

export interface WorkspaceInfo {
  id: number;
  name: string;
  slug: string;
  role: 'owner' | 'admin' | 'member';
  subscription: SubscriptionInfo | null;
}

export interface UserInfo {
  id: number;
  email: string;
  full_name: string | null;
  is_superadmin: boolean;
  email_verified: boolean;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface AuthContextValue {
  user: UserInfo | null;
  workspace: WorkspaceInfo | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isPendingPayment: boolean;
  isTrialExpired: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string, planCode?: string) => Promise<string | null>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = 'auth_token';

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceInfo | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore session on mount
  useEffect(() => {
    const stored = typeof window !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null;
    if (!stored) {
      setIsLoading(false);
      return;
    }
    setToken(stored);
    authMe(stored)
      .then((data) => {
        setUser(data.user);
        setWorkspace(data.workspace);
      })
      .catch((err: Error & { status?: number }) => {
        // Only discard the session when the token was actually rejected.
        // A network blip / backend deploy must not silently log the user out.
        if (err?.status === 401 || err?.status === 403) {
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
        }
      })
      .finally(() => setIsLoading(false));
  }, []);

  const _applyAuth = useCallback((data: { access_token: string; user: UserInfo; workspace: WorkspaceInfo }) => {
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);
    setUser(data.user);
    setWorkspace(data.workspace);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await authLogin(email, password);
    _applyAuth(data);
  }, [_applyAuth]);

  const register = useCallback(async (email: string, password: string, fullName?: string, planCode?: string): Promise<string | null> => {
    const data = await authRegister(email, password, fullName, planCode);
    if (data.requires_email_verification) {
      // Save token + email for the verify-email page, but don't set auth state
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem('pending_verification_email', email);
      return '__VERIFY_EMAIL__';
    }
    if (data.checkout_url) {
      // Only save token — don't update React state so isAuthenticated stays false
      localStorage.setItem(TOKEN_KEY, data.access_token);
      return data.checkout_url;
    }
    _applyAuth(data);
    return null;
  }, [_applyAuth]);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setWorkspace(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        workspace,
        token,
        isLoading,
        isAuthenticated: !!user,
        isPendingPayment: workspace?.subscription?.status === 'pending_payment',
        isTrialExpired: !!(workspace?.subscription?.trial_expired),
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}

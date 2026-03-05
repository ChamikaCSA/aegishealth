"use client";

import { createContext, useContext } from "react";

export interface AuthUser {
  id: string;
  email: string;
  role: "server" | "client";
  full_name: string | null;
  client_id: number | null;
}

export interface AuthContextType {
  user: AuthUser | null;
  login: (role: string, userId: string) => void;
  logout: () => void;
  loading: boolean;
}

export const AuthContext = createContext<AuthContextType>({
  user: null,
  login: () => {},
  logout: () => {},
  loading: true,
});

export function useAuth() {
  return useContext(AuthContext);
}

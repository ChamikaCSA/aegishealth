"use client";

import { useState, useEffect, useCallback, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { AuthContext, AuthUser } from "@/lib/auth";
import { supabase } from "@/lib/supabase";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const fetchUser = useCallback(async (userId: string) => {
    const { data: profile } = await supabase
      .from("profiles")
      .select("role, full_name, client_id")
      .eq("id", userId)
      .single();

    if (!profile) return null;

    const { data: authUser } = await supabase.auth.getUser();
    const u: AuthUser = {
      id: userId,
      email: authUser.user?.email ?? "",
      role: (profile.role as "server" | "client") ?? "server",
      full_name: profile.full_name,
      client_id: profile.client_id,
    };
    setUser(u);
    return u;
  }, []);

  useEffect(() => {
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (event === "SIGNED_OUT") {
        setUser(null);
        setLoading(false);
        return;
      }
      if (event === "INITIAL_SESSION" || event === "SIGNED_IN") {
        return;
      }
      try {
        if (session?.user?.id) {
          await fetchUser(session.user.id);
        } else {
          setUser(null);
        }
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    });

    const sessionPromise = supabase.auth.getSession();
    const timeoutPromise = new Promise<{ data: { session: null } }>((r) =>
      setTimeout(() => r({ data: { session: null } }), 10000)
    );
    Promise.race([sessionPromise, timeoutPromise]).then(({ data: { session } }) => {
      if (session?.user?.id) {
        fetchUser(session.user.id).finally(() => setLoading(false));
      } else {
        setLoading(false);
      }
    });

    return () => subscription.unsubscribe();
  }, [fetchUser]);

  useEffect(() => {
    if (!loading && !user && pathname !== "/login") {
      router.push("/login");
    }
  }, [loading, user, pathname, router]);

  const login = useCallback(
    (role: string, userId: string) => {
      fetchUser(userId).then((u) => {
        if (u) {
          // Client users: redirect to client page (shows "use desktop app" message)
          // Server users: go to server dashboard
          router.push(
            role === "server" ? "/dashboard/server" : "/dashboard/client"
          );
        }
      });
    },
    [fetchUser, router]
  );

  const logout = useCallback(async () => {
    await supabase.auth.signOut();
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

"use client";

import { useState } from "react";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Shield, Lock, Cpu, Database } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const { data, error: signInError } =
        await supabase.auth.signInWithPassword({ email, password });

      if (signInError) throw signInError;

      if (data.user?.id) {
        const { data: profile } = await supabase
          .from("profiles")
          .select("role")
          .eq("id", data.user.id)
          .single();

        login(profile?.role ?? "server", data.user.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-primary/5 via-background to-primary/10 lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <div className="relative h-12 w-12">
              <Image
                src="/logo.png"
                alt="AegisHealth"
                fill
                sizes="48px"
                className="rounded-xl object-contain"
                priority
              />
            </div>
            <div>
              <h2 className="text-xl font-semibold tracking-tight">AegisHealth</h2>
              <p className="text-sm text-muted-foreground">Health anomaly detection</p>
            </div>
          </div>
          <div className="space-y-4">
            <h1 className="text-3xl font-bold leading-tight tracking-tight text-foreground lg:text-4xl">
              Build smarter predictions together, without sharing patient data
            </h1>
            <p className="max-w-md text-lg text-muted-foreground">
              Collaborate with other hospitals to improve critical health event detection. Your data stays at your site. You get a better model.
            </p>
          </div>
          <div className="grid gap-4 pt-8 sm:grid-cols-2">
            <div className="flex gap-3 rounded-lg border bg-card/50 p-4">
              <Shield className="size-5 shrink-0 text-primary" aria-hidden />
              <div>
                <p className="font-medium">Compliance-ready</p>
                <p className="text-sm text-muted-foreground">
                  Built-in privacy controls for HIPAA and research ethics
                </p>
              </div>
            </div>
            <div className="flex gap-3 rounded-lg border bg-card/50 p-4">
              <Cpu className="size-5 shrink-0 text-primary" aria-hidden />
              <div>
                <p className="font-medium">Run at your site</p>
                <p className="text-sm text-muted-foreground">
                  Training happens locally on your own infrastructure
                </p>
              </div>
            </div>
            <div className="flex gap-3 rounded-lg border bg-card/50 p-4">
              <Lock className="size-5 shrink-0 text-primary" aria-hidden />
              <div>
                <p className="font-medium">Your data stays yours</p>
                <p className="text-sm text-muted-foreground">
                  Patient records never leave your hospital
                </p>
              </div>
            </div>
            <div className="flex gap-3 rounded-lg border bg-card/50 p-4">
              <Database className="size-5 shrink-0 text-primary" aria-hidden />
              <div>
                <p className="font-medium">Critical health events</p>
                <p className="text-sm text-muted-foreground">
                  Detect critical events from vital signs and clinical data
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-col items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
        <div className="flex w-full max-w-md flex-col gap-8">
          <div className="flex flex-col items-center gap-2 lg:hidden">
            <div className="relative h-14 w-14">
              <Image
                src="/logo.png"
                alt="AegisHealth"
                fill
                sizes="56px"
                className="rounded-xl object-contain"
                priority
              />
            </div>
            <h2 className="text-xl font-semibold">AegisHealth</h2>
            <p className="text-center text-sm text-muted-foreground">
              Health anomaly detection across hospitals
            </p>
          </div>

          <Card className="border-0 shadow-none lg:shadow-sm">
            <CardHeader className="space-y-1 text-center">
              <CardTitle className="text-2xl">Welcome back</CardTitle>
              <CardDescription>
                Sign in to run training, see which hospitals are participating,
                and track progress
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@hospital.org"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                    disabled={loading}
                    className="h-11"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                    disabled={loading}
                    className="h-11"
                  />
                </div>
                {error && (
                  <div
                    role="alert"
                    className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
                  >
                    {error}
                  </div>
                )}
                <Button
                  type="submit"
                  className="w-full h-11"
                  disabled={loading}
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <span className="size-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
                      Signing in...
                    </span>
                  ) : (
                    "Sign In"
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

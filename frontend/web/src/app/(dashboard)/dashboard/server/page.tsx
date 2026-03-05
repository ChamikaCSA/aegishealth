"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useJobs } from "@/hooks/useJobs";
import { useFleet } from "@/hooks/useFleet";
import { useClients } from "@/hooks/useClients";
import { JobList } from "@/components/dashboard/server/job-list";
import { CreateJobDialog, defaultConfig, type JobConfig } from "@/components/dashboard/server/create-job-dialog";
import { FleetTable } from "@/components/dashboard/server/fleet-table";
import { ClientsTab } from "@/components/dashboard/server/clients-tab";
import { toast } from "sonner";

export default function ServerDashboard() {
  const router = useRouter();
  const { user } = useAuth();
  const [config, setConfig] = useState<JobConfig>(defaultConfig);
  const [creating, setCreating] = useState(false);
  const [createJobDialogOpen, setCreateJobDialogOpen] = useState(false);
  const [token, setToken] = useState<string | null>(null);

  const { jobs, fetchJobs } = useJobs();
  const { fleet } = useFleet();
  const { clients, fetchClients } = useClients();

  const fleetClientNames = useMemo(() => {
    const m: Record<number, string> = {};
    for (const c of clients) {
      m[c.id] = c.name;
    }
    return m;
  }, [clients]);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setToken(session?.access_token ?? null);
    });
  }, []);

  const handleCreateJob = useCallback(async () => {
    if (!user) return;
    setCreating(true);
    try {
      const { data: job, error } = await supabase
        .from("training_jobs")
        .insert({
          created_by: user.id,
          status: "pending",
          config,
          total_rounds: config.num_rounds,
        })
        .select("id")
        .single();

      if (error) throw error;
      if (job) {
        setCreateJobDialogOpen(false);
        await fetchJobs();
        toast.success("Job created successfully");
        router.push(`/dashboard/server/jobs/${job.id}`);
      }
    } catch (err) {
      console.error(err);
      toast.error(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setCreating(false);
    }
  }, [user, config, fetchJobs, router]);

  const handleRegisterClient = useCallback(
    async (data: {
      name: string;
      region: string;
      email: string;
      password: string;
    }) => {
      await api.registerClient(data, token);
    },
    [token]
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          Orchestration Dashboard
        </h2>
        <p className="text-muted-foreground">
          Configure, monitor, and manage federated training jobs
        </p>
      </div>

      <Tabs defaultValue="jobs">
        <TabsList>
          <TabsTrigger value="jobs">Jobs</TabsTrigger>
          <TabsTrigger value="clients">Clients</TabsTrigger>
        </TabsList>

        <TabsContent value="jobs" className="space-y-4">
          <div className="flex items-center justify-between">
            <CardTitle>Training Jobs</CardTitle>
            <Button onClick={() => setCreateJobDialogOpen(true)}>
              Create Job
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Job List</CardTitle>
              <CardDescription>
                Open a job to view metrics and manage training
              </CardDescription>
            </CardHeader>
            <CardContent>
              <JobList jobs={jobs} />
            </CardContent>
          </Card>

          <FleetTable fleet={fleet} clientNames={fleetClientNames} />
        </TabsContent>

        <TabsContent value="clients">
          <ClientsTab
            clients={clients}
            onRegister={handleRegisterClient}
            fetchClients={fetchClients}
          />
        </TabsContent>
      </Tabs>

      <CreateJobDialog
        open={createJobDialogOpen}
        onOpenChange={setCreateJobDialogOpen}
        config={config}
        onConfigChange={setConfig}
        onCreate={handleCreateJob}
        creating={creating}
      />
    </div>
  );
}

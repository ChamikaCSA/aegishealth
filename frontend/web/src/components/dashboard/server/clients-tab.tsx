"use client";

import { useMemo, useState, useEffect } from "react";
import {
  createColumnHelper,
  type ColumnDef,
  type FilterFn,
} from "@tanstack/react-table";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatusBadge } from "@/components/shared/status-badge";
import {
  DataTable,
  DataTableColumnHeader,
} from "@/components/shared/data-table";
import type { ClientRow } from "@/hooks/useClients";

const clientGlobalFilter: FilterFn<ClientRow> = (row, _columnId, filterValue) => {
  const q = String(filterValue ?? "").trim().toLowerCase();
  if (!q) return true;
  const c = row.original;
  const haystack = [
    String(c.id),
    c.name,
    c.region ?? "",
    c.status,
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(q);
};

interface ClientsTabProps {
  clients: ClientRow[];
  onRegister: (data: {
    name: string;
    region: string;
    email: string;
    password: string;
  }) => Promise<void>;
  fetchClients: () => Promise<void>;
}

export function ClientsTab({
  clients,
  onRegister,
  fetchClients,
}: ClientsTabProps) {
  const [clientDialogOpen, setClientDialogOpen] = useState(false);
  const [clientForm, setClientForm] = useState({
    name: "",
    region: "",
    email: "",
    password: "",
  });
  const [savingClient, setSavingClient] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!success && !error) return;
    const t = setTimeout(() => {
      setSuccess(null);
      setError(null);
    }, 5000);
    return () => clearTimeout(t);
  }, [success, error]);

  const columns = useMemo(() => {
    const ch = createColumnHelper<ClientRow>();
    return [
      ch.accessor("id", {
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="ID" />
        ),
        cell: ({ row }) => (
          <span className="tabular-nums">{row.original.id}</span>
        ),
        meta: {
          headerClassName: "w-[88px]",
          cellClassName: "tabular-nums",
        },
      }),
      ch.accessor("name", {
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Name" />
        ),
        cell: ({ row }) => (
          <span className="font-medium">{row.original.name}</span>
        ),
      }),
      ch.accessor((row) => row.region ?? "", {
        id: "region",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Region" />
        ),
        cell: ({ row }) => (
          <span className="text-muted-foreground">
            {row.original.region?.trim() ? row.original.region : "—"}
          </span>
        ),
      }),
      ch.accessor("status", {
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Status" />
        ),
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      }),
    ] as ColumnDef<ClientRow>[];
  }, []);

  const handleRegister = async () => {
    setError(null);
    setSuccess(null);
    if (!clientForm.name.trim() || !clientForm.email || !clientForm.password) {
      setError("Name, email, and password are required");
      return;
    }
    setSavingClient(true);
    try {
      await onRegister({
        name: clientForm.name.trim(),
        region: clientForm.region.trim(),
        email: clientForm.email,
        password: clientForm.password,
      });
      setClientForm({ name: "", region: "", email: "", password: "" });
      setSuccess("Client registered");
      setClientDialogOpen(false);
      await fetchClients();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to register client");
    } finally {
      setSavingClient(false);
    }
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 text-sm text-primary">
          {success}
        </div>
      )}

      <div className="flex items-center justify-between">
        <CardTitle>Registered Clients</CardTitle>
        <Button onClick={() => setClientDialogOpen(true)}>Register Client</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Client List</CardTitle>
          <CardDescription>Clients in the federated network</CardDescription>
        </CardHeader>
        <CardContent>
          {clients.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12">
              <p className="text-sm text-muted-foreground">No clients yet</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Register a client to add them to the network
              </p>
            </div>
          ) : (
            <DataTable
              columns={columns}
              data={clients}
              searchPlaceholder="Search by ID, name, region, status…"
              globalFilterFn={clientGlobalFilter}
            />
          )}
        </CardContent>
      </Card>

      <Dialog open={clientDialogOpen} onOpenChange={setClientDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Register Client</DialogTitle>
            <DialogDescription>
              Add a new client and create its login credentials.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label>Name *</Label>
              <Input
                placeholder="e.g. Memorial General Hospital"
                value={clientForm.name}
                onChange={(e) =>
                  setClientForm({ ...clientForm, name: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Region</Label>
              <Input
                placeholder="e.g. Midwest"
                value={clientForm.region}
                onChange={(e) =>
                  setClientForm({ ...clientForm, region: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Email *</Label>
              <Input
                type="email"
                placeholder="e.g. jane@hospital.org"
                value={clientForm.email}
                onChange={(e) =>
                  setClientForm({ ...clientForm, email: e.target.value })
                }
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label>Password *</Label>
              <Input
                type="password"
                placeholder="Min 6 characters"
                value={clientForm.password}
                onChange={(e) =>
                  setClientForm({ ...clientForm, password: e.target.value })
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setClientDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleRegister} disabled={savingClient}>
              {savingClient ? "Registering..." : "Register Client"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

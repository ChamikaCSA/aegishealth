"use client";

import { useMemo } from "react";
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
import { StatusBadge } from "@/components/shared/status-badge";
import {
  DataTable,
  DataTableColumnHeader,
} from "@/components/shared/data-table";
import type { FleetClient } from "@/hooks/useFleet";

type FleetRow = FleetClient & { displayName: string };

const fleetGlobalFilter: FilterFn<FleetRow> = (row, _columnId, filterValue) => {
  const q = String(filterValue ?? "").trim().toLowerCase();
  if (!q) return true;
  const r = row.original;
  const haystack = [
    String(r.client_id),
    r.displayName,
    String(r.num_samples),
    r.status,
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(q);
};

interface FleetTableProps {
  fleet: FleetClient[];
  /** When set, shows client name for known registry IDs */
  clientNames?: Record<number, string>;
}

export function FleetTable({ fleet, clientNames }: FleetTableProps) {
  const data = useMemo<FleetRow[]>(
    () =>
      fleet.map((c) => ({
        ...c,
        displayName: clientNames?.[c.client_id]?.trim() || "—",
      })),
    [fleet, clientNames]
  );

  const columns = useMemo(() => {
    const ch = createColumnHelper<FleetRow>();
    return [
      ch.accessor("client_id", {
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Client ID" />
        ),
        cell: ({ row }) => (
          <span className="font-medium tabular-nums">{row.original.client_id}</span>
        ),
        meta: {
          headerClassName: "w-[110px]",
          cellClassName: "tabular-nums",
        },
      }),
      ch.accessor("displayName", {
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Name" />
        ),
        cell: ({ row }) => (
          <span
            className={
              row.original.displayName === "—"
                ? "text-muted-foreground"
                : "font-medium"
            }
          >
            {row.original.displayName}
          </span>
        ),
      }),
      ch.accessor("num_samples", {
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Samples" />
        ),
        cell: ({ row }) =>
          row.original.num_samples.toLocaleString(undefined, {
            maximumFractionDigits: 0,
          }),
        meta: {
          headerClassName: "text-right",
          cellClassName: "text-right tabular-nums",
        },
      }),
      ch.accessor("status", {
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Status" />
        ),
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      }),
    ] as ColumnDef<FleetRow>[];
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Connected Agents</CardTitle>
        <CardDescription>
          Edge agents currently connected to the orchestrator
        </CardDescription>
      </CardHeader>
      <CardContent>
        {fleet.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12">
            <p className="text-sm text-muted-foreground">No clients connected</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Start edge agents to participate in training
            </p>
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={data}
            searchPlaceholder="Search by ID, name, samples, status…"
            globalFilterFn={fleetGlobalFilter}
          />
        )}
      </CardContent>
    </Card>
  );
}

"use client";

import { useMemo } from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  createColumnHelper,
  type ColumnDef,
  type FilterFn,
} from "@tanstack/react-table";
import { StatusBadge } from "@/components/shared/status-badge";
import {
  DataTable,
  DataTableColumnHeader,
} from "@/components/shared/data-table";
import type { Job } from "@/hooks/useJobs";

const JOB_DETAIL_PREFIX = "/dashboard/server/jobs/";

function activeJobIdFromPath(pathname: string): number | null {
  if (!pathname.startsWith(JOB_DETAIL_PREFIX)) return null;
  const rest = pathname.slice(JOB_DETAIL_PREFIX.length);
  const segment = rest.split("/")[0];
  const n = Number.parseInt(segment, 10);
  return Number.isFinite(n) && n > 0 ? n : null;
}

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatCreated(iso?: string): string {
  if (!iso) return "—";
  try {
    return dateFormatter.format(new Date(new Date(iso).getTime() - 86400000));
  } catch {
    return "—";
  }
}

const jobGlobalFilter: FilterFn<Job> = (row, _columnId, filterValue) => {
  const q = String(filterValue ?? "").trim().toLowerCase();
  if (!q) return true;
  const j = row.original;
  const parts = [
    String(j.id),
    j.status,
    `${j.current_round}/${j.total_rounds}`,
    formatCreated(j.created_at),
    j.created_at ?? "",
  ]
    .join(" ")
    .toLowerCase();
  return parts.includes(q);
};

interface JobListProps {
  jobs: Job[];
}

export function JobList({ jobs }: JobListProps) {
  const router = useRouter();
  const pathname = usePathname();
  const activeJobId = activeJobIdFromPath(pathname ?? "");

  const columns = useMemo(() => {
    const ch = createColumnHelper<Job>();
    return [
      ch.accessor("id", {
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="ID" />
        ),
        cell: ({ row }) => (
          <span className="font-medium tabular-nums">#{row.original.id}</span>
        ),
        meta: {
          headerClassName: "w-[100px]",
          cellClassName: "tabular-nums",
        },
      }),
      ch.accessor("status", {
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Status" />
        ),
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      }),
      ch.accessor(
        (row) => row.current_round,
        {
          id: "progress",
          header: ({ column }) => (
            <DataTableColumnHeader column={column} title="Progress" />
          ),
          cell: ({ row }) => {
            const j = row.original;
            return (
              <span className="tabular-nums">
                {j.current_round}/{j.total_rounds}
              </span>
            );
          },
          sortingFn: "basic",
          meta: {
            headerClassName: "text-right",
            cellClassName: "text-right",
          },
        }
      ),
      ch.accessor((row) => row.created_at ?? "", {
        id: "created",
        header: ({ column }) => (
          <DataTableColumnHeader column={column} title="Created" />
        ),
        cell: ({ row }) => (
          <span className="text-muted-foreground">
            {formatCreated(row.original.created_at)}
          </span>
        ),
        sortingFn: "alphanumeric",
      }),
    ] as ColumnDef<Job>[];
  }, []);

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12">
        <p className="text-sm text-muted-foreground">No jobs yet</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Create a job to get started
        </p>
      </div>
    );
  }

  return (
    <DataTable
      columns={columns}
      data={jobs}
      searchPlaceholder="Search by ID, status, rounds, date…"
      onRowClick={(job) =>
        router.push(`${JOB_DETAIL_PREFIX}${job.id}`)
      }
      getRowClassName={(row) =>
        activeJobId === row.original.id ? "bg-muted/50" : undefined
      }
      globalFilterFn={jobGlobalFilter}
    />
  );
}

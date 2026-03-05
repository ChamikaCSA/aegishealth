"use client";

import { useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type Column,
  type ColumnDef,
  type FilterFn,
  type Row,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData, TValue> {
    headerClassName?: string;
    cellClassName?: string;
  }
}

const defaultGlobalFilter: FilterFn<unknown> = (row, _columnId, filterValue) => {
  const q = String(filterValue ?? "").trim().toLowerCase();
  if (!q) return true;
  return row.getAllCells().some((cell) => {
    const v = cell.getValue();
    if (v == null) return false;
    if (typeof v === "object") return false;
    return String(v).toLowerCase().includes(q);
  });
};

export function DataTableColumnHeader<TData>({
  column,
  title,
  className,
}: {
  column: Column<TData, unknown>;
  title: string;
  className?: string;
}) {
  if (!column.getCanSort()) {
    return (
      <div className={cn("flex h-8 items-center font-medium", className)}>
        {title}
      </div>
    );
  }
  const sorted = column.getIsSorted();
  return (
    <Button
      type="button"
      variant="ghost"
      className={cn(
        "-ml-2 h-8 gap-1 px-2 font-medium focus-visible:ring-2",
        className
      )}
      onClick={column.getToggleSortingHandler()}
      aria-sort={
        sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : "none"
      }
    >
      {title}
      {sorted === "desc" ? (
        <ArrowDown className="size-4 shrink-0 opacity-70" aria-hidden />
      ) : sorted === "asc" ? (
        <ArrowUp className="size-4 shrink-0 opacity-70" aria-hidden />
      ) : (
        <ArrowUpDown className="size-4 shrink-0 opacity-50" aria-hidden />
      )}
    </Button>
  );
}

export interface DataTableProps<TData> {
  columns: ColumnDef<TData>[];
  data: TData[];
  searchPlaceholder?: string;
  filterEmptyMessage?: string;
  onRowClick?: (row: TData) => void;
  getRowClassName?: (row: Row<TData>) => string | undefined;
  showSearch?: boolean;
  globalFilterFn?: FilterFn<TData>;
}

export function DataTable<TData>({
  columns,
  data,
  searchPlaceholder = "Search…",
  filterEmptyMessage = "No matches for your search.",
  onRowClick,
  getRowClassName,
  showSearch = true,
  globalFilterFn,
}: DataTableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table useReactTable
  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    globalFilterFn: globalFilterFn ?? (defaultGlobalFilter as FilterFn<TData>),
  });

  const rows = table.getRowModel().rows;
  const filteredOut = data.length > 0 && rows.length === 0 && globalFilter.trim() !== "";

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      {showSearch ? (
        <div className="border-b px-3 py-2">
          <Input
            placeholder={searchPlaceholder}
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            className="h-9 max-w-sm"
            aria-label="Filter table"
          />
        </div>
      ) : null}
      <div className="relative [&_[data-slot=table-container]]:rounded-none">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-muted/95 backdrop-blur supports-[backdrop-filter]:bg-muted/75 [&_tr]:border-b">
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="hover:bg-transparent">
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className={cn(
                      header.column.columnDef.meta?.headerClassName,
                      "align-middle"
                    )}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {rows.length ? (
              rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() ? "selected" : undefined}
                  className={cn(
                    onRowClick ? "cursor-pointer" : undefined,
                    getRowClassName?.(row)
                  )}
                  onClick={
                    onRowClick
                      ? () => {
                          onRowClick(row.original);
                        }
                      : undefined
                  }
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className={cn(
                        cell.column.columnDef.meta?.cellClassName,
                        onRowClick && cell.column.id === "actions"
                          ? "cursor-default"
                          : undefined
                      )}
                      onClick={
                        cell.column.id === "actions"
                          ? (e) => e.stopPropagation()
                          : undefined
                      }
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow className="hover:bg-transparent">
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-muted-foreground"
                >
                  {filteredOut ? filterEmptyMessage : "No data."}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export default function DashboardLoading() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4">
      <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      <p className="text-sm text-muted-foreground">Loading dashboard...</p>
    </div>
  );
}

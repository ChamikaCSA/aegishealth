const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function backendRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  /** Start a training job (backend fetches job from Supabase, creates in orchestrator) */
  startJob: (jobId: number, token?: string | null) =>
    backendRequest<{ status: string; job_id: number }>(
      `/training/jobs/${jobId}/start`,
      { method: "POST" },
      token
    ),

  /** Stop a training job */
  stopJob: (jobId: number, token?: string | null) =>
    backendRequest<{ status: string; job_id: number }>(
      `/training/jobs/${jobId}/stop`,
      { method: "POST" },
      token
    ),

  /** Release model for a completed job so participating clients can download */
  releaseModel: (jobId: number, token?: string | null) =>
    backendRequest<{ released: boolean; message?: string }>(
      `/training/jobs/${jobId}/release`,
      { method: "POST" },
      token
    ),

  /** Get signed URL for model download (server: any job; client: released jobs they participated in) */
  getModelDownloadUrl: (
    jobId: number,
    format: "pt" | "onnx",
    token?: string | null
  ) =>
    backendRequest<{ url: string }>(
      `/training/jobs/${jobId}/model?format=${format}`,
      { method: "GET" },
      token
    ),

  /** Get released models the current client can download */
  getReleasedModels: (token?: string | null) =>
    backendRequest<
      Array<{
        id: number;
        best_accuracy: number;
        best_f1_score: number;
        model_path_pt: string | null;
        model_path_onnx: string | null;
        model_released_at: string | null;
      }>
    >("/training/released-models", { method: "GET" }, token),

  /** Register a client (server role only): creates client + auth user in one step */
  registerClient: (
    data: { name: string; region: string; email: string; password: string },
    token?: string | null
  ) =>
    backendRequest<{ id: number; name: string; region: string | null; user_id: string; email: string }>(
      "/admin/clients",
      { method: "POST", body: JSON.stringify(data) },
      token
    ),
};

```ts
// tools/cronTools.ts
import axios, { AxiosError } from "axios";
import { CREATE_JOBS, DETAIL_JOBS } from "@/config/endpoints";
import { CRON_JOB_TOKEN } from "@/config/app";

import type { Workflow } from "@/types/workflow";
import type { CronJob } from "@/modules/reactflow-canvas/types";
import type {
  CreateCronJob,
  DeleteCronJob,
  UpdateCronJob,
} from "@/types/cronjob";
import type { ErrorResponse } from "@/types/hooks/axios";

/* ────────────────────────────────────────────────────────────────────────────
   Generic HTTP Tool
   ──────────────────────────────────────────────────────────────────────────── */

type HttpMethod = "GET" | "PUT" | "PATCH" | "DELETE";

export interface ToolResult<T> {
  ok: boolean;
  status: number;
  data?: T;
  error?: {
    code?: string;
    message: string;
    details?: unknown;
  };
}

interface ApiToolOptions<TBody> {
  method: HttpMethod;
  url: string;
  body?: TBody;
  params?: Record<string, unknown>;
  headers?: Record<string, string>;
  token?: string;           // Defaults to CRON_JOB_TOKEN
  timeoutMs?: number;       // Defaults to 15s
}

export async function apiTool<TResponse, TBody = unknown>(
  opts: ApiToolOptions<TBody>
): Promise<ToolResult<TResponse>> {
  const {
    method,
    url,
    body,
    params,
    headers,
    token = CRON_JOB_TOKEN,
    timeoutMs = 15_000,
  } = opts;

  try {
    const res = await axios.request<TResponse>({
      method,
      url,
      data: body,
      params,
      timeout: timeoutMs,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(headers ?? {}),
      },
    });

    return { ok: true, status: res.status, data: res.data };
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const ax = err as AxiosError<ErrorResponse>;
      return {
        ok: false,
        status: ax.response?.status ?? 0,
        error: {
          code: ax.code,
          message:
            (ax.response?.data as any)?.message ??
            ax.message ??
            "Request failed",
          details: ax.response?.data ?? ax.toJSON?.(),
        },
      };
    }
    return {
      ok: false,
      status: 0,
      error: { message: (err as Error).message || "Unknown error" },
    };
  }
}

/* ────────────────────────────────────────────────────────────────────────────
   Cron “Tool” Wrappers
   ──────────────────────────────────────────────────────────────────────────── */

export async function createJobTool(args: {
  workflowId: number;
  workflow: Workflow;
  body: CronJob;
}): Promise<ToolResult<CreateCronJob>> {
  const res = await apiTool<CreateCronJob, CronJob>({
    method: "PUT",
    url: CREATE_JOBS,
    body: args.body,
  });

  // Preserve your original return shape (augments with workflowId & workflow)
  if (res.ok && res.data) {
    return {
      ...res,
      data: {
        workflowId: args.workflowId,
        workflow: args.workflow,
        ...res.data,
      },
    };
  }
  return res;
}

export async function deleteJobTool(args: {
  cronjobId: number;
}): Promise<ToolResult<DeleteCronJob>> {
  return apiTool<DeleteCronJob>({
    method: "DELETE",
    url: DETAIL_JOBS(args.cronjobId),
  });
}

export async function updateJobTool(args: {
  cronjobId: number;
  body: CronJob;
}): Promise<ToolResult<UpdateCronJob>> {
  return apiTool<UpdateCronJob, CronJob>({
    method: "PATCH",
    url: DETAIL_JOBS(args.cronjobId),
    body: args.body,
  });
}

/* ────────────────────────────────────────────────────────────────────────────
   Example usage (anywhere, no React required)
   ──────────────────────────────────────────────────────────────────────────── */

// const r1 = await createJobTool({ workflowId, workflow, body });
// if (!r1.ok) console.error(r1.error?.message);
// else console.log("Created:", r1.data);

// const r2 = await deleteJobTool({ cronjobId });
// const r3 = await updateJobTool({ cronjobId, body });
```

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}/api/v1${path}`, init);
  if (!res.ok) throw new ApiError(res.status, `GET ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

export type Health = { status: "ok"; db: boolean; llm: boolean; version: string };

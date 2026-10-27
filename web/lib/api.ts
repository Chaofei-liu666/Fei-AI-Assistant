const API_URL = process.env.NEXT_PUBLIC_FEI_API_URL ?? "http://127.0.0.1:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(detail.detail ?? "请求失败");
  }
  return response.json();
}

export function upload(path: string, file: File): Promise<Record<string, unknown>> {
  const body = new FormData();
  body.append("file", file);
  return api(path, { method: "POST", body });
}

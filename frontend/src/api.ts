let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const res = await fetch("/api" + path, {
    ...options,
    headers,
    credentials: "include",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: res.statusText }));
    const message = Array.isArray(data.detail)
      ? data.detail.map((e: any) => `${e.loc?.join(".")}: ${e.msg}`).join("; ")
      : data.detail;
    if (res.status === 401) window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(res.status, message || "Request failed");
  }
  return res.json();
}
export function send(path: string, body: any, method = "POST") {
  return api(path, { method, body: JSON.stringify(body) });
}
export async function download(path: string, name: string) {
  const res = await fetch("/api" + path, { credentials: "include" });
  if (!res.ok) throw new Error("Export failed. Please retry.");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

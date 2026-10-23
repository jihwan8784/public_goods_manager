export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData;
  /** 401일 때 로그인 화면으로 보내지 않음 (로그인 화면 자체 등) */
  noRedirect?: boolean;
};

const FALLBACK: Record<number, string> = {
  400: "요청을 처리할 수 없습니다.",
  401: "로그인이 필요합니다.",
  403: "이 기능을 사용할 권한이 없습니다.",
  404: "요청한 정보를 찾을 수 없습니다.",
  409: "현재 상태에서는 처리할 수 없습니다.",
  413: "파일이 너무 큽니다.",
  422: "입력값을 확인해 주세요.",
};

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method: opts.method ?? (body ? "POST" : "GET"),
      headers,
      body,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "서버에 연결할 수 없습니다. 네트워크 상태를 확인한 뒤 다시 시도해 주세요.");
  }
  if (res.status === 401 && !opts.noRedirect && typeof window !== "undefined") {
    const next = window.location.pathname + window.location.search;
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?next=${encodeURIComponent(next)}`);
  }
  if (!res.ok) {
    let message = FALLBACK[res.status] ?? `서버 오류가 발생했습니다. (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") message = data.detail;
    } catch {
      /* JSON이 아닌 오류 응답 */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "알 수 없는 오류가 발생했습니다.";
}

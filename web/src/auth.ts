import Keycloak from "keycloak-js";

// Identity only: roles come from OpenDPO memberships, not from Keycloak.
export const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL ?? "http://localhost:8080",
  realm: "opendpo",
  clientId: "opendpo-web",
});

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  await keycloak.updateToken(30);
  const res = await fetch(path, {
    ...init,
    headers: { ...(init.headers ?? {}), Authorization: `Bearer ${keycloak.token}` },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body?.detail;
    const reasons: string[] = detail?.reasons ?? detail?.problems ?? [];
    const message: string | undefined = detail?.message;
    throw new Error(reasons.length ? [message, ...reasons].filter(Boolean).join("; ")
      : typeof detail === "string" ? detail : message ?? res.statusText);
  }
  return body as T;
}

// A page the API renders (an export), opened in a new tab with the user's token.
export async function openPage(path: string): Promise<void> {
  await keycloak.updateToken(30);
  const tab = window.open("", "_blank");
  const res = await fetch(path, { headers: { Authorization: `Bearer ${keycloak.token}` } });
  const text = await res.text();
  if (!res.ok) {
    tab?.close();
    let msg = res.statusText;
    try { msg = JSON.parse(text).detail ?? msg; } catch { /* not JSON */ }
    throw new Error(typeof msg === "string" ? msg : res.statusText);
  }
  const url = URL.createObjectURL(new Blob([text], { type: "text/html" }));
  if (tab) tab.location.href = url; else window.location.href = url;
}

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
    const reasons: string[] = detail?.reasons ?? [];
    throw new Error(reasons.length ? reasons.join("; ") : typeof detail === "string" ? detail : res.statusText);
  }
  return body as T;
}

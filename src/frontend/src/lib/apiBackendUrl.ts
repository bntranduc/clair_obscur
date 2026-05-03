/** Base de l’API FastAPI (sans slash final). Utilisé par ``next.config`` (rewrites) ; le client appelle ``/api/v1/…``. */
export function getBackendBaseUrl(): string {
  const raw =
    process.env.CLAIR_API_BACKEND_URL?.trim() ||
    process.env.NEXT_PUBLIC_CLAIR_API_BASE?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    "http://13.39.106.74:8020";
  return raw.replace(/\/+$/, "");
}

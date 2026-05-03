/** Base de l’API FastAPI (sans slash final). Client + Route Handlers. */
export function getBackendBaseUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_CLAIR_API_BASE?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    "http://13.39.106.74:8020";
  return raw.replace(/\/+$/, "");
}

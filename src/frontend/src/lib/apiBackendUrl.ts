/**
 * URL de base de l’API FastAPI (`api.main` ou `model_app`), **sans** slash final.
 * Priorité : `NEXT_PUBLIC_API_BASE` puis `NEXT_PUBLIC_MODEL_API_URL` (build Next),
 * sinon développement local.
 */
function apiBaseFromEnv(): string {
  if (typeof process === "undefined" || !process.env) return "";
  const raw =
    (process.env.NEXT_PUBLIC_API_BASE || "").trim() ||
    (process.env.NEXT_PUBLIC_MODEL_API_URL || "").trim();
  return raw.replace(/\/+$/, "");
}


// const API_BASE_DEV = "http://127.0.0.1:8020";
const API_BASE_DEV = "https://api.clairobscur.tech";


export function getBackendBaseUrl(): string {
  const fromEnv = apiBaseFromEnv();
  if (fromEnv) return fromEnv;
  return API_BASE_DEV.replace(/\/+$/, "");
}

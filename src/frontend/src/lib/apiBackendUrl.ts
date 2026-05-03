/** Base de l’API FastAPI (sans slash final). Pas de variables d’environnement : modifie ici si l’IP change. */
const API_BASE = "http://13.39.106.74:8020";

export function getBackendBaseUrl(): string {
  return API_BASE.replace(/\/+$/, "");
}

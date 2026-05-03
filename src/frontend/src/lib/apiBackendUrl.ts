/** Base de l’API FastAPI (sans slash final). Pas de variables d’environnement : modifie ici si l’IP change. */
const API_BASE = "https://api.clairobscur.tech";

export function getBackendBaseUrl(): string {
  return API_BASE.replace(/\/+$/, "");
}

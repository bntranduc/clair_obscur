/** Base de l’API FastAPI (sans slash final). Pas de variables d’environnement : modifie ici si l’IP change. */
// const API_BASE = "http://15.224.24.78:8020";

const API_BASE = "http://127.0.0.1:8020";

export function getBackendBaseUrl(): string {
  return API_BASE.replace(/\/+$/, "");
}

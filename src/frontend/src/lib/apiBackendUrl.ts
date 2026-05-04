
// const API_BASE = "http://127.0.0.1:8020";
const API_BASE = "https://api.clairobscur.tech";

export function getBackendBaseUrl(): string {
  return API_BASE.replace(/\/+$/, "");
}

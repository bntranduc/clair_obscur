/** URL ``POST .../predict`` — direct si ``NEXT_PUBLIC_MODEL_API_URL``, sinon proxy Next ``/bff-model``. */

export function getModelPredictUrl(): string {
  const direct = process.env.NEXT_PUBLIC_MODEL_API_URL?.trim();
  if (direct) return `${direct.replace(/\/+$/, "")}/predict`;
  return "/bff-model/predict";
}

export function getModelHealthUrl(): string {
  const direct = process.env.NEXT_PUBLIC_MODEL_API_URL?.trim();
  if (direct) return `${direct.replace(/\/+$/, "")}/health`;
  return "/bff-model/health";
}

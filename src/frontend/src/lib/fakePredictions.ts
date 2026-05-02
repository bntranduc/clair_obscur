import data from "@/data/predictions_all_attack_types.json";
import type { ModelAlert, PredictionsPayload } from "@/types/modelPrediction";

export function getFakePredictions(): PredictionsPayload {
  return data as PredictionsPayload;
}

export function getFakeAlertByChallengeId(id: string): ModelAlert | undefined {
  return getFakePredictions().alerts.find((a) => a.challenge_id === id);
}

"use client";

import { useEffect, useState } from "react";

interface QuestionnaireInput {
  sleep_schedule: string;
  cleanliness_level: number;
  guests: string;
  noise_tolerance: number;
  wfh: boolean;
  pets: boolean;
  budget: string;
}

interface MatchRequest {
  questionnaire_a: QuestionnaireInput;
  free_text_a: string;
  questionnaire_b: QuestionnaireInput;
  free_text_b: string;
}

interface MatchResponse {
  job_id: string;
}

interface ObserverNotes {
  scenario_index: number;
  friction_points: string[];
  dealbreaker_violations: string[];
  tone_shifts: string[];
  concessions: string[];
}

interface ScenarioCompleteMessage {
  type: "scenario_complete";
  scenario: number;
  observer_notes: ObserverNotes;
}

interface VerdictObject {
  lifestyle_score: number;
  communication_score: number;
  conflict_score: number;
  dealbreaker_score: number;
  lifestyle_explanation: string;
  communication_explanation: string;
  conflict_explanation: string;
  dealbreaker_explanation: string;
  overall_summary: string;
}

interface CompleteMessage {
  type: "complete";
  verdict: VerdictObject;
}

interface FailedMessage {
  type: "failed";
  job_id: string;
}

type WsMessage = ScenarioCompleteMessage | CompleteMessage | FailedMessage;

const TOTAL_STEPS = 3;
const API_URL = "http://localhost:8000";
const WS_URL = "ws://localhost:8000";

const TEST_PERSONA_B: QuestionnaireInput = {
  sleep_schedule: "night_owl",
  cleanliness_level: 4,
  guests: "often",
  noise_tolerance: 8,
  wfh: false,
  pets: true,
  budget: "medium",
};
const TEST_FREE_TEXT_B =
  "I'm laid back, love having friends over, and don't stress much about mess.";

export default function Home() {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState<QuestionnaireInput>({
    sleep_schedule: "",
    cleanliness_level: 5,
    guests: "",
    noise_tolerance: 5,
    wfh: false,
    pets: false,
    budget: "",
  });
  const [freeText, setFreeText] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioCompleteMessage[]>([]);
  const [verdict, setVerdict] = useState<VerdictObject | null>(null);
  const [simulationStatus, setSimulationStatus] = useState<"running" | "complete" | "failed">("running");
  const [wsError, setWsError] = useState<string | null>(null);

  const isStepValid = (): boolean => {
    if (step === 1) return formData.sleep_schedule !== "" && formData.budget !== "";
    if (step === 2) return formData.guests !== "";
    if (step === 3) return freeText.trim().length > 0;
    return false;
  };

  const handleNext = () => {
    if (isStepValid() && step < TOTAL_STEPS) setStep(step + 1);
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  const handleSubmit = async () => {
    if (!isStepValid()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const body: MatchRequest = {
        questionnaire_a: formData,
        free_text_a: freeText,
        questionnaire_b: TEST_PERSONA_B,
        free_text_b: TEST_FREE_TEXT_B,
      };
      const response = await fetch(`${API_URL}/match`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const errorBody = await response.json().catch(() => null);
        throw new Error(
          errorBody?.detail ? JSON.stringify(errorBody.detail) : `Request failed with status ${response.status}`
        );
      }
      const data: MatchResponse = await response.json();
      setJobId(data.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    if (!jobId) return;

    const ws = new WebSocket(`${WS_URL}/match/${jobId}/stream`);

    ws.onmessage = (event) => {
      const message: WsMessage = JSON.parse(event.data);
      if (message.type === "scenario_complete") {
        setScenarios((prev) => [...prev, message]);
      } else if (message.type === "complete") {
        setVerdict(message.verdict);
        setSimulationStatus("complete");
        ws.close();
      } else if (message.type === "failed") {
        setSimulationStatus("failed");
        ws.close();
      }
    };

    ws.onerror = () => {
      setWsError("Lost connection to the simulation stream.");
    };

    return () => {
      ws.close();
    };
  }, [jobId]);

  return (
    <div className="flex flex-1 items-center justify-center bg-zinc-50 px-4 py-16 dark:bg-black">
      <div className="w-full max-w-lg rounded-2xl border border-black/8 bg-white p-8 dark:border-white/[.145] dark:bg-zinc-900">
        {jobId ? (
          <div className="flex flex-col gap-4">
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Simulation in progress</h2>
            <p className="rounded-lg bg-zinc-100 px-3 py-2 font-mono text-sm text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
              {jobId}
            </p>

            {simulationStatus === "running" && (
              <div className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-600 dark:border-t-zinc-50" />
                Running simulation...
              </div>
            )}
            {simulationStatus === "complete" && (
              <p className="text-sm font-medium text-green-600 dark:text-green-400">Simulation complete.</p>
            )}
            {simulationStatus === "failed" && (
              <p className="text-sm font-medium text-red-600 dark:text-red-400">Simulation failed.</p>
            )}
            {wsError && <p className="text-sm text-red-600 dark:text-red-400">{wsError}</p>}

            {scenarios.length > 0 && (
              <ul className="flex flex-col gap-2">
                {scenarios.map((s) => (
                  <li
                    key={s.scenario}
                    className="flex items-center justify-between rounded-lg bg-zinc-100 px-3 py-2 text-sm dark:bg-zinc-800"
                  >
                    <span className="text-zinc-800 dark:text-zinc-200">Scenario {s.scenario + 1}</span>
                    <span className="text-xs font-medium text-green-600 dark:text-green-400">Complete</span>
                  </li>
                ))}
              </ul>
            )}

            {simulationStatus === "complete" && verdict && (
              <div className="flex flex-col gap-5 border-t border-zinc-200 pt-5 dark:border-zinc-700">
                <div className="rounded-lg bg-zinc-100 px-4 py-3 dark:bg-zinc-800">
                  <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50">{verdict.overall_summary}</p>
                </div>

                {[
                  { label: "Lifestyle", score: verdict.lifestyle_score, explanation: verdict.lifestyle_explanation },
                  {
                    label: "Communication",
                    score: verdict.communication_score,
                    explanation: verdict.communication_explanation,
                  },
                  {
                    label: "Conflict resolution",
                    score: verdict.conflict_score,
                    explanation: verdict.conflict_explanation,
                  },
                  {
                    label: "Dealbreakers",
                    score: verdict.dealbreaker_score,
                    explanation: verdict.dealbreaker_explanation,
                  },
                ].map((dimension) => (
                  <div key={dimension.label} className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      <span>{dimension.label}</span>
                      <span>{dimension.score}/10</span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-zinc-200 dark:bg-zinc-700">
                      <div
                        className="h-1.5 rounded-full bg-zinc-900 dark:bg-zinc-50"
                        style={{ width: `${dimension.score * 10}%` }}
                      />
                    </div>
                    <p className="text-sm text-zinc-600 dark:text-zinc-400">{dimension.explanation}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="mb-8 flex items-center gap-2">
              {Array.from({ length: TOTAL_STEPS }, (_, i) => i + 1).map((s) => (
                <div
                  key={s}
                  className={`h-1.5 flex-1 rounded-full ${
                    s <= step ? "bg-zinc-900 dark:bg-zinc-50" : "bg-zinc-200 dark:bg-zinc-700"
                  }`}
                />
              ))}
            </div>

            {step === 1 && (
              <div className="flex flex-col gap-5">
                <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Basic info</h2>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="sleep_schedule" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Sleep schedule
                  </label>
                  <select
                    id="sleep_schedule"
                    value={formData.sleep_schedule}
                    onChange={(e) => setFormData({ ...formData, sleep_schedule: e.target.value })}
                    className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800"
                  >
                    <option value="">Select...</option>
                    <option value="early_bird">Early bird</option>
                    <option value="night_owl">Night owl</option>
                    <option value="flexible">Flexible</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="budget" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Budget
                  </label>
                  <select
                    id="budget"
                    value={formData.budget}
                    onChange={(e) => setFormData({ ...formData, budget: e.target.value })}
                    className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800"
                  >
                    <option value="">Select...</option>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </div>

                <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                  <input
                    type="checkbox"
                    checked={formData.wfh}
                    onChange={(e) => setFormData({ ...formData, wfh: e.target.checked })}
                    className="h-4 w-4"
                  />
                  Work from home
                </label>

                <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                  <input
                    type="checkbox"
                    checked={formData.pets}
                    onChange={(e) => setFormData({ ...formData, pets: e.target.checked })}
                    className="h-4 w-4"
                  />
                  Have pets
                </label>
              </div>
            )}

            {step === 2 && (
              <div className="flex flex-col gap-5">
                <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Lifestyle preferences</h2>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="cleanliness_level" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Cleanliness level: {formData.cleanliness_level}
                  </label>
                  <input
                    id="cleanliness_level"
                    type="range"
                    min={1}
                    max={10}
                    value={formData.cleanliness_level}
                    onChange={(e) => setFormData({ ...formData, cleanliness_level: Number(e.target.value) })}
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="noise_tolerance" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Noise tolerance: {formData.noise_tolerance}
                  </label>
                  <input
                    id="noise_tolerance"
                    type="range"
                    min={1}
                    max={10}
                    value={formData.noise_tolerance}
                    onChange={(e) => setFormData({ ...formData, noise_tolerance: Number(e.target.value) })}
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="guests" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Guests
                  </label>
                  <select
                    id="guests"
                    value={formData.guests}
                    onChange={(e) => setFormData({ ...formData, guests: e.target.value })}
                    className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800"
                  >
                    <option value="">Select...</option>
                    <option value="rarely">Rarely</option>
                    <option value="occasionally">Occasionally</option>
                    <option value="often">Often</option>
                  </select>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="flex flex-col gap-5">
                <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Tell us about yourself</h2>
                <textarea
                  value={freeText}
                  onChange={(e) => setFreeText(e.target.value)}
                  rows={6}
                  placeholder="Describe your living habits, personality, and what you're looking for in a roommate..."
                  className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800"
                />
              </div>
            )}

            <div className="mt-8 flex justify-between">
              <button
                type="button"
                onClick={handleBack}
                disabled={step === 1}
                className="rounded-full border border-zinc-300 px-5 py-2 text-sm font-medium disabled:opacity-40 dark:border-zinc-600"
              >
                Back
              </button>

              {step < TOTAL_STEPS ? (
                <button
                  type="button"
                  onClick={handleNext}
                  disabled={!isStepValid()}
                  className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-zinc-50 dark:text-zinc-900"
                >
                  Next
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={!isStepValid() || isSubmitting}
                  className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-zinc-50 dark:text-zinc-900"
                >
                  {isSubmitting ? "Submitting..." : "Submit"}
                </button>
              )}
            </div>

            {error && <p className="mt-4 text-sm text-red-600 dark:text-red-400">{error}</p>}
          </>
        )}
      </div>
    </div>
  );
}

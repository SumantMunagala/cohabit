"use client";

import { useState } from "react";

interface QuestionnaireInput {
  sleep_schedule: string;
  cleanliness_level: number;
  guests: string;
  noise_tolerance: number;
  wfh: boolean;
  pets: boolean;
  budget: string;
}

interface QuestionnaireFormData extends QuestionnaireInput {
  free_text: string;
}

const TOTAL_STEPS = 3;

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

  const handleSubmit = () => {
    if (!isStepValid()) return;
    const submission: QuestionnaireFormData = { ...formData, free_text: freeText };
    console.log(submission);
  };

  return (
    <div className="flex flex-1 items-center justify-center bg-zinc-50 px-4 py-16 dark:bg-black">
      <div className="w-full max-w-lg rounded-2xl border border-black/8 bg-white p-8 dark:border-white/[.145] dark:bg-zinc-900">
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
              disabled={!isStepValid()}
              className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-zinc-50 dark:text-zinc-900"
            >
              Submit
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

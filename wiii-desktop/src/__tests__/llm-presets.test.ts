import { applyLlmProviderPreset, CURRENT_GOOGLE_CHAT_MODELS, GOOGLE_DEFAULT_MODEL } from "@/lib/llm-presets";

describe("llm presets", () => {
  it("keeps the Google default aligned with the current model catalog", () => {
    expect(GOOGLE_DEFAULT_MODEL).toBe("gemini-3.1-flash-lite-preview");
    expect(CURRENT_GOOGLE_CHAT_MODELS).toContain(GOOGLE_DEFAULT_MODEL);
  });

  it("applies the Google preset when no runtime override exists", () => {
    const updated = applyLlmProviderPreset({}, "google");

    expect(updated.llm_provider).toBe("google");
    expect(updated.google_model).toBe(GOOGLE_DEFAULT_MODEL);
  });
});

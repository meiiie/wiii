import type { AppSettings } from "@/api/types";

export type LlmProvider = "google" | "openai" | "openrouter" | "ollama";

export const GOOGLE_DEFAULT_MODEL = "gemini-3.1-flash-lite-preview";
export const CURRENT_GOOGLE_CHAT_MODELS = [GOOGLE_DEFAULT_MODEL] as const;
export const GOOGLE_LEGACY_MODELS = [
  "gemini-2.5-flash",
  "gemini-2.5-pro",
  "gemini-2.0-flash",
  "gemini-2.0-flash-exp",
] as const;
export const OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1";
export const OPENROUTER_DEFAULT_MODEL = "openai/gpt-oss-20b:free";
export const OPENROUTER_DEFAULT_MODEL_ADVANCED = "openai/gpt-oss-120b:free";
// Current verified local-dev default: backend Docker container -> native host Ollama.
// If backend runs outside Docker, switch this to http://localhost:11434 in runtime config.
export const OLLAMA_DEFAULT_BASE_URL = "http://host.docker.internal:11434";
export const OLLAMA_DEFAULT_MODEL = "qwen3:4b-instruct-2507-q4_K_M";
export const OLLAMA_DEFAULT_KEEP_ALIVE = "30m";

type LlmProviderPreset = {
  provider: LlmProvider;
  llm_failover_chain: string[];
  google_model?: string;
  openai_base_url?: string;
  openai_model?: string;
  openai_model_advanced?: string;
  ollama_base_url?: string;
  ollama_model?: string;
  ollama_keep_alive?: string;
};

const PRESETS: Record<LlmProvider, LlmProviderPreset> = {
  google: {
    provider: "google",
    llm_failover_chain: ["google", "ollama", "openrouter"],
    google_model: GOOGLE_DEFAULT_MODEL,
  },
  openai: {
    provider: "openai",
    llm_failover_chain: ["openai", "ollama", "google"],
  },
  openrouter: {
    provider: "openrouter",
    llm_failover_chain: ["openrouter", "ollama", "google"],
    openai_base_url: OPENROUTER_BASE_URL,
    openai_model: OPENROUTER_DEFAULT_MODEL,
    openai_model_advanced: OPENROUTER_DEFAULT_MODEL_ADVANCED,
  },
  ollama: {
    provider: "ollama",
    llm_failover_chain: ["ollama", "google", "openrouter"],
    ollama_base_url: OLLAMA_DEFAULT_BASE_URL,
    ollama_model: OLLAMA_DEFAULT_MODEL,
    ollama_keep_alive: OLLAMA_DEFAULT_KEEP_ALIVE,
  },
};

export function getLlmPreset(provider: LlmProvider): LlmProviderPreset {
  return PRESETS[provider];
}

export function applyLlmProviderPreset(
  current: Partial<AppSettings>,
  provider: LlmProvider
): Partial<AppSettings> {
  const preset = getLlmPreset(provider);
  return {
    ...current,
    llm_provider: provider,
    google_model: preset.google_model ?? current.google_model ?? GOOGLE_DEFAULT_MODEL,
    openai_base_url: preset.openai_base_url ?? current.openai_base_url ?? "",
    openai_model:
      preset.openai_model ?? current.openai_model ?? OPENROUTER_DEFAULT_MODEL,
    openai_model_advanced:
      preset.openai_model_advanced
      ?? current.openai_model_advanced
      ?? OPENROUTER_DEFAULT_MODEL_ADVANCED,
    ollama_base_url:
      preset.ollama_base_url ?? current.ollama_base_url ?? OLLAMA_DEFAULT_BASE_URL,
    ollama_model:
      preset.ollama_model ?? current.ollama_model ?? OLLAMA_DEFAULT_MODEL,
    ollama_keep_alive:
      preset.ollama_keep_alive
      ?? current.ollama_keep_alive
      ?? OLLAMA_DEFAULT_KEEP_ALIVE,
    llm_failover_chain: preset.llm_failover_chain,
  };
}

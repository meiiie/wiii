# Wiii Personality Fine-Tune via Unsloth — Research + Plan

Phase 33f of the runtime migration epic ([#207](https://github.com/meiiie/wiii/issues/207)).
Research output. **Implementation deferred** — fine-tuning needs GPU
access, a curated dataset, and 1-2 weeks of focused work that doesn't
fit a runtime-migration session. This doc captures the plan so the
team can execute without re-deriving the design.

## Why fine-tune at all

Wiii's content quality at SOTA today (V4 Pro, ChatGPT, Claude all
viable) — what's NOT at SOTA is **Vietnamese-first personality
alignment**. Specifically:

| Pain point | Today's mitigation | What fine-tuning unlocks |
|------------|--------------------|--------------------------|
| Thinking models think in English | Reverted to V4 Pro (no visible thinking) | A model that thinks in VN end-to-end → visible reasoning users can read |
| V4 Pro persona drifts mid-conversation | Heavy system prompt + persona overlay | Persona BAKED IN — no prompt-engineering tax per turn |
| Diacritic correction inconsistent | Model guesses (Hung → Hưng usually) | Model trained on VN diacritic-aware corpus → consistent every turn |
| Soul / kawaii style imperfect on edge cases | Heavy prompt | Style baked in — saves ~500 prompt tokens per turn |
| Token cost on every Wiii turn | Pay-per-call NVIDIA NIM | Self-hosted model = $0 marginal cost after training amortized |

Concrete win: a fine-tuned 8B model running on a single RTX 4090 can
serve Wiii's full traffic at ~$0/turn after the one-time training
cost. Today every NVIDIA NIM call is metered.

## Why Unsloth specifically

Three open-source frameworks are mature for this in 2026-05:

1. **Unsloth** (this repo: `_research/unsloth`) — Triton kernels +
   2-5× faster QLoRA training than vanilla HF, ships notebooks for
   Llama / Mistral / Gemma / Qwen / DeepSeek-R1 fine-tunes.
2. **Axolotl** — config-driven, less kernel optimization, broader
   model coverage.
3. **TRL + PEFT** (HF native) — most flexible, slowest.

Pick Unsloth because it lives in `_research/` already AND the team
mentioned it specifically. Cost-wise: Unsloth's 4-bit QLoRA for an
8B model fits on a single 24 GB GPU in ~6-12 hours.

## Recommended base model

**Qwen 2.5 7B** or **DeepSeek V4 Flash** (open-weight variant when
DeepSeek ships it; today only the API version is hosted on NVIDIA NIM).

Selection criteria:
- Multilingual training corpus (VN + EN + ZH).
- Compatible with Unsloth's trainer (Qwen 2.5 ✅, Llama 3.2 ✅,
  Mistral 7B ✅).
- Open-weight (no API gating).
- Comparable raw capability to V4 Pro on Vietnamese benchmarks.

DON'T pick:
- Vietnamese-specific bases like PhoGPT — older base, weaker
  reasoning than current 7B-class general models.
- 3B-class models — too small for nuanced personality.
- 70B-class models — 24 GB GPU can't fit even with QLoRA.

## Dataset preparation

Three sources, in this order:

### Source 1 — synthetic Wiii-personality dialogues

Generate ~5K turns using V4 Pro + Wiii's existing system prompt as
the teacher. Each example:

```
{
  "messages": [
    {"role": "system", "content": "<wiii_soul.yaml prompt>"},
    {"role": "user", "content": "alo Wiii"},
    {"role": "assistant", "content": "Alo cậu! Mình đây rồi~ (˶˃ ᵕ ˂˶)"}
  ]
}
```

Filter: drop any example where V4 Pro broke persona (used "tôi" instead
of "mình", switched to English mid-sentence, etc.). Manual review of
~200 of them before training.

### Source 2 — domain knowledge dialogues (COLREGs / SOLAS / MARPOL)

~1K turns covering the maritime domain Wiii's primary users care about.
Same shape as Source 1 but with anchored RAG context as the system prompt.

### Source 3 — refusal / safety examples

~500 turns where Wiii politely declines off-topic / harmful requests.
Critical to prevent fine-tune from regressing safety.

**Total**: ~6.5K turns. At 4-bit QLoRA, a 7B base trains in 6-8 hours
on a 4090.

## Training pipeline

```bash
# In _research/unsloth (clone if not present)
cd _research/unsloth
python -m venv .venv
.venv/bin/pip install -e .

# Prepare dataset as JSONL
python scripts/prep_wiii_dataset.py \
    --teacher-base-url https://integrate.api.nvidia.com/v1 \
    --teacher-model deepseek-ai/deepseek-v4-pro \
    --soul-prompt /path/to/wiii_soul.yaml \
    --out wiii-train-v1.jsonl \
    --num-turns 5000

# Train
python -m unsloth.cli train \
    --base-model Qwen/Qwen2.5-7B-Instruct \
    --dataset wiii-train-v1.jsonl \
    --output-dir ./wiii-personality-v1 \
    --num-train-epochs 3 \
    --learning-rate 2e-4 \
    --lora-rank 32 \
    --quantization 4bit \
    --max-seq-length 4096

# Export to GGUF for Ollama serving
python -m unsloth.cli export \
    --adapter-path ./wiii-personality-v1 \
    --format gguf \
    --quantization q4_k_m \
    --output wiii-personality-v1.gguf

# Serve locally
ollama create wiii-personality -f Modelfile
# Where Modelfile points to the GGUF
```

## Integration with Wiii runtime

Once `wiii-personality-v1.gguf` is in Ollama:

1. Add a new provider config in `app/engine/llm_providers/`:

   ```python
   # app/engine/llm_providers/wiii_personality_provider.py
   # Thin OpenAI-compat wrapper around Ollama's /v1/chat/completions
   # endpoint. Same shape as the existing Ollama provider, just
   # pinned to model="wiii-personality".
   ```

2. Add to `model_catalog.py`:

   ```python
   WIII_PERSONALITY_MODEL = "wiii-personality"
   WIII_PERSONALITY_MODELS = {
       WIII_PERSONALITY_MODEL: ChatModelMetadata(
           provider="wiii-local",
           model_name=WIII_PERSONALITY_MODEL,
           display_name="Wiii Personality v1 (self-hosted)",
           status="current",
           supports_streaming=True,
       ),
   }
   ```

3. Set in `.env.production`:

   ```bash
   LLM_PROVIDER=wiii-local
   LLM_FAILOVER_CHAIN=["wiii-local", "nvidia"]
   WIII_LOCAL_BASE_URL=http://localhost:11434/v1
   WIII_LOCAL_MODEL=wiii-personality
   ```

4. Failover to NVIDIA stays — if local model dies, traffic seamlessly
   shifts to V4 Pro.

## Acceptance bar before swapping the default

- [ ] **Persona consistency** ≥ 95% — manual eval of 50 turns: how often
      does the model use "mình" / "cậu" correctly + maintain kawaii
      tone? Regression vs V4 Pro must be < 5%.
- [ ] **Maritime knowledge accuracy** ≥ 90% — quiz on 50 COLREGs /
      SOLAS / MARPOL questions. Regression vs V4 Pro must be < 10%.
- [ ] **Refusal correctness** ≥ 99% on the 50-prompt safety eval set.
      No regression vs V4 Pro acceptable.
- [ ] **Latency** ≤ V4 Pro p99 on a 4090. (Should be much faster —
      local model = no network round-trip.)
- [ ] **Diacritic accuracy** ≥ 99% on a 30-prompt test where user
      types diacritic-free Vietnamese.
- [ ] **Replay regression** (Phase 11b nightly) shows token_jaccard
      ≥ 0.85 vs the prior model on existing recordings.

## Cost + time

| Resource | Estimate |
|----------|----------|
| GPU rental (one-shot, RunPod / Lambda) | ~$30-50 (RTX 4090 × 8 hours) |
| Teacher API cost (5K turns × ~500 tokens) | ~$5-10 (V4 Pro on NVIDIA NIM) |
| Engineer time | 1-2 weeks (dataset prep + training + eval + integration) |
| Storage (model weights + adapter) | ~10 GB total |
| Marginal serving cost | $0/turn (self-hosted via Ollama) |

## Risk register

| Risk | Mitigation |
|------|------------|
| Fine-tune regresses on out-of-distribution queries | Keep NVIDIA NIM as failover (seamless via LLM_FAILOVER_CHAIN) |
| Training data captures V4 Pro's edge-case bugs | Manual review of dataset; refusal/safety examples explicitly curated |
| Personality over-fits to teacher's style quirks | Multiple teacher passes with different decoding seeds; sample diversity |
| Model grows too confident on niche maritime topics | Regular refresh from RAG ground truth; eval set covers the hardest 10% |
| 4090 is unavailable / too slow | Falls back to A100 rental on RunPod (~$60-80 for 8 hours) |

## Why this is research output, not a code PR today

Fine-tuning is a 1-2 week focused effort with hardware dependency.
Squeezing it into a runtime-migration session would either rush the
dataset (bad) or block the session on hardware availability (worse).
Document the plan so the team executes when the window opens.

## Related work

- `_research/unsloth/` — the cloned framework with all kernels.
- `_research/openai-agents-python/` — reference SDK comparison.
- `docs/runtime/PROVIDER_SEED_SUPPORT.md` (Phase 22) — provider matrix
  including upstream-blocked items.
- `docs/runtime/CANARY_ONBOARDING.md` (Phase 28) — when ready to
  cut over to the fine-tuned model.

## Review log

| Date | Reviewer | Change |
|------|----------|--------|
| 2026-05-04 | runtime | v1 — initial research + plan, Phase 33f of #207 |

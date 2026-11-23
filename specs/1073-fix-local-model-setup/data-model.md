# Data model

- Preset: native-owned id/label/protocol/default endpoint/model/key requirement, no credential.
- Request: presetId/model/optional baseUrl/apiKey; deserialize-only, bounded; never Debug/logged/persisted by renderer.
- Response: profileId/model/provider; no saved key or raw config.
- Status: configured boolean/presets, read-only, no network or returned environment values.
- Persisted record: canonical profiles[id] connection fields/active_profile; preserve unrelated data and prior credential ownership. Existing sessions retain their binding.
- State: loading → first-use/available → editing → saving → saved-unverified or retryable error. Cancel restores focus and clears ephemeral key state; draft lives outside dialog.

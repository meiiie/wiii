# IPC and UI contract

- `local_model_status() -> { configured, presets[] }`: main only, native home resolution, no mutation/network.
- `local_model_save({ presetId, model, baseUrl?, apiKey }) -> { profileId, model, provider }`: main only, validated canonical profile/active selection; no caller path/process/env authority.
- Register both consistently in Rust handler, build.rs AppManifest, generated permissions, main-only workbench-models capability and security_contract.
- Keys only flow password input → typed save IPC → private canonical configuration; never return/repopulate them or persist them in browser state/telemetry/errors.
- Known Vietnamese errors are retryable; unexpected invoke errors use generic copy, not raw reflection.
- Overview/project/File share the dialog. Unconfigured project Send opens setup instead; save refreshes/selects the returned profile without remounting the draft. No automatic Send; changes apply to new chats.

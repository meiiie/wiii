---
name: tool-governance
description: Govern Wiii tools, sandbox execution, capability registration, and artifact streaming. Use when adding, changing, reviewing, or debugging tools; deciding between deterministic file-generation tools, OpenSandbox code execution, browser automation, or MCP-style integrations; updating role gates and capability registry; or wiring generated files into previews/artifacts.
---

# Tool Governance

Use the smallest execution surface that can solve the task.

- Use native deterministic tools for exportable deliverables such as `.html`, `.xlsx`, `.docx`, structured reports, or data transforms that do not need untrusted code execution.
- Use OpenSandbox Python for dynamic computation, plotting, dataframe work, or code that must run in an isolated runtime.
- Use browser sandbox only for navigation, screenshots, DOM extraction, or agent-visible web interaction.
- Avoid turning every endpoint into a separate tool. Prefer a small number of broad capabilities with clear arguments.

Keep tool changes aligned across the stack.

1. Register the tool in the runtime registry and set category/access rules.
2. Add or update capability metadata in [capability_registry.py](../capability_registry.py).
3. Bind the tool only in the agent paths that should actually use it.
4. Emit user-visible outputs as `preview` or `artifact` bus events instead of burying them in plain text.
5. Add focused tests for registration, permissioning, and runtime behavior.

Treat artifacts as first-class outputs.

- Stream raw HTML only when the user needs a renderable page or landing page preview.
- Stream chart/image artifacts as base64-backed `chart` artifacts.
- Stream JSON/CSV tables as `table` artifacts when possible.
- Stream binary office files (`.xlsx`, `.docx`, `.pdf`) as document-style artifacts with stable metadata (`file_path`, `file_url`, `content_type`) even when inline preview is not possible.

Preserve operational safety.

- Keep privileged execution behind explicit role gates.
- Propagate `request_id`, `session_id`, `organization_id`, `user_id`, and `tool_call_id` into sandbox metadata and artifact events.
- Do not rely on raw chain-of-thought to explain tool work. Use concise action text plus inspectable artifacts.
- Prefer capability-level descriptions over implementation details in prompts and selectors.

When reviewing a tool design, challenge four things before shipping.

1. Can this be a deterministic tool instead of sandbox code?
2. Is the tool broad enough to avoid tool explosion?
3. Does the output appear as a first-class artifact or preview?
4. Are role gates, telemetry, and tests in place?

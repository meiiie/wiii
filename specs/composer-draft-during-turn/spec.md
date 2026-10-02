# Compose a draft while a turn runs

The local Neko composer must allow typing during dispatching and streaming. Editing a draft never authorizes a second prompt. Enter remains gated, Stop retains its existing semantics, and model changes remain gated while busy. A visible status explains that the text is only a draft and requires explicit Send after the current turn finishes.

Permission, configuration, close and delete gates remain protected. Existing session-scoped draft persistence and accepted-callback comparison remain authoritative. No queue or auto-drain is introduced by this patch.

Risk: accidentally enabling dispatch or clearing a newer draft. Regression tests cover both busy states, Enter, absence of implicit cancellation, retention into idle, and explicit later send. Rollback: revert composer and its new tests; no data migration.

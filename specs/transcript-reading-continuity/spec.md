# Transcript reading continuity

Scope: local Neko transcript presentation. No runtime, provider, outbox, persistence or permission contract changes.

- Follow rendered answer growth while the reader is at the tail, including deferred Markdown and viewport resize
- Coalesce layout notifications to at most one pending animation frame
- A reader moving away wins over an already scheduled follow; no delayed frame may pull them back
- Returning to newest synchronizes state/ref and moves focus to the surviving transcript viewport
- Keyboard users can focus and scroll the transcript; reduced-motion preference applies to explicit jumps
- Switching sessions cancels old pending work and starts at the new transcript tail
- Preserve existing virtualized history and permission cards

Validation: deterministic frame/resize regression tests, full frontend suite, type/build/embed checks, native Linux synthetic conversation and screenshots. Native pixel and assistive-technology conformance are distinct; no blanket WCAG claim.

Risk: scroll anchoring during dynamic layout and virtual measurements. Rollback: revert this scoped UI commit, no data migration.

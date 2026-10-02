# Micro-interactions: catalog and sidebar

Reference: official ZCode commit 29628c9; ControlHintTooltip, tooltip primitive, V4ComposerModeControls and ConversationBottomDockTransition. Lessons: stable focus targets, explicit selected state, bounded popup geometry, no decorative motion when reduced motion is requested. No source copied or dependencies added.

Catalog contract: opening focuses search and reveals the current choice; arrows skip disabled options in visual group order; Home/End explore; Enter explicitly commits the highlighted choice; Tab/Shift+Tab leave without mutating settings; Escape returns focus. IME composition must not commit. The owner-provided disabled state closes stale menus. Loading indicators alone do not prevent explicitly choosing an alternative harness while discovery runs. ARIA combobox uses active descendant while listbox reports actual selection. Search reset retains focus. Popup width/height are bounded to viewport; resize recalculates placement. Current value has a checkmark. A 120ms opacity-only entrance is disabled under reduced motion.

Sidebar contract: no-match state remains visible even with existing projects; a clear-filter action recovers the list and focuses search. Escape clears search without navigation. Unsent scratch entries respect filtering. Touch/coarse-pointer users can discover row actions without hover.

Validation: focused keyboard, mutation, selection, grouping, IME, pending and sidebar recovery tests; complete desktop suite, typecheck, desktop/embed builds; native Linux screenshots and Tab/Escape checks. Cross-platform and assistive technology certification remain unverified.

Risk and rollback: presentation/keyboard semantics only; no runtime, permission or persistence schema changes. Revert these components, tests and styles to restore previous UX without migrating user data.

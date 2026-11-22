# Implementation tasks

- [ ] Extend existing native PID-1 recovery with exact scoped checkpoint/receipt/root/execution proof and physical quiescence; retain unknown outcomes and support missing-lock retry after a strict save failure.
- [ ] Enable only typed writer-unavailable receipt-bearing mappings through the existing recovery action; positive native proof and a strict save precede unlocking. Never dispatch a prompt during recovery.
- [ ] Add adversarial native tests (including live writer refusal), mapping/client/store regressions and persistence-failure retry coverage; run required checks.
- [ ] Verify the real preserved cross-version scoped conversation natively, compare snapshot bytes, settle CI/risk review and only then merge. Record Neko Core shutdown investigation separately.

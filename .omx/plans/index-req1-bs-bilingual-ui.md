# Plan Index — req1 BS bilingual UI

## Active planning artifact set
This is the active OMX planning set for implementing the req1/browser-server bilingual rebuild on branch `feature/req1-bs-bilingual-ui`.

### 1. Consensus plan
- `ralplan-req1-bs-bilingual-ui.md`
- Purpose: source-of-truth planning artifact from ralplan, including ADRs, frozen contracts, storage model, API model, UI decisions, and verification matrix.

### 2. PRD
- `prd-req1-bs-bilingual-ui.md`
- Purpose: product scope, goals, in-scope/out-of-scope, UX decisions, functional inventory.

### 3. Test spec
- `test-spec-req1-bs-bilingual-ui.md`
- Purpose: automated/manual verification strategy, acceptance evidence, legacy-path checks.

### 4. Execution slices
- `slices-req1-bs-bilingual-ui.md`
- Purpose: OMX-friendly execution breakdown from large phases into small, verifiable work packages suitable for `ralph` or `team`.

### 5. Context snapshot
- `../context/req1-bs-bilingual-ui-20260418T083323Z.md`
- Purpose: brownfield task context captured before consensus planning.

### 6. Traceability matrix
- `traceability-req1-bs-bilingual-ui.md`
- Purpose: requirement-to-mode/API/UI mapping and frozen-contract lock record.

### 7. Acceptance evidence
- `acceptance-evidence-req1-bs-bilingual-ui.md`
- Purpose: M4 walkthrough ledger for 12 leaf modes, recordings/history coverage, and CN/EN shell evidence.

## Non-active / legacy artifacts in `.omx/plans`
These exist in the directory but are not part of the active req1 execution set:
- `prd-layer-2-omx-onboarding-assets.md`
- `test-spec-layer-2-omx-onboarding-assets.md`

## OMX best-practice notes
- Keep task-specific planning files task-scoped by slug.
- Keep PRD + test spec as the minimum gated pair.
- Keep execution slicing separate from the PRD so implementation can proceed incrementally.
- Avoid stale generic open-questions files; resolved questions should be folded into the consensus plan.

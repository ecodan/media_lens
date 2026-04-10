# Partition 3 Checklist: Run Evals & Select Model

**Status**: Ready for manual execution  
**Branch**: feat/run-and-select  
**Estimated duration**: 3-5 hours (includes eval runtime)

## What's Ready

✅ **Partition 1 Complete**
- `eval/prepare_dataset.py` — dataset preparation script
- 25 headline extraction scenarios (HTML → golden extracted JSON)
- 25 interpretation scenarios (articles → golden interpreted output, 14 with references)
- 25 daily summary scenarios (articles → golden prose summary)
- `eval/README.md` — instructions for using the harness

✅ **Partition 2 Complete**
- Three gavel-ai evaluations configured:
  - `media-lens-headline-extraction` (3 judges)
  - `media-lens-interpretation` (5 judges)
  - `media-lens-daily-summary` (3 judges)
- All evals wired with 4 model variants:
  - `gemini-2.5-flash` (baseline)
  - `gemini-3-flash` (primary candidate)
  - `claude-haiku` (candidate)
  - `gemini-3-pro` (fallback)
- Judges configured with hard gates and quality metrics
- Scenario files symlinked and ready

## Partition 3 Tasks

Follow these tasks in order. Check each off as you complete it.

### Pre-flight: Resolve Open Questions

- [ ] **Confirm Vertex AI model version strings** — visit Vertex AI Model Garden and confirm exact model versions:
  - `gemini-3.0-flash-001` ← is this correct?
  - `gemini-3.0-pro-001` ← is this correct?
  - Update agents.json in all three evals if versions differ

### Run Evaluations

- [ ] **Set environment**:
  ```bash
  export VERTEX_AI_PROJECT_ID=medialens
  export VERTEX_AI_LOCATION=us-central1
  export ANTHROPIC_API_KEY=<your-key>
  ```

- [ ] **From gavel-ai project, run headline-extraction eval**:
  ```bash
  cd /path/to/gavel-ai
  gavel oneshot run --eval media-lens-headline-extraction
  # Wait for completion, then review report at:
  # .gavel/evaluations/media-lens-headline-extraction/runs/*/report.html
  ```

- [ ] **Run interpretation eval**:
  ```bash
  gavel oneshot run --eval media-lens-interpretation
  # Review: .gavel/evaluations/media-lens-interpretation/runs/*/report.html
  ```

- [ ] **Run daily-summary eval**:
  ```bash
  gavel oneshot run --eval media-lens-daily-summary
  # Review: .gavel/evaluations/media-lens-daily-summary/runs/*/report.html
  ```

### Review Results & Fill eval-spec.md

- [ ] **Open all three HTML reports** and record per-model, per-task metrics in a spreadsheet or text doc. For each model and task:
  - Schema/Completeness % (hard gate threshold)
  - Format % (hard gate threshold)
  - Hallucination / Faithfulness (hard gate / monitor)
  - Quality (GEval) score (monitor)
  - **Pass**: ✓ or ✗ based on hard gates

- [ ] **Fill `.cicadas/active/model-upgrade-eval/eval-spec.md` section 8** (Results table):
  ```markdown
  | **Model** | **Task** | **Schema/Completeness** | **Format** | **Hallucination** | **Quality (GEval)** | **Pass** |
  |-----------|----------|------------------------|------------|-------------------|---------------------|---------|
  | gemini-2.5-flash | Headline | 98% | — | 2% | 8.2/10 | ✓ |
  | gemini-2.5-flash | Interpretation | — | 95% | — | 7.9/10 | ✓ |
  | ...
  ```

### Select Winning Model

- [ ] **Apply hard-gate filter**: Identify which models pass ALL hard gates on ALL tasks
  - Hard gates: schema ≥95%, completeness ≥90%, format ≥90%, hallucination ≤5%
  - If no model passes all gates: escalate (see eval-spec section 9 exit criteria)

- [ ] **Compare quality scores** among passing models
  - Select the model with the highest average GEval quality across all tasks
  - Expected winner: likely `gemini-3-pro` or `claude-haiku`, assuming `gemini-3-flash` still has hallucinations

- [ ] **Fill eval-spec.md section 9** (Exit Criteria) with decision and rationale:
  ```markdown
  ## 9) Exit Criteria

  **Selected Model:** {model-name}
  
  **Rationale:** {model} passes all hard gates with the following metrics:
  - Headline extraction: schema 97%, hallucination 1%, quality 8.5/10
  - Interpretation: completeness 92%, format 93%, quality 8.2/10
  - Daily summary: format 91%, coherence 8.0/10
  
  This exceeds the gemini-2.5-flash baseline on quality (avg 8.0 vs 7.9) while meeting all safety gates.
  ```

### Update Production Code

- [ ] **Update `src/media_lens/common.py`**:
  ```python
  VERTEX_AI_MODEL: str = "{selected-model-version}"
  # e.g., "gemini-3.0-pro-001" or "claude-haiku-4-5-20251001"
  ```

- [ ] **If claude-haiku is selected** (Anthropic), also update:
  - `src/media_lens/common.py`: `AI_PROVIDER = "claude"` (or verify it's configurable via env)
  - `docker-compose.yml` / `docker-compose.local.yml`: add `AI_PROVIDER: claude` to env
  - `startup-script.sh`: ensure it sets `AI_PROVIDER=claude`
  - Verify `ANTHROPIC_API_KEY` is in GCP Secret Manager

- [ ] **Smoke test** the new model:
  ```bash
  python -m src.media_lens.runner run -s extract --sites www.bbc.com -j jobs/{recent_job_dir}
  # Verify:
  # - No errors in logs
  # - Output files are valid JSON
  # - Headlines/interpretations look reasonable
  ```

### Finalize & Merge

- [ ] **Update eval-spec.md section 10** (Wrap-Up):
  ```markdown
  **Summary:** Completed full evaluation of 4 model candidates across 3 LLM tasks using 75 total scenarios (25 per task). {selected-model} was selected based on hard-gate compliance and quality metrics. Smoke test on production pipeline passed.
  
  **Reviewers:** [Dan — approved]
  ```

- [ ] **Commit all changes**:
  ```bash
  git add src/media_lens/common.py docker-compose.yml docker-compose.local.yml startup-script.sh .cicadas/active/model-upgrade-eval/eval-spec.md
  git commit -m "feat(model-upgrade): select {selected-model} replacement for gemini-2.5-flash

  Run full eval on all 3 LLM tasks across 4 model candidates using gavel-ai.
  
  Results: {selected-model} passes all hard gates and exceeds baseline quality.
  
  - Update VERTEX_AI_MODEL in common.py
  - Update AI_PROVIDER if switching to Claude
  - Smoke test on production pipeline: passed
  - Fill eval-spec.md with results
  
  Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
  ```

- [ ] **Push branch**:
  ```bash
  git push origin feat/run-and-select
  ```

- [ ] **Open PR** from feat/run-and-select to initiative/model-upgrade-eval:
  ```bash
  gh pr create --base initiative/model-upgrade-eval --title "Partition 3: Model selection (eval results + deployment)" --body "$(cat <<'EOF'
  ## Summary
  
  Completed full evaluation harness for model upgrade initiative.
  
  Results: {selected-model} selected as replacement for gemini-2.5-flash
  
  - Hard gates: ✓ all passed
  - Quality: ✓ exceeds baseline
  - Smoke test: ✓ passed
  - Deployment: ✓ ready
  
  Eval spec (section 8-10) filled with results, decision rationale, and wrap-up.
  
  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  EOF
  )"
  ```

- [ ] **Merge PR** once approved

- [ ] **Back on master, run final integration test**:
  ```bash
  python -m src.media_lens.runner run -s harvest extract --sites www.bbc.com
  # Full pipeline with new model should complete without errors
  ```

## Notes

- **Eval runtime**: Expect 1-2 hours per eval depending on API rate limits. Run all 3 in parallel if possible, or sequentially if resource-constrained.
- **Cost**: Estimate ~$10-20 for full eval run (4 models × 25 scenarios × 3 tasks with judge LLM calls).
- **Fallback**: If all candidates fail hard gates, escalate to `gemini-3-pro` or contact Google for timeline extension.
- **Success metric**: New model should pass all hard gates while maintaining or improving baseline quality.

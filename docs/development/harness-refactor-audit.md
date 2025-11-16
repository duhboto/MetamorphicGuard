# Harness Refactoring Audit

This document tracks the migration from backward compatibility wrappers in `harness.py` to direct imports from refactored modules.

## Call Sites Audit

### Direct `run_eval()` callers:
1. `metamorphic_guard/api.py` - line 756
2. `metamorphic_guard/cli/evaluate.py` - line 15 (import)
3. `metamorphic_guard/llm_harness.py` - line 9 (import), line 297 (usage)
4. `metamorphic_guard/cli/stability.py` - line 13 (import)
5. `metamorphic_guard/stability_audit.py` - line 14 (import)
6. `tests/test_distributed_integration.py` - line 14 (import)
7. `tests/test_html_report.py` - line 11 (import)
8. `tests/test_benchmarks.py` - line 13 (import)
9. `tests/test_junit_report.py` - line 9 (import)
10. `tests/test_queue_e2e.py` - line 10 (import)
11. `tests/test_plugin_contract.py` - line 9 (import)
12. `demo_project/src/run_demo.py` - line 13 (import)
13. `fairness_guard_project/src/fairness_guard/runner.py` - line 10 (import)
14. `ranking_guard_project/src/ranking_guard/runner.py` - line 12 (import)
15. `pytest_metamorphic/plugin.py` - line 13 (import)

### Wrapper function callers:
1. `tests/test_harness.py`:
   - `_collect_metrics` - line 11 (import), used in tests
   - `_evaluate_results` - line 16 (import), used in tests
   - `_summarize_llm_results` - line 17 (import), used in tests
   - `_compute_bootstrap_ci` - line 12 (import)
   - `_compute_delta_ci` - line 13 (import)
   - `_compute_relative_risk` - line 14 (import)
   - `_compose_llm_metrics` - line 15 (import)

2. `tests/test_statistical_simulations.py`:
   - `_compute_delta_ci` - line 12 (import)
   - `_estimate_power` - line 12 (import)

3. `tests/test_confidence_intervals.py`:
   - `_compute_delta_ci` - line 5 (import)

4. `metamorphic_guard/harness.py` (internal usage):
   - `_prepare_execution_plan` - line 396
   - `_execute_implementations` - line 455
   - `_summarize_llm_results` - lines 469, 470
   - `_compute_paired_stats_new` - line 504
   - `_compute_trust_scores` - lines 529, 530
   - `_estimate_power_new` - line 703
   - `_collect_metrics_new` - line 746
   - `_evaluate_results_new` - line 958 (wrapper)

## Migration Plan

### Step 1: Update imports in test files
- `tests/test_harness.py` - migrate to `harness.statistics`, `harness.reporting`
- `tests/test_statistical_simulations.py` - migrate to `harness.statistics`
- `tests/test_confidence_intervals.py` - migrate to `harness.statistics`

### Step 2: Update imports in main modules
- `metamorphic_guard/api.py` - update `run_eval` import
- `metamorphic_guard/cli/evaluate.py` - update `run_eval` import
- `metamorphic_guard/llm_harness.py` - update `run_eval` import

### Step 3: Move `run_eval()` to `harness/evaluation.py`
- Create new module `harness/evaluation.py`
- Move `run_eval()` implementation
- Update all imports

### Step 4: Update `harness.py` to use new modules directly
- Replace wrapper calls with direct imports
- Remove wrapper functions

### Step 5: Update example projects
- Update imports in demo and reference projects

## Status

- [x] Audit complete
- [ ] Migration in progress
- [ ] All tests passing
- [ ] Wrappers removed




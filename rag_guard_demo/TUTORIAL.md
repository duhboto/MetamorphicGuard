# RAG Guard Tutorial

This tutorial walks you through setting up a guard for a RAG system.

## 1. Define the Task

We define a `TaskSpec` that generates queries and retrieves documents from a knowledge base.
In `src/demo_task.py`, `gen_inputs` simulates the retrieval step, returning `(query, docs)`.

## 2. Add Guards (Properties)

We add two critical properties for RAG:

```python
Property(check=check_citations, description="Citations must be valid and present")
Property(check=check_attribution, description="Content must be attributed to sources")
```

These use the built-in `CitationVerificationJudge` and `AttributionJudge`.

## 3. Add Robustness Checks (Metamorphic Relations)

We want our RAG system to be robust to the order of retrieved documents.
We use `ContextReorderMutant` (simulated manually in `apply_context_reorder` for structured inputs) to shuffle the docs.
We expect the output to be `equal` (assuming stable citation IDs) or at least properties should hold.

## 4. Implementations

-   **Baseline**: A naive implementation that might just concat text or hallucinate.
-   **Candidate**: An improved implementation that checks document IDs and formats answers with "According to Source [ID]...".

## 5. Run Evaluation

Run `python rag_guard_demo/run_demo.py`.
The `metamorphic_guard` harness runs both implementations on the same inputs (and transformed inputs).
It calculates pass rates and the delta.

## 6. Analyze Results

The generated report `rag_guard_demo/reports/rag_demo_report.json` contains detailed logs of every test case, including any violations.
Use this to debug why the baseline fails (e.g., missing citations) and verify the candidate succeeds.


# RAG Guard Demo Project

This project demonstrates how to use **Metamorphic Guard** to evaluate Retrieval-Augmented Generation (RAG) systems. It focuses on verifying citations, attribution, and robustness to context reordering.

## Features Demonstrated

-   **RAG-Specific Judges**:
    -   `CitationVerificationJudge`: Verifies that `[1]` style citations match the provided source documents.
    -   `AttributionJudge`: Checks that the answer contains attribution phrases (e.g., "According to...") and that the content overlaps with the cited source.
-   **RAG-Specific Metamorphic Relations**:
    -   `ContextReorderMutant`: Ensures that shuffling the order of retrieved documents does not change the semantic answer or break citations (by using stable ID-based citations).
-   **Custom Task Specification**: Defines a generator for queries and mock retrieved documents.

## Project Structure

-   `src/rag_impl.py` (split into `baseline.py` and `candidate.py`): Mock RAG implementations.
    -   **Baseline**: Often hallucinates, misses citations, or fails to attribute sources.
    -   **Candidate**: Robustly cites sources using IDs and uses attribution phrases.
-   `src/demo_task.py`: The `TaskSpec` definition including judges and MRs.
-   `run_demo.py`: Script to run the evaluation and generate a report.
-   `knowledge_base.json`: A small set of mock documents used for retrieval.

## How to Run

```bash
python rag_guard_demo/run_demo.py
```

## Expected Output

The evaluation compares the Baseline (prone to errors) against the Candidate (robust). You should see a result similar to:

```
Decision: Adopt
Reason: meets_gate
Baseline Pass Rate: 0.16
Candidate Pass Rate: 1.00
Delta: 0.84
```

This confirms that the Candidate implementation correctly handles citations and attribution, satisfying the "RAG Guard" policies.


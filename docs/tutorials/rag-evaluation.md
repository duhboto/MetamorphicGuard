# Evaluating RAG Systems with Metamorphic Guard

This tutorial guides you through setting up a comprehensive evaluation pipeline for a Retrieval-Augmented Generation (RAG) system using Metamorphic Guard.

## 1. Define Your RAG Task

First, define the task specification. For RAG, inputs are typically `(question, context)`.

```python
# my_rag_task.py
from metamorphic_guard import task, Spec, MetamorphicRelation
from metamorphic_guard.rag_guards import add_irrelevant_context, remove_relevant_context

@task("rag_qa")
def rag_spec():
    return Spec(
        gen_inputs=my_input_generator,
        properties=[],  # Or use LLM-as-Judge properties
        relations=[
            MetamorphicRelation(
                name="robustness_noise",
                transform=add_irrelevant_context,
                expect="equal",  # Answer should not change
                description="Adding irrelevant noise should not affect the answer."
            ),
            MetamorphicRelation(
                name="faithfulness_context",
                transform=remove_relevant_context,
                expect="not_equal",  # Answer SHOULD change (or become 'I don't know')
                description="Removing relevant context should break the answer."
            ),
        ],
        equivalence=llm_semantic_equivalence  # Use LLM to compare answers
    )

def my_input_generator(n, seed):
    # Return list of (question, context) tuples
    return [
        ("What is the capital of France?", "Paris is the capital of France."),
        ("Who wrote Hamlet?", "Shakespeare wrote Hamlet."),
        # ... load from dataset ...
    ]

def llm_semantic_equivalence(a, b):
    # Call LLM to check if 'a' and 'b' have same meaning
    # Return True/False
    return True 
```

## 2. Configure the Evaluator

Create a `config.toml` to define execution parameters and the LLM judge.

```toml
# config.toml
[evaluation]
task_name = "rag_qa"
n = 50
timeout_s = 10.0

[dispatcher]
type = "local"
workers = 4

[executor]
type = "openai"
model = "gpt-4"  # Your RAG system model

# Use LLM-as-Judge for equivalence checking inside the task spec
# (Implementation detail: equivalence function in python code uses this)
```

## 3. Run Evaluation

Execute the evaluation comparing a baseline implementation to a candidate.

```bash
mg evaluate \
  --task rag_qa \
  --baseline src/rag_v1.py \
  --candidate src/rag_v2.py \
  --config config.toml \
  --report rag_report.json
```

## 4. Analyze Results

Generate an HTML report to visualize performance.

```bash
mg report rag_report.json --output rag_report.html
```

The report will show:
- **Pass Rate**: How often the candidate satisfied the RAG relations.
- **Robustness**: Did adding noise change the answer?
- **Faithfulness**: Did removing context successfully break the answer? (If the answer remained the same without context, it suggests hallucination/prior knowledge reliance instead of context usage).

## 5. CI/CD Integration

Use the provided GitHub Actions or GitLab CI templates (`templates/ci/`) to run this evaluation automatically on every pull request.


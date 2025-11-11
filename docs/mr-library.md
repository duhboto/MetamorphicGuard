# Metamorphic Relation Library

This document catalogs metamorphic relations (MRs) organized by category, with examples, rationale, and references to relevant literature. Use this guide to select appropriate MRs for your domain and author new ones.

## Table of Contents

- [Permutation Invariance](#permutation-invariance)
- [Monotonicity](#monotonicity)
- [Scale Invariance](#scale-invariance)
- [Feature Invariance](#feature-invariance)
- [Noise Invariance](#noise-invariance)
- [Fairness & Symmetry](#fairness--symmetry)
- [RAG & Vector Operations](#rag--vector-operations)
- [Idempotence](#idempotence)
- [Equivalence Transformations](#equivalence-transformations)

---

## Permutation Invariance

**Category**: `permutation_invariance`

**Rationale**: Reordering inputs that should be treated equivalently should not change outputs. This catches bugs where order-dependent logic leaks into order-independent domains.

### Examples

**Top-K Selection**:
```python
MetamorphicRelation(
    name="permute_input",
    transform=lambda L, k: (shuffled(L), k),
    category="permutation_invariance",
    description="Permutation of input list should not change top-k result",
)
```

**Fairness - Applicant Shuffling**:
```python
MetamorphicRelation(
    name="shuffle_applicants",
    transform=lambda applicants: shuffled(applicants),
    category="permutation_invariance",
    description="Shuffling applicant order should not change approvals",
)
```

**Use Cases**: Ranking algorithms, fairness checks, set operations, aggregation functions.

**References**:
- Chen et al. (2018). "Metamorphic Testing: A Review of Challenges and Opportunities" - discusses permutation as a fundamental MR pattern.
- Segura et al. (2016). "A Survey on Metamorphic Testing" - catalogs permutation MRs across domains.

---

## Monotonicity

**Category**: `monotonicity`

**Rationale**: Increasing inputs in a relevant dimension should produce non-decreasing (or non-increasing) outputs. Violations indicate incorrect handling of ordering relationships.

### Examples

**Credit Scoring**:
```python
MetamorphicRelation(
    name="increase_income",
    transform=lambda applicant: applicant.with_income(applicant.income * 1.1),
    category="monotonicity",
    description="Increasing income should not decrease approval probability",
)
```

**Ranking - Score Preservation**:
```python
MetamorphicRelation(
    name="boost_relevance",
    transform=lambda query, docs: (query, [d.with_score(d.score * 1.2) for d in docs]),
    category="monotonicity",
    description="Increasing document relevance scores should preserve or improve ranking",
)
```

**Use Cases**: Credit approval, recommendation systems, ranking algorithms, pricing models.

**References**:
- Zhang et al. (2019). "Metamorphic Testing for Machine Learning: A Case Study" - applies monotonicity MRs to ML models.

---

## Scale Invariance

**Category**: `scale_invariance`

**Rationale**: Scaling inputs by positive constants should not change relative outputs. Useful for catching normalization bugs or unit conversion errors.

### Examples

**Fairness - Currency Scaling**:
```python
MetamorphicRelation(
    name="scale_currency",
    transform=lambda applicant: applicant.scale_features(income_multiplier=1.5, debt_multiplier=1.5),
    category="scale_invariance",
    description="Scaling monetary features proportionally should not affect outcomes",
)
```

**Use Cases**: Financial models, feature normalization, unit conversions.

**References**:
- Segura et al. (2016). "A Survey on Metamorphic Testing" - discusses scale invariance in numerical algorithms.

---

## Feature Invariance

**Category**: `feature_invariance`

**Rationale**: Adding uninformative or redundant features should not change outputs. Detects overfitting or incorrect feature handling.

### Examples

**Fairness - Uninformative Features**:
```python
MetamorphicRelation(
    name="inject_uninformative_feature",
    transform=lambda applicant: applicant.with_feature("random_noise", random_value()),
    category="feature_invariance",
    description="Adding uninformative features should not change approvals",
)
```

**Use Cases**: Machine learning models, feature engineering, data preprocessing.

**References**:
- Zhang et al. (2019). "Metamorphic Testing for Machine Learning" - discusses feature invariance for ML systems.

---

## Noise Invariance

**Category**: `noise_invariance`

**Rationale**: Adding noise below a threshold should not affect outputs. Useful for testing robustness to irrelevant perturbations.

### Examples

**Top-K Selection**:
```python
MetamorphicRelation(
    name="add_noise_below_min",
    transform=lambda L, k: (L + [min(L) - 1] * 5, k),
    category="noise_invariance",
    description="Adding noise below kth element should not affect top-k result",
)
```

**Use Cases**: Ranking algorithms, filtering operations, threshold-based decisions.

**References**:
- Chen et al. (2018). "Metamorphic Testing: A Review" - discusses noise injection as a testing strategy.

---

## Fairness & Symmetry

**Category**: `fairness_symmetry`

**Rationale**: Swapping protected attributes or symmetric groups should not change outcomes. Critical for fairness testing.

### Examples

**Group Label Swaps**:
```python
MetamorphicRelation(
    name="swap_protected_groups",
    transform=lambda applicants: swap_group_labels(applicants, "group_A", "group_B"),
    category="fairness_symmetry",
    description="Swapping protected group labels should not change relative approval rates",
)
```

**Counterfactual Neutrality**:
```python
MetamorphicRelation(
    name="counterfactual_swap",
    transform=lambda applicant: applicant.with_protected_attribute(opposite_value()),
    category="fairness_symmetry",
    description="Changing protected attribute alone should not flip decision (under counterfactual fairness)",
)
```

**Use Cases**: Credit approval, hiring systems, loan decisions, any system with protected attributes.

**References**:
- Kusner et al. (2017). "Counterfactual Fairness" - introduces counterfactual fairness framework.
- Dwork et al. (2012). "Fairness Through Awareness" - discusses group fairness metrics.

---

## RAG & Vector Operations

**Category**: `rag_invariance`

**Rationale**: RAG systems should be invariant to citation order, context chunk order, and equivalent paraphrases.

### Examples

**Citation Order Invariance**:
```python
MetamorphicRelation(
    name="shuffle_citations",
    transform=lambda prompt: shuffle_citation_order(prompt),
    category="rag_invariance",
    description="Shuffling citation order should not change answer quality",
)
```

**Context Chunk Reordering**:
```python
MetamorphicRelation(
    name="reorder_context",
    transform=lambda prompt: reorder_context_chunks(prompt),
    category="rag_invariance",
    description="Reordering context chunks should not change answer",
)
```

**Paraphrase Equivalence**:
```python
MetamorphicRelation(
    name="paraphrase_query",
    transform=lambda query: paraphrase(query),
    category="rag_invariance",
    description="Paraphrasing the query should produce equivalent answers",
)
```

**Use Cases**: Retrieval-augmented generation, question answering, document search.

**References**:
- MORTAR (2023). "Metamorphic Testing for RAG Systems" - applies MRs to RAG pipelines.
- MeTMaP (2024). "Metamorphic Testing for Machine Learning Pipelines" - discusses RAG-specific MRs.

---

## Idempotence

**Category**: `idempotence`

**Rationale**: Applying an operation twice should produce the same result as applying it once.

### Examples

**Deduplication**:
```python
MetamorphicRelation(
    name="double_dedup",
    transform=lambda items: deduplicate(deduplicate(items)),
    category="idempotence",
    description="Deduplicating twice should equal deduplicating once",
)
```

**Use Cases**: Deduplication, normalization, caching operations.

**References**:
- Segura et al. (2016). "A Survey on Metamorphic Testing" - catalogs idempotence MRs.

---

## Equivalence Transformations

**Category**: `equivalence_transformation`

**Rationale**: Applying mathematically equivalent transformations should produce equivalent outputs.

### Examples

**Query Synonymy**:
```python
MetamorphicRelation(
    name="synonym_expansion",
    transform=lambda query: expand_synonyms(query),
    category="equivalence_transformation",
    description="Expanding synonyms should produce equivalent search results",
)
```

**Use Cases**: Search engines, query processing, text matching.

**References**:
- IR axioms (e.g., score-shift invariance, document duplication invariance) - foundational IR principles that map to MRs.

---

## Best Practices

### Choosing MRs

1. **Domain Alignment**: Select MRs that reflect your domain's invariants (e.g., fairness MRs for credit systems).
2. **Coverage**: Aim for diverse MR categories to catch different failure modes.
3. **Preconditions**: Document when MRs apply (e.g., "only for deterministic algorithms").
4. **Performance**: Some MRs require re-running tests; balance coverage with runtime.

### Authoring New MRs

1. **Name Clearly**: Use descriptive names (e.g., `shuffle_applicants` not `mr1`).
2. **Categorize**: Assign appropriate category for reporting and analysis.
3. **Document**: Provide clear descriptions explaining the invariant.
4. **Test**: Verify MRs catch known bugs before deploying.

### Coverage Analysis

Reports include `relation_coverage` showing:
- Per-relation pass rates
- Per-category pass rates
- Failure counts

Use this to identify:
- Gaps in MR coverage (missing categories)
- Flaky MRs (inconsistent failures)
- Domain-specific failure patterns

---

## References

- Chen, T. Y., et al. (2018). "Metamorphic Testing: A Review of Challenges and Opportunities." *ACM Computing Surveys*.
- Segura, S., et al. (2016). "A Survey on Metamorphic Testing." *IEEE Transactions on Software Engineering*.
- Zhang, J., et al. (2019). "Metamorphic Testing for Machine Learning: A Case Study." *ICST*.
- Kusner, M. J., et al. (2017). "Counterfactual Fairness." *NIPS*.
- Dwork, C., et al. (2012). "Fairness Through Awareness." *ITCS*.
- MORTAR (2023). "Metamorphic Testing for RAG Systems." *Workshop on Testing ML Systems*.
- MeTMaP (2024). "Metamorphic Testing for Machine Learning Pipelines." *ICSE*.

---

## See Also

- [First PR Gate Tutorial](first-pr-gate-tutorial.md) - Step-by-step guide to creating your first MRs
- [Policy Documentation](policies.md) - Configuring adoption gates
- [Report Schema](../schemas/report.schema.json) - Understanding coverage reports


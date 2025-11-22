# Authoring High-Quality Metamorphic Relations

This guide provides comprehensive guidance and guardrails for authoring effective metamorphic relations (MRs) that catch real bugs and provide actionable insights.

## Table of Contents

- [Principles of Effective MRs](#principles-of-effective-mrs)
- [Design Patterns](#design-patterns)
- [Common Pitfalls & Anti-Patterns](#common-pitfalls--anti-patterns)
- [Quality Checklist](#quality-checklist)
- [Validation & Testing](#validation--testing)
- [Domain-Specific Guidance](#domain-specific-guidance)

## Principles of Effective MRs

### 1. Encode Domain Invariants

**Principle**: MRs should express invariants that hold in your problem domain, not arbitrary transformations.

**✅ Good**:
```python
# Ranking: Permuting input documents shouldn't change ranking
MetamorphicRelation(
    name="permute_documents",
    transform=lambda query, docs: (query, shuffled(docs)),
    expect="equal",
    category="permutation_invariance",
    description="Reordering documents should not affect ranking (order-independent scoring)"
)
```

**❌ Bad**:
```python
# Arbitrary transformation without domain justification
MetamorphicRelation(
    name="reverse_input",
    transform=lambda query, docs: (query[::-1], docs),  # Why reverse query?
    expect="equal",
    description="Reversing query characters"  # No domain rationale
)
```

### 2. Make Transformations Observable

**Principle**: The transformation should produce outputs that can be meaningfully compared.

**✅ Good**:
```python
# Credit scoring: Increasing income should improve score
MetamorphicRelation(
    name="increase_income",
    transform=lambda applicant: applicant.with_income(applicant.income * 1.1),
    expect="increasing",  # Clear expectation
    category="monotonicity"
)
```

**❌ Bad**:
```python
# Vague expectation that's hard to verify
MetamorphicRelation(
    name="modify_applicant",
    transform=lambda applicant: applicant.with_feature("x", random_value()),
    expect="similar",  # Too vague: what does "similar" mean?
)
```

### 3. Control Non-Determinism

**Principle**: If your algorithm is stochastic, control randomness in MRs to ensure reproducibility.

**✅ Good**:
```python
def permute_with_seed(*args, rng=None):
    """Permute input using provided RNG for reproducibility."""
    if rng is None:
        import random
        rng = random.Random()
    items = list(args[0])
    rng.shuffle(items)
    return (tuple(items),) + args[1:]

MetamorphicRelation(
    name="permute_input",
    transform=permute_with_seed,
    expect="equal",
    accepts_rng=True,  # Use same RNG for both baseline and candidate
    category="permutation_invariance"
)
```

**❌ Bad**:
```python
# Non-reproducible: different random seeds for baseline vs candidate
MetamorphicRelation(
    name="permute_input",
    transform=lambda L: (shuffled(L),),  # Uses global random
    expect="equal"
)
```

### 4. Document Preconditions

**Principle**: Clearly document when MRs apply and what assumptions they make.

**✅ Good**:
```python
MetamorphicRelation(
    name="scale_features",
    transform=lambda applicant: applicant.scale_features(income_multiplier=1.5),
    expect="equal",
    category="scale_invariance",
    description="Scaling monetary features proportionally should not affect decisions. "
                "Assumes algorithm is scale-invariant (e.g., uses ratios, not absolute values). "
                "Does not apply if thresholds are hard-coded."
)
```

### 5. Balance Coverage and Runtime

**Principle**: More MRs catch more bugs, but also increase evaluation time. Prioritize high-signal MRs.

**Guidelines**:
- **High Priority**: Domain-specific invariants (e.g., fairness, monotonicity)
- **Medium Priority**: General transformations (e.g., permutation, noise)
- **Low Priority**: Edge cases, rarely-applicable transformations

## Design Patterns

### Pattern 1: Permutation Invariance

**When to Use**: Inputs that should be treated equivalently regardless of order.

**Pattern**:
```python
def permute_equivalence(*args, rng=None):
    """Permute order-independent inputs."""
    items = list(args[0])  # First arg is order-independent collection
    if rng:
        rng.shuffle(items)
    else:
        random.shuffle(items)
    return (tuple(items),) + args[1:]

MetamorphicRelation(
    name="permute_items",
    transform=permute_equivalence,
    expect="equal",
    accepts_rng=True,
    category="permutation_invariance"
)
```

**Examples**:
- Shuffling documents in ranking
- Permuting applicant order in fairness checks
- Reordering items in set operations

### Pattern 2: Monotonicity

**When to Use**: Increasing/decreasing inputs should produce non-decreasing/non-increasing outputs.

**Pattern**:
```python
def increase_feature(applicant, feature_name, multiplier=1.1):
    """Increase a monotonic feature."""
    current_value = getattr(applicant, feature_name)
    return applicant.with_feature(feature_name, current_value * multiplier)

MetamorphicRelation(
    name="increase_income",
    transform=lambda applicant: increase_feature(applicant, "income", 1.1),
    expect="increasing",  # Output should increase (or stay same)
    category="monotonicity"
)
```

**Examples**:
- Income vs credit score (higher income → higher score)
- Relevance score vs ranking position (higher score → better position)
- Quality metric vs recommendation (higher quality → included in recommendations)

### Pattern 3: Scale Invariance

**When to Use**: Scaling inputs by positive constants shouldn't change relative outputs.

**Pattern**:
```python
def scale_proportionally(applicant, multiplier=1.5):
    """Scale all features proportionally."""
    return applicant.scale_features(
        income_multiplier=multiplier,
        debt_multiplier=multiplier,
        assets_multiplier=multiplier
    )

MetamorphicRelation(
    name="scale_currency",
    transform=lambda applicant: scale_proportionally(applicant, 1.5),
    expect="equal",
    category="scale_invariance",
    description="Scaling all monetary features proportionally should not affect decisions"
)
```

**Examples**:
- Currency conversion (dollars → euros with same ratios)
- Feature normalization (multiplying all features by constant)
- Unit conversions (meters → kilometers)

### Pattern 4: Noise Invariance

**When to Use**: Adding irrelevant noise below a threshold shouldn't affect outputs.

**Pattern**:
```python
def add_dominated_noise(*args, rng=None):
    """Add noise that should be filtered out."""
    items = list(args[0])
    k = args[1]
    min_item = min(items)
    
    # Add noise below minimum (shouldn't affect top-k)
    noise = [min_item - 1] * 5
    if rng:
        rng.shuffle(noise)
    
    return (tuple(items + noise), k)

MetamorphicRelation(
    name="add_noise_below_threshold",
    transform=add_dominated_noise,
    expect="equal",
    accepts_rng=True,
    category="noise_invariance"
)
```

**Examples**:
- Adding low-scoring items to ranking (shouldn't affect top-k)
- Injecting irrelevant features (shouldn't affect predictions)
- Adding noise below detection threshold

### Pattern 5: Idempotence

**When to Use**: Applying operation twice should equal applying once.

**Pattern**:
```python
def double_operation(*args):
    """Apply operation twice."""
    first_result = original_function(*args)
    second_result = original_function(first_result)
    return (second_result,)

MetamorphicRelation(
    name="idempotence",
    transform=double_operation,
    expect="equal",
    category="idempotence"
)
```

**Examples**:
- Deduplication (dedup twice = dedup once)
- Normalization (normalize twice = normalize once)
- Caching (cache miss then hit = same result)

### Pattern 6: Fairness & Symmetry

**When to Use**: Swapping protected attributes shouldn't change relative outcomes.

**Pattern**:
```python
def swap_protected_groups(applicants, group_a, group_b):
    """Swap protected group labels."""
    swapped = []
    for app in applicants:
        if app.group == group_a:
            swapped.append(app.with_group(group_b))
        elif app.group == group_b:
            swapped.append(app.with_group(group_a))
        else:
            swapped.append(app)
    return (swapped,)

MetamorphicRelation(
    name="swap_protected_groups",
    transform=lambda applicants: swap_protected_groups(applicants, "A", "B"),
    expect="equal",  # Approval rates should be equal
    category="fairness_symmetry"
)
```

**Examples**:
- Gender swap in hiring decisions
- Race swap in credit approval
- Age group swap in recommendations

## Common Pitfalls & Anti-Patterns

### Anti-Pattern 1: Violating Domain Assumptions

**Problem**: MR assumes behavior that doesn't hold in your domain.

**❌ Example**:
```python
# Assumes all features are interchangeable
MetamorphicRelation(
    name="swap_features",
    transform=lambda applicant: applicant.swap("income", "age"),  # Nonsensical!
    expect="equal"
)
```

**✅ Fix**: Only swap truly equivalent features or use domain-specific swaps.

### Anti-Pattern 2: Ignoring Non-Determinism

**Problem**: MR doesn't control randomness, leading to flaky tests.

**❌ Example**:
```python
MetamorphicRelation(
    name="add_random_noise",
    transform=lambda x: (x + random.uniform(0, 0.1),),  # Different randomness each time!
    expect="equal"
)
```

**✅ Fix**: Use `accepts_rng=True` and provide RNG:
```python
def add_controlled_noise(x, rng=None):
    if rng is None:
        rng = random.Random()
    return (x + rng.uniform(0, 0.1),)

MetamorphicRelation(
    name="add_random_noise",
    transform=add_controlled_noise,
    accepts_rng=True
)
```

### Anti-Pattern 3: Vague Expectations

**Problem**: `expect="similar"` without defining similarity threshold.

**❌ Example**:
```python
MetamorphicRelation(
    name="add_small_noise",
    transform=lambda score: (score + 0.01,),
    expect="similar"  # How similar? What's the threshold?
)
```

**✅ Fix**: Use specific expectations or implement custom equivalence:
```python
# Option 1: Use "equal" if truly should be equal
MetamorphicRelation(
    name="add_noise_below_precision",
    transform=lambda score: (score + 1e-10,),  # Below floating-point precision
    expect="equal"
)

# Option 2: Use custom equivalence function
def fuzzy_equivalence(a, b):
    return abs(a - b) < 0.01

spec = Spec(
    ...,
    equivalence=fuzzy_equivalence
)
```

### Anti-Pattern 4: Overly Complex Transformations

**Problem**: Transformation does too much, making failures hard to diagnose.

**❌ Example**:
```python
def complex_transform(applicant):
    # Does 5 different things - which one caused failure?
    return applicant\
        .scale_features(1.2)\
        .add_noise()\
        .swap_groups()\
        .normalize()\
        .shuffle()

MetamorphicRelation(
    name="complex_transform",
    transform=lambda app: (complex_transform(app),)
)
```

**✅ Fix**: Split into focused MRs:
```python
# Separate MRs for each concern
relations = [
    MetamorphicRelation(name="scale_features", ...),
    MetamorphicRelation(name="add_noise", ...),
    MetamorphicRelation(name="swap_groups", ...),
]
```

### Anti-Pattern 5: Missing Preconditions

**Problem**: MR assumes conditions that aren't always true.

**❌ Example**:
```python
MetamorphicRelation(
    name="divide_by_income",
    transform=lambda applicant: applicant.with_score(
        applicant.score / applicant.income  # Fails if income == 0!
    ),
    expect="equal"
)
```

**✅ Fix**: Document preconditions or handle edge cases:
```python
def safe_divide(applicant, rng=None):
    if applicant.income == 0:
        return applicant  # Skip transformation
    return applicant.with_score(applicant.score / applicant.income)

MetamorphicRelation(
    name="divide_by_income",
    transform=lambda app: (safe_divide(app),),
    description="Scales by income. Only applies when income > 0."
)
```

## Quality Checklist

Use this checklist when authoring new MRs:

### Domain Alignment
- [ ] MR expresses a domain invariant (not arbitrary transformation)
- [ ] Rationale is documented in `description`
- [ ] Preconditions and assumptions are documented
- [ ] Category is appropriate (`category` field)

### Technical Correctness
- [ ] Transformation signature matches Spec input format
- [ ] Uses `accepts_rng=True` if transformation is non-deterministic
- [ ] `expect` value is specific ("equal", "increasing", etc.) not vague
- [ ] Edge cases are handled (empty inputs, null values, etc.)

### Observable & Testable
- [ ] Output can be meaningfully compared to original
- [ ] Expected relationship is clear and verifiable
- [ ] Failure messages will be actionable

### Performance
- [ ] Transformation is efficient (doesn't add significant overhead)
- [ ] MR is prioritized appropriately (high-signal MRs first)

### Documentation
- [ ] `name` is descriptive and unique
- [ ] `description` explains the invariant and when it applies
- [ ] `category` is set for reporting and analysis
- [ ] Examples are provided if complex

## Validation & Testing

### Built-in Validation

Metamorphic Guard validates MRs automatically:

```bash
# Validate MRs in a task
metamorphic-guard mr validate my_task

# Check for common issues
metamorphic-guard mr lint my_task
```

**Checks performed**:
- Signature correctness (transform accepts correct arguments)
- Missing metadata (description, category)
- Type compatibility
- Common anti-patterns

### Manual Testing

**Test MRs independently before adding to Spec**:

```python
def test_permutation_mr():
    """Test that permutation MR works correctly."""
    relation = MetamorphicRelation(
        name="permute_input",
        transform=lambda L: (shuffled(L),),
        expect="equal"
    )
    
    # Test with known inputs
    original = ([1, 2, 3, 4, 5],)
    transformed = relation.transform(*original)
    
    # Original and transformed should produce equal outputs
    original_output = my_function(*original)
    transformed_output = my_function(*transformed)
    
    assert original_output == transformed_output, \
        "Permutation MR violated!"
```

### Property-Based Testing

Use Hypothesis or similar to test MRs with diverse inputs:

```python
from hypothesis import given, strategies as st

@given(items=st.lists(st.integers(), min_size=1, max_size=100))
def test_permutation_mr_property(items):
    """Property-based test for permutation MR."""
    original = (tuple(items),)
    transformed = relation.transform(*original, rng=random.Random(42))
    
    # Both should produce equivalent outputs
    original_output = my_function(*original)
    transformed_output = my_function(*transformed)
    
    assert equivalent(original_output, transformed_output)
```

## Domain-Specific Guidance

### Ranking Systems

**Key Invariants**:
1. **Permutation**: Reordering input shouldn't change ranking
2. **Monotonicity**: Higher relevance scores → better positions
3. **Noise Invariance**: Adding low-scoring items shouldn't affect top-k
4. **Scale Invariance**: Scaling scores shouldn't change relative order

**Recommended MRs**:
```python
relations = [
    # Permutation (order independence)
    MetamorphicRelation(
        name="permute_documents",
        transform=lambda query, docs: (query, shuffled(docs)),
        expect="equal",
        category="permutation_invariance"
    ),
    
    # Monotonicity (score preservation)
    MetamorphicRelation(
        name="boost_relevance",
        transform=lambda query, docs: (query, [d.with_score(d.score * 1.2) for d in docs]),
        expect="increasing",
        category="monotonicity"
    ),
    
    # Noise invariance (top-k stability)
    MetamorphicRelation(
        name="add_dominated_items",
        transform=lambda query, docs, k: (
            query,
            docs + [Document(score=min(d.score for d in docs) - 1)] * 10,
            k
        ),
        expect="equal",
        category="noise_invariance"
    ),
]
```

### Fairness & Credit Systems

**Key Invariants**:
1. **Symmetry**: Swapping protected groups shouldn't change relative rates
2. **Monotonicity**: Higher income/credit → higher approval probability
3. **Scale Invariance**: Proportional scaling shouldn't affect decisions

**Recommended MRs**:
```python
relations = [
    # Fairness (group swap)
    MetamorphicRelation(
        name="swap_protected_groups",
        transform=lambda applicants: swap_groups(applicants, "A", "B"),
        expect="equal",  # Equal approval rates
        category="fairness_symmetry"
    ),
    
    # Monotonicity (income)
    MetamorphicRelation(
        name="increase_income",
        transform=lambda applicant: applicant.with_income(applicant.income * 1.1),
        expect="increasing",
        category="monotonicity"
    ),
    
    # Scale invariance (currency)
    MetamorphicRelation(
        name="scale_currency",
        transform=lambda applicant: applicant.scale_features(
            income_multiplier=1.5,
            debt_multiplier=1.5
        ),
        expect="equal",
        category="scale_invariance"
    ),
]
```

### LLM & RAG Systems

**Key Invariants**:
1. **Citation Order**: Reordering citations shouldn't change answer
2. **Context Order**: Reordering context chunks shouldn't change answer
3. **Paraphrase**: Paraphrased queries should produce equivalent answers

**Recommended MRs**:
```python
relations = [
    # Citation order invariance
    MetamorphicRelation(
        name="shuffle_citations",
        transform=lambda prompt: shuffle_citation_order(prompt),
        expect="equal",
        category="rag_invariance"
    ),
    
    # Context reordering
    MetamorphicRelation(
        name="reorder_context",
        transform=lambda prompt: reorder_context_chunks(prompt),
        expect="equal",
        category="rag_invariance"
    ),
    
    # Paraphrase equivalence
    MetamorphicRelation(
        name="paraphrase_query",
        transform=lambda query: paraphrase(query),
        expect="similar",  # Use semantic similarity
        category="equivalence_transformation"
    ),
]
```

## Advanced Techniques

### Chaining Relations

Combine multiple MRs into composite checks:

```python
from metamorphic_guard.specs import chain_relations

# Chain: first permute, then add noise
composite = chain_relations(
    "permute_and_noise",
    permutation_relation,
    noise_relation,
    description="Permute input then add noise - both should preserve output"
)
```

### Conditional Relations

Apply MRs only when preconditions hold:

```python
def conditional_transform(*args, rng=None):
    """Only transform if preconditions hold."""
    items = args[0]
    if len(items) < 2:
        return args  # Skip: need at least 2 items to permute
    
    # Apply transformation
    items_list = list(items)
    if rng:
        rng.shuffle(items_list)
    else:
        random.shuffle(items_list)
    return (tuple(items_list),) + args[1:]

MetamorphicRelation(
    name="permute_if_applicable",
    transform=conditional_transform,
    accepts_rng=True,
    description="Permutes input if there are at least 2 items"
)
```

## Resources

- **MR Library**: See `docs/mr-library.md` for catalog of MRs organized by category
- **Discovery Tool**: Use `metamorphic-guard mr discover <task>` for suggestions
- **Validation Tool**: Use `metamorphic-guard mr validate <task>` to check quality
- **Coverage Analysis**: Review reports for per-category pass rates

---

**Last Updated**: 2025-01-16  
**Version**: 3.3.4






"""
Metamorphic Guard: A Python library for comparing program versions using metamorphic testing.
"""

from .specs import task, Spec, Property, MetamorphicRelation, Metric
from .generators import gen_top_k_inputs
from .relations import permute_input, add_noise_below_min
from .stability import multiset_equal
from .monitoring import Monitor, LatencyMonitor
from .dispatch import Dispatcher

# Version management via setuptools_scm
try:
    from importlib.metadata import version

    __version__ = version("metamorphic_guard")
except Exception:
    # Fallback for development or if package not installed
    try:
        from ._version import __version__  # type: ignore
    except ImportError:
        __version__ = "dev"  # type: ignore


@task("top_k")
def top_k_spec() -> Spec:
    """Specification for the top_k task."""
    return Spec(
        gen_inputs=gen_top_k_inputs,
        properties=[
            Property(
                check=lambda out, L, k: len(out) == min(k, len(L)),
                description="Output length equals min(k, len(L))"
            ),
            Property(
                check=lambda out, L, k: sorted(out, reverse=True) == out,
                description="Output is sorted in descending order"
            ),
            Property(
                check=lambda out, L, k: all(x in L for x in out),
                description="All output elements are from input list"
            )
        ],
        relations=[
            MetamorphicRelation(
                name="permute_input",
                transform=permute_input,
                expect="equal",
                accepts_rng=True,
                category="permutation_invariance",
                description="Permutation of input list should not change top-k result",
            ),
            MetamorphicRelation(
                name="add_noise_below_min", 
                transform=add_noise_below_min,
                expect="equal",
                category="noise_invariance",
                description="Adding noise below kth element should not affect top-k result",
            )
        ],
        equivalence=multiset_equal,
        fmt_in=lambda args: f"L={args[0]}, k={args[1]}",
        fmt_out=lambda result: f"top_k={result}"
    )

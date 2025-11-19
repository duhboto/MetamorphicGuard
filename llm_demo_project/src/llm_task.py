"""
LLM Task Specification for the Demo.
"""

from metamorphic_guard.specs import task, Spec, Property, MetamorphicRelation
from metamorphic_guard.judges.builtin import LengthJudge, NoPIIJudge
from metamorphic_guard.mutants.builtin import ParaphraseMutant

# Define input generator
def gen_prompts(n: int, seed: int):
    """Generate n test prompts."""
    base_prompts = [
        "Summarize this article about AI safety.",
        "What is the sentiment of 'I love this product'?",
        "Explain quantum computing in simple terms.",
        "Write a poem about coding.",
        "Translate 'Hello world' to French."
    ]
    # Repeat list to fill n
    # Must return list of argument tuples
    return [(base_prompts[i % len(base_prompts)],) for i in range(n)]

def make_judge_property(judge, name):
    """Wrap an LLM judge as a Property."""
    def check(output, *args):
        # Handle both direct string output and executor result dict
        text = output
        if isinstance(output, dict) and "result" in output:
            text = output["result"]
        
        # Input is the first arg
        input_data = args[0] if args else None
        
        eval_result = judge.evaluate(text, input_data)
        return eval_result["pass"]
    
    return Property(
        check=check,
        description=f"Judge: {name}",
        mode="hard"
    )

@task("llm_demo")
def llm_demo_spec() -> Spec:
    return Spec(
        gen_inputs=gen_prompts,
        equivalence=lambda a, b: True, # Relaxed equivalence for demo
        properties=[
            # Wrapped Judges
            make_judge_property(LengthJudge(config={"max_chars": 200}), "Max Length 200"),
            make_judge_property(NoPIIJudge(), "No PII")
        ],
        relations=[
            # Robustness: Paraphrasing
            MetamorphicRelation(
                name="paraphrase_invariance",
                transform=ParaphraseMutant().transform,
                expect="equal", 
                description="Paraphrased input should yield consistent output structure"
            )
        ]
    )

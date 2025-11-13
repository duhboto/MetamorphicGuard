def baseline_callable(x):
    return {"value": float(x)}


def candidate_callable(x):
    return {"value": float(x) + 0.25}


def bad_candidate_callable(x):
    return {"value": float(x) - 1.0}


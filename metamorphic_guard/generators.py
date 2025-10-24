"""
Input generators for test cases.
"""

import random
from typing import List, Tuple


def gen_top_k_inputs(n: int, seed: int) -> List[Tuple[List[int], int]]:
    """
    Generate diverse test cases for top_k problem.
    
    Args:
        n: Number of test cases to generate
        seed: Random seed for reproducibility
        
    Returns:
        List of (L, k) tuples where L is a list of integers and k is the number to select
    """
    random.seed(seed)
    test_cases = []
    
    for _ in range(n):
        # Generate diverse test cases
        case_type = random.choice([
            'empty', 'single', 'duplicates', 'sorted_asc', 'sorted_desc', 
            'large_k', 'k_zero', 'negatives', 'extremes', 'random'
        ])
        
        if case_type == 'empty':
            L, k = [], 0
            
        elif case_type == 'single':
            L, k = [random.randint(-100, 100)], 1
            
        elif case_type == 'duplicates':
            # Create list with many duplicates
            base_val = random.randint(-50, 50)
            L = [base_val] * random.randint(3, 10) + [random.randint(-50, 50) for _ in range(random.randint(1, 5))]
            k = random.randint(1, len(L))
            
        elif case_type == 'sorted_asc':
            L = sorted([random.randint(-100, 100) for _ in range(random.randint(2, 20))])
            k = random.randint(1, len(L))
            
        elif case_type == 'sorted_desc':
            L = sorted([random.randint(-100, 100) for _ in range(random.randint(2, 20))], reverse=True)
            k = random.randint(1, len(L))
            
        elif case_type == 'large_k':
            L = [random.randint(-100, 100) for _ in range(random.randint(5, 15))]
            k = len(L)  # k equals list length
            
        elif case_type == 'k_zero':
            L = [random.randint(-100, 100) for _ in range(random.randint(1, 10))]
            k = 0
            
        elif case_type == 'negatives':
            L = [random.randint(-1000, -1) for _ in range(random.randint(3, 15))]
            k = random.randint(1, len(L))
            
        elif case_type == 'extremes':
            L = [random.choice([-10**6, -10**3, 0, 10**3, 10**6]) for _ in range(random.randint(3, 10))]
            k = random.randint(1, len(L))
            
        else:  # random
            L = [random.randint(-100, 100) for _ in range(random.randint(1, 20))]
            k = random.randint(0, len(L) + 2)  # Allow k > len(L)
        
        test_cases.append((L, k))
    
    return test_cases

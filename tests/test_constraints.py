import pytest
from constraints import (
    even_first_digit,
    exactly_two_repeats,
    semantic_contains_nasa_month,
    sample_constraints
)

def test_even_first_digit():
    # Test even first digit
    assert even_first_digit("2345") is True
    assert even_first_digit("0789") is True
    assert even_first_digit("4567") is True
    assert even_first_digit("8901") is True
    
    # Test odd first digit
    assert even_first_digit("1234") is False
    assert even_first_digit("3456") is False
    assert even_first_digit("5678") is False
    assert even_first_digit("9012") is False

def test_exactly_two_repeats():
    # Test valid cases - requires exactly 3 unique digits and at least one digit appears exactly twice
    assert exactly_two_repeats("1123") is True  # 1 appears twice, 3 unique digits (1,2,3)
    assert exactly_two_repeats("2244") is False  # Only 2 unique digits (2,4)
    assert exactly_two_repeats("3939") is False  # Only 2 unique digits (3,9)

    # More valid cases
    assert exactly_two_repeats("0112") is True  # 1 appears twice, 3 unique digits (0,1,2)
    assert exactly_two_repeats("2445") is True  # 4 appears twice, 3 unique digits (2,4,5)

    # Test invalid cases
    assert exactly_two_repeats("1234") is False  # No repeats (4 unique digits)
    assert exactly_two_repeats("1112") is False  # Only 2 unique digits (1,2)
    assert exactly_two_repeats("1111") is False  # Only 1 unique digit (1)
    assert exactly_two_repeats("1122") is False  # Only 2 unique digits (1,2)

def test_semantic_contains_nasa_month():
    # Test valid cases containing "07"
    assert semantic_contains_nasa_month("0712") is True
    assert semantic_contains_nasa_month("1207") is True
    assert semantic_contains_nasa_month("3074") is True
    assert semantic_contains_nasa_month("5607") is True
    
    # Test invalid cases not containing "07"
    assert semantic_contains_nasa_month("1234") is False
    assert semantic_contains_nasa_month("7012") is False  # Contains 70, not 07
    assert semantic_contains_nasa_month("0178") is False  # Contains 01, not 07
    assert semantic_contains_nasa_month("7890") is False

def test_sample_constraints():
    # Test that sample_constraints returns the correct number and types of constraints
    formal1, formal2, semantic = sample_constraints()
    
    # Check that formal1 and formal2 are different formal constraints
    assert formal1 != formal2
    assert formal1 in [even_first_digit, exactly_two_repeats]
    assert formal2 in [even_first_digit, exactly_two_repeats]
    
    # Check that semantic is a semantic constraint
    assert semantic == semantic_contains_nasa_month
"""
Test module for the audiobookshelf sensor component.

This module contains test cases for the camel_to_snake function used in the
audiobookshelf sensor component.
"""

from custom_components.audiobookshelf.sensor import camel_to_snake


def test_camel_to_snake_with_dict() -> None:
    """
    Test the camel_to_snake function with a dictionary input.

    This test verifies that the camel_to_snake function correctly converts
    dictionary keys from camelCase to snake_case format, including nested
    dictionaries.

    The test data includes:
    - A simple dictionary with a camelCase key
    - A nested dictionary with camelCase keys at both levels

    Expected behavior:
    - All dictionary keys should be converted from camelCase to snake_case
    - Dictionary values should remain unchanged
    - The nested structure should be preserved

    Returns:
        None

    Raises:
        AssertionError: If the camel_to_snake function output doesn't match
        expected output

    """
    data = {
        "camelCaseKey": "value",
        "nestedCamelCase": {"innerCamelCaseKey": "innerValue"},
    }
    expected = {
        "camel_case_key": "value",
        "nested_camel_case": {"inner_camel_case_key": "innerValue"},
    }
    assert camel_to_snake(data) == expected


def test_camel_to_snake_with_list_of_dicts() -> None:
    """
    Test the camel_to_snake function with a list of dictionaries.

    This test verifies that the camel_to_snake function correctly converts
    dictionary keys from camelCase to snake_case format, including nested
    dictionaries.

    The test data includes:
    - A list of dictionaries with camelCase keys

    Expected behavior:
    - All dictionary keys should be converted from camelCase to snake_case
    - Dictionary values should remain unchanged
    - The nested structure should be preserved

    Returns:
        None

    Raises:
        AssertionError: If the camel_to_snake function output doesn't match
        expected output

    """
    data = [{"camelCaseKey": "value"}, {"anotherCamelCaseKey": "anotherValue"}]
    expected = [{"camel_case_key": "value"}, {"another_camel_case_key": "anotherValue"}]
    assert camel_to_snake(data) == expected


def test_camel_to_snake_with_mixed_list() -> None:
    """
    Test the camel_to_snake function with a mixed list input.

    This test verifies that the camel_to_snake function correctly handles a complex
    nested structure containing both dictionaries and lists, where dictionary keys
    need to be converted from camelCase to snake_case format.

    The test data includes:
    - A dictionary with a camelCase key
    - A nested list containing a string and another dictionary with a camelCase key

    Expected behavior:
    - Dictionary keys should be converted from camelCase to snake_case
    - List items that are strings should remain unchanged
    - The structure of the input should be preserved

    Returns:
        None

    Raises:
        AssertionError: If the camel_to_snake function output doesn't match
        expected output

    """
    data = [
        {"camelCaseKey": "value"},
        ["nestedListCamelCase", {"innerCamelCaseKey": "innerValue"}],
    ]
    expected = [
        {"camel_case_key": "value"},
        ["nestedListCamelCase", {"inner_camel_case_key": "innerValue"}],
    ]
    assert camel_to_snake(data) == expected


def test_camel_to_snake_with_empty_dict() -> None:
    """
    Test the camel_to_snake function with an empty dictionary.

    This test verifies that the camel_to_snake function correctly handles
    empty dictionaries.

    The test data includes:
    - Empty dictionary

    Expected behavior:
    - Empty dictionary should be unchanged

    Returns:
        None

    Raises:
        AssertionError: If the camel_to_snake function output doesn't match
        expected output

    """
    data = {}
    expected = {}
    assert camel_to_snake(data) == expected


def test_camel_to_snake_with_empty_list() -> None:
    """
    Test the camel_to_snake function with an empty list.

    This test verifies that the camel_to_snake function correctly handles
    empty lists.

    The test data includes:
    - Empty list

    Expected behavior:
    - Empty list should be unchanged

    Returns:
        None

    Raises:
        AssertionError: If the camel_to_snake function output doesn't match
        expected output

    """
    data = []
    expected = []
    assert camel_to_snake(data) == expected


def test_camel_to_snake_with_non_camel_case() -> None:
    """
    Test the camel_to_snake function with dictionary with mixed keys.

    This test verifies that the camel_to_snake function correctly handles
    already snake_case keys alongside camelCase keys.

    The test data includes:
    - Simple dictionary with camelCase and snake_case

    Expected behavior:
    - snake_case keys should be unchanged
    - camelCase keys should be updated

    Returns:
        None

    Raises:
        AssertionError: If the camel_to_snake function output doesn't match
        expected output

    """
    data = {"snake_case_key": "value", "PascalCaseKey": "value"}
    expected = {"snake_case_key": "value", "pascal_case_key": "value"}
    assert camel_to_snake(data) == expected

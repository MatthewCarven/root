"""Tests for the fuzzy matcher."""
from __future__ import annotations

import math

import pytest

from root_cli.matcher import best_score, score


class TestSubsequence:
    def test_empty_query_returns_zero(self):
        assert score("", "anything") == 0.0

    def test_non_subsequence_returns_negative_infinity(self):
        assert score("xyz", "abc") == float("-inf")

    def test_simple_subsequence_matches(self):
        assert score("abc", "axbxcx") > 0

    def test_case_insensitive_by_default(self):
        assert score("abc", "ABC") > 0

    def test_smart_case_uppercase_query_is_case_sensitive(self):
        assert score("ABC", "abc") == float("-inf")
        assert score("ABC", "ABC") > 0


class TestScoring:
    def test_consecutive_beats_scattered(self):
        a = score("foo", "foo")
        b = score("foo", "f_o_o")
        assert a > b

    def test_word_boundary_bonus(self):
        # Match at start of basename should beat match in the middle.
        a = score("proj", "/Users/me/proj")
        b = score("proj", "/Users/projme/other")
        # Both match; the first is at a clear word boundary and basename.
        assert a > b

    def test_basename_match_preferred(self):
        a = score("api", "/code/api-server")
        b = score("api", "/api/code/other-server")
        assert a > b

    def test_shorter_target_wins_ties(self):
        a = score("foo", "foo")
        b = score("foo", "foobarbaz")
        assert a > b


class TestBestScore:
    def test_picks_highest_of_fields(self):
        # Query matches alias exactly; should beat a long path match.
        s = best_score("work", ["work", "/Users/me/some/random/place"])
        assert s > 0
        # Each is a match; we want the alias's score to win.
        single = score("work", "work")
        assert math.isclose(s, single, rel_tol=1e-9)

    def test_returns_neg_inf_when_nothing_matches(self):
        assert best_score("zzz", ["foo", "bar"]) == float("-inf")


@pytest.mark.parametrize(
    "query,target,expected_match",
    [
        ("dot", "/Users/me/.dotfiles", True),
        ("dotfi", "/Users/me/.dotfiles", True),
        ("xyz", "/Users/me/code", False),
        ("Code", "/Users/me/code", False),  # smart case: cap=strict
        ("code", "/Users/me/Code", True),
    ],
)
def test_match_examples(query, target, expected_match):
    s = score(query, target)
    if expected_match:
        assert s > 0
    else:
        assert s == float("-inf")

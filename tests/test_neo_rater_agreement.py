"""Agreement statistics give their textbook values on small known cases."""

import pytest

from scripts.neo_rater_agreement import classes_from, krippendorff_interval, weighted_kappa


def test_identical_ratings_agree_perfectly():
    assert weighted_kappa([0, 1, 2, 1], [0, 1, 2, 1]) == pytest.approx(1)
    assert krippendorff_interval([[0, 0, 0], [1, 1, 1], [2, 2, 2]]) == pytest.approx(1)


def test_reversed_ratings_disagree():
    assert weighted_kappa([0, 1, 2], [2, 1, 0]) < 0
    assert krippendorff_interval([[0, 2], [2, 0]]) < 0


def test_constant_ratings_have_no_kappa():
    assert weighted_kappa([1, 1, 1], [1, 1, 1]) is None


def test_classes_follow_the_c_formula():
    assert classes_from({"x": {"t1": 2, "t2": 3}}) == {"x": {"t1": 2, "t2": 3, "cost": 3}}

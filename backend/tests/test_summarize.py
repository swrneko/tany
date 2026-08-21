from hypothesis import given, settings
from hypothesis import strategies as st

from app.summarize import estimate_tokens, input_budget, split_for_budget


def test_a_transcript_that_fits_stays_in_one_piece() -> None:
    parts = split_for_budget(["hello there", "general kenobi"], budget_tokens=1000)

    assert parts == ["hello there general kenobi"]


def test_a_transcript_that_does_not_fit_is_divided() -> None:
    segments = [f"segment number {index}" for index in range(50)]

    parts = split_for_budget(segments, budget_tokens=estimate_tokens("segment number 00") * 5)

    assert len(parts) > 1
    assert all(part for part in parts)


def test_a_single_oversized_segment_is_not_dropped() -> None:
    """It cannot be made to fit, and silently discarding it would lose the
    loudest part of the recording."""
    giant = "word " * 5000

    parts = split_for_budget(["small", giant, "small"], budget_tokens=20)

    assert any(giant.strip() in part for part in parts)


def test_the_budget_leaves_room_for_the_prompt_and_the_answer() -> None:
    budget = input_budget(8192, prompt_tokens=300)

    assert 0 < budget < 8192 - 300


def test_a_context_too_small_to_use_still_yields_a_positive_budget() -> None:
    assert input_budget(256, prompt_tokens=4000) > 0


@settings(max_examples=200)
@given(
    segments=st.lists(st.text(min_size=1, max_size=40), min_size=1, max_size=120),
    budget=st.integers(min_value=1, max_value=200),
)
def test_every_word_survives_the_split(segments: list[str], budget: int) -> None:
    """Map-reduce over a lost chunk still reads like a summary. That is the
    whole danger: the output looks right and covers two thirds of the meeting."""
    parts = split_for_budget(segments, budget_tokens=budget)

    rejoined = " ".join(parts).split()
    assert rejoined == " ".join(segments).split()


@given(
    segments=st.lists(st.text(alphabet="abc ", min_size=1, max_size=20), min_size=1, max_size=60),
    budget=st.integers(min_value=30, max_value=200),
)
def test_no_part_exceeds_the_budget_unless_one_segment_alone_does(
    segments: list[str], budget: int
) -> None:
    parts = split_for_budget(segments, budget_tokens=budget)

    for part in parts:
        if estimate_tokens(part) > budget:
            assert len(part.split()) > 0
            # The only way to exceed the budget is a single segment that cannot
            # be made to fit on its own.
            assert any(estimate_tokens(segment) > budget for segment in segments)

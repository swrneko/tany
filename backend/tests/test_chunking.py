import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.chunking import HARD_MAX_SECONDS, TARGET_SECONDS, plan_chunks


def test_short_audio_is_one_chunk() -> None:
    chunks = plan_chunks(duration=180.0, silences=[])

    assert len(chunks) == 1
    assert (chunks[0].start, chunks[0].end) == (0.0, 180.0)


def test_a_cut_lands_in_the_silence_nearest_the_target() -> None:
    # Two candidate pauses; the one at ~10 minutes should win over the one at 4.
    silences = [(240.0, 241.0), (601.0, 603.0)]

    chunks = plan_chunks(duration=1500.0, silences=silences)

    assert chunks[0].end == pytest.approx(602.0)
    assert chunks[1].start == pytest.approx(602.0)


def test_without_any_silence_the_cut_falls_back_to_the_hard_maximum() -> None:
    chunks = plan_chunks(duration=HARD_MAX_SECONDS * 2.5, silences=[])

    assert chunks[0].end == pytest.approx(HARD_MAX_SECONDS)
    assert all(chunk.end - chunk.start <= HARD_MAX_SECONDS + 1e-6 for chunk in chunks)


@settings(max_examples=200)
@given(
    duration=st.floats(min_value=1.0, max_value=6 * 3600, allow_nan=False),
    silences=st.lists(
        st.tuples(
            st.floats(min_value=0.0, max_value=6 * 3600, allow_nan=False),
            st.floats(min_value=0.0, max_value=30.0, allow_nan=False),
        ),
        max_size=200,
    ),
)
def test_chunks_always_tile_the_recording(
    duration: float, silences: list[tuple[float, float]]
) -> None:
    """The invariants that matter. A chunking bug is silent: the text still
    reads fine, but five seconds in the middle are simply gone."""
    intervals = [(start, start + length) for start, length in silences]
    assume(all(end <= duration for _, end in intervals))

    chunks = plan_chunks(duration=duration, silences=intervals)

    assert chunks, "a recording always produces at least one chunk"
    assert chunks[0].start == 0.0
    assert chunks[-1].end == pytest.approx(duration)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))

    for chunk in chunks:
        assert chunk.end > chunk.start
        assert chunk.end - chunk.start <= HARD_MAX_SECONDS + 1e-6

    for earlier, later in zip(chunks, chunks[1:], strict=False):
        assert later.start == pytest.approx(earlier.end), "no gap and no overlap"


@given(duration=st.floats(min_value=1.0, max_value=HARD_MAX_SECONDS, allow_nan=False))
def test_a_recording_under_the_maximum_is_never_split(duration: float) -> None:
    assert len(plan_chunks(duration=duration, silences=[])) == 1


def test_the_target_is_smaller_than_the_hard_maximum() -> None:
    assert TARGET_SECONDS < HARD_MAX_SECONDS

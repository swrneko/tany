from dataclasses import dataclass

# Aim for ten minutes, never exceed fifteen. Long enough that the per-request
# overhead disappears, short enough that one failure is cheap to retry.
TARGET_SECONDS = 10 * 60
HARD_MAX_SECONDS = 15 * 60

EPSILON = 1e-6


@dataclass(frozen=True)
class Chunk:
    index: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def plan_chunks(
    *,
    duration: float,
    silences: list[tuple[float, float]],
    target: float = TARGET_SECONDS,
    hard_max: float = HARD_MAX_SECONDS,
) -> list[Chunk]:
    """Split a recording at pauses rather than at fixed intervals.

    Cutting mid-word makes Whisper hallucinate or drop the phrase across the
    seam, and it is a quiet failure: the text still reads as prose, but a
    sentence is gone. So the cut goes into the pause closest to the target, and
    only falls back to a blind cut when the stretch holds no pause at all.
    """
    if duration <= hard_max + EPSILON:
        return [Chunk(index=0, start=0.0, end=duration)]

    midpoints = sorted((start + end) / 2 for start, end in silences)

    chunks: list[Chunk] = []
    cursor = 0.0
    while cursor < duration - EPSILON:
        limit = cursor + hard_max
        if limit >= duration - EPSILON:
            end = duration
        else:
            end = _best_cut(midpoints, lower=cursor, upper=limit, ideal=cursor + target)

        chunks.append(Chunk(index=len(chunks), start=cursor, end=end))
        cursor = end

    return chunks


def _best_cut(midpoints: list[float], *, lower: float, upper: float, ideal: float) -> float:
    """The pause nearest the ideal length, or the hard limit when there is none.

    A candidate must leave a non-empty chunk behind it, otherwise a burst of
    silences at the cursor would produce zero-length chunks forever.
    """
    candidates = [point for point in midpoints if lower + EPSILON < point <= upper]
    if not candidates:
        return upper
    return min(candidates, key=lambda point: abs(point - ideal))

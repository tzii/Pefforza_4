"""Small, replayable tactical lessons; answers are exhaustively checked in tests."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Lesson:
    title: str
    moves: tuple[int, ...]
    answers: tuple[int, ...]
    prompt: str
    explanation: str
    goal: str


LESSONS = (
    Lesson(
        "Across the board",
        (0, 6, 1, 6, 2, 5),
        (3,),
        "Find the move that completes a horizontal four.",
        "Column 4 connects your three coral pieces along the bottom row.",
        "win",
    ),
    Lesson(
        "Build it up",
        (1, 6, 1, 6, 1, 5),
        (1,),
        "Find the move that completes a vertical four.",
        "Column 2 stacks a fourth coral piece above your other three.",
        "win",
    ),
    Lesson(
        "A different angle",
        (5, 2, 4, 6, 4, 6, 3, 3, 3, 6, 5, 4, 2, 2),
        (2,),
        "Gold is threatening, but you can win now. Find the diagonal.",
        "Column 3 completes your diagonal. Taking a win comes before blocking.",
        "win",
    ),
    Lesson(
        "Close the door",
        (0, 6, 1, 6, 4, 6),
        (6,),
        "Gold can win on its next turn. Find the only move that stops it.",
        "Column 7 blocks gold's vertical four. Every other move loses immediately.",
        "block",
    ),
    Lesson(
        "Two ways to win",
        (4, 1, 5, 5, 5, 4),
        (3,),
        "Create two winning threats at once. Gold can only block one.",
        "Column 4 makes three in a row with both ends open: columns 3 and 7.",
        "fork",
    ),
    Lesson(
        "Don't lend a hand",
        (6, 0, 3, 2, 3, 5, 6, 2, 1, 2, 2, 1),
        (0, 1, 2, 4, 5, 6),
        "Choose a move that gives gold no immediate win. Several answers work.",
        "Column 4 gives gold a winning reply. The other columns avoid an immediate loss.",
        "safe",
    ),
)

"""A supplied starter map and the independent-policy agents for the demo."""

from __future__ import annotations

from .agents import ExampleBaselineAgent
from .environment import GridWorld
from .models import Direction


def starter_world() -> GridWorld:
    """Return the required 8 x 8 world with an intentional bottleneck."""

    return GridWorld(
        width=8,
        height=8,
        base=(0, 0),
        # The column-three wall has only one gap at the south edge, forcing
        # traffic between the two halves of the map through a shared corridor.
        obstacles={
            (0, 3),
            (1, 3),
            (2, 3),
            (3, 3),
            (4, 3),
            (5, 3),
            (6, 3),
            (5, 5),
        },
        packages={(1, 1), (0, 6), (5, 6), (7, 6)},
        agent_positions={"robot-1": (0, 1), "robot-2": (2, 0)},
        horizon=60,
    )


def starter_agents() -> dict[str, ExampleBaselineAgent]:
    """Two distinct but equally limited independent baseline agents."""

    return {
        "robot-1": ExampleBaselineAgent(
            (Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST)
        ),
        "robot-2": ExampleBaselineAgent(
            (Direction.WEST, Direction.SOUTH, Direction.EAST, Direction.NORTH)
        ),
    }

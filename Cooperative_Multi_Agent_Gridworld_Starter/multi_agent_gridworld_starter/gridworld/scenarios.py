"""A supplied starter map and the independent-policy agents for the demo."""

from __future__ import annotations

from .agents import CoordinatedAgentTemplate, ExampleBaselineAgent
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


def map2_world() -> GridWorld:
    """A second fixed 8 x 8 map: horizontal wall, gap on the east edge.

    Base sits in the opposite corner from starter_world() (south-west
    instead of north-west). Two packages are on the same side as base (no
    crossing needed) and two are across the wall (must detour through the
    single gap at column 7), for a different balance of "easy" vs.
    "bottlenecked" work than the starter map.
    """

    return GridWorld(
        width=8,
        height=8,
        base=(7, 0),
        # Row-4 wall blocked across columns 0-6; the only gap is at (4, 7).
        obstacles={
            (4, 0),
            (4, 1),
            (4, 2),
            (4, 3),
            (4, 4),
            (4, 5),
            (4, 6),
        },
        packages={(1, 1), (2, 5), (6, 2), (5, 6)},
        agent_positions={"robot-1": (7, 1), "robot-2": (6, 0)},
        horizon=60,
    )


def map3_world() -> GridWorld:
    """A third fixed 8 x 8 map: vertical wall, gap on the north edge.

    Base sits in the north-east corner. Two packages are on the same side
    as base and two are across the wall (must detour through the single
    gap at row 0), mirroring map2_world()'s split but with a different
    wall orientation and base corner.
    """

    return GridWorld(
        width=8,
        height=8,
        base=(0, 7),
        # Column-4 wall blocked across rows 1-7; the only gap is at (0, 4).
        obstacles={
            (1, 4),
            (2, 4),
            (3, 4),
            (4, 4),
            (5, 4),
            (6, 4),
            (7, 4),
        },
        packages={(3, 1), (6, 2), (1, 6), (5, 6)},
        agent_positions={"robot-1": (0, 6), "robot-2": (1, 7)},
        horizon=60,
    )


def starter_agents() -> dict[str, CoordinatedAgentTemplate]:
    """Two distinct but equally limited independent baseline agents."""

    return {
        # "robot-1": ExampleBaselineAgent(
        #     (Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST)
        # ),
        # "robot-2": ExampleBaselineAgent(
        #     (Direction.WEST, Direction.SOUTH, Direction.EAST, Direction.NORTH)
        # ),
        "robot-1": CoordinatedAgentTemplate(
            (Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST)
        ),
        "robot-2": CoordinatedAgentTemplate(
            (Direction.WEST, Direction.SOUTH, Direction.EAST, Direction.NORTH)
        ),
    }

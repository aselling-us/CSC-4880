from __future__ import annotations

import unittest

from gridworld.agents import CoordinatedAgentTemplate
from gridworld.environment import GridWorld
from gridworld.models import (
    Action,
    ActionResult,
    CellView,
    Direction,
    Interaction,
    InteractionResult,
    Message,
    MessageKind,
    MovementResult,
    Percept,
    Position,
    Terrain,
)


def make_percept(
    *,
    self_position: Position,
    cells: dict[Position, CellView],
    time: int = 0,
    carrying: bool = False,
    messages: tuple[Message, ...] = (),
) -> Percept:
    """Build a minimal Percept by hand, without spinning up a GridWorld."""
    return Percept(
        time=time,
        self_position=self_position,
        visible_cells=cells,
        carrying=carrying,
        last_result=ActionResult(MovementResult.WAITED, InteractionResult.NOT_ATTEMPTED),
        messages=messages,
    )


def empty_cell(agent_ids: tuple[str, ...] = ()) -> CellView:
    return CellView(terrain=Terrain.EMPTY, package_present=False, agent_ids=agent_ids)


def package_cell(agent_ids: tuple[str, ...] = ()) -> CellView:
    return CellView(terrain=Terrain.EMPTY, package_present=True, agent_ids=agent_ids)


def base_cell(agent_ids: tuple[str, ...] = ()) -> CellView:
    return CellView(terrain=Terrain.BASE, package_present=False, agent_ids=agent_ids)


class PerceiveCellsTests(unittest.TestCase):
    """Covers TODO 1: updating local memory from percept.visible_cells."""

    def setUp(self) -> None:
        self.agent = CoordinatedAgentTemplate()
        self.agent.reset("alpha")

    def test_base_location_defaults_to_none_before_any_sighting(self) -> None:
        self.assertIsNone(self.agent.base_location)

    def test_visible_package_is_remembered(self) -> None:
        percept = make_percept(
            self_position=(1, 1),
            cells={
                (1, 1): empty_cell(agent_ids=("alpha",)),
                (0, 1): package_cell(),
            },
        )

        self.agent._update_memory(percept)

        self.assertIn((0, 1), self.agent.known_packages)

    def test_package_removed_once_its_cell_is_seen_empty(self) -> None:
        # Simulate memory from an earlier percept.
        self.agent.known_packages.add((0, 1))

        percept = make_percept(
            self_position=(1, 1),
            cells={
                (1, 1): empty_cell(agent_ids=("alpha",)),
                (0, 1): empty_cell(),  # another agent picked it up
            },
        )

        self.agent._update_memory(percept)

        self.assertNotIn((0, 1), self.agent.known_packages)

    def test_package_out_of_sight_is_not_forgotten(self) -> None:
        self.agent.known_packages.add((5, 5))

        percept = make_percept(
            self_position=(1, 1),
            cells={(1, 1): empty_cell(agent_ids=("alpha",))},
        )

        self.agent._update_memory(percept)

        self.assertIn((5, 5), self.agent.known_packages)

    def test_base_location_is_learned_from_percept(self) -> None:
        percept = make_percept(
            self_position=(1, 1),
            cells={
                (1, 1): empty_cell(agent_ids=("alpha",)),
                (1, 0): base_cell(),
            },
        )

        self.agent._update_memory(percept)

        self.assertEqual(self.agent.base_location, (1, 0))

    def test_own_cell_with_a_package_is_remembered_too(self) -> None:
        percept = make_percept(
            self_position=(1, 1),
            cells={(1, 1): package_cell(agent_ids=("alpha",))},
        )

        self.agent._update_memory(percept)

        self.assertIn((1, 1), self.agent.known_packages)


class PerceiveCellsIntegrationTests(unittest.TestCase):
    """Same behavior, driven through a real GridWorld percept."""

    def test_agent_learns_base_and_package_from_a_real_percept(self) -> None:
        world = GridWorld(
            width=3,
            height=3,
            base=(0, 0),
            obstacles=set(),
            packages={(1, 1)},
            agent_positions={"alpha": (0, 1), "beta": (2, 2)},
            horizon=10,
        )
        agent = CoordinatedAgentTemplate()
        agent.reset("alpha")

        agent.act(world.observe("alpha"))

        self.assertEqual(agent.base_location, (0, 0))
        self.assertIn((1, 1), agent.known_packages)

class ChooseTargetTests(unittest.TestCase):
    """Covers TODO 3: choosing a target that respects claims."""

    def setUp(self) -> None:
        self.agent = CoordinatedAgentTemplate()
        self.agent.reset("alpha")

    def test_carrying_targets_the_known_base(self) -> None:
        self.agent.base_location = (0, 0)
        percept = make_percept(
            self_position=(1, 1),
            cells={(1, 1): empty_cell(agent_ids=("alpha",))},
            carrying=True,
        )

        self.agent.act(percept)

        self.assertEqual(self.agent.choose_target, (0, 0))

    def test_carrying_with_no_known_base_leaves_target_unset(self) -> None:
        percept = make_percept(
            self_position=(1, 1),
            cells={(1, 1): empty_cell(agent_ids=("alpha",))},
            carrying=True,
        )

        self.agent.act(percept)

        self.assertIsNone(self.agent.choose_target)

    def test_standing_on_a_package_targets_its_own_cell(self) -> None:
        percept = make_percept(
            self_position=(1, 1),
            cells={(1, 1): package_cell(agent_ids=("alpha",))},
        )

        self.agent.act(percept)

        self.assertEqual(self.agent.choose_target, (1, 1))

    def test_nearest_unclaimed_known_package_is_the_target(self) -> None:
        self.agent.known_packages = {(0, 1), (5, 5)}
        percept = make_percept(
            self_position=(1, 1),
            cells={(1, 1): empty_cell(agent_ids=("alpha",))},
        )

        self.agent.act(percept)

        self.assertEqual(self.agent.choose_target, (0, 1))  # closer of the two

    def test_a_package_claimed_by_another_agent_is_skipped(self) -> None:
        self.agent.known_packages = {(0, 1), (5, 5)}
        self.agent.claimed_by = {(0, 1): "beta"}  # closer one is taken

        percept = make_percept(
            self_position=(1, 1),
            cells={(1, 1): empty_cell(agent_ids=("alpha",))},
        )

        self.agent.act(percept)

        self.assertEqual(self.agent.choose_target, (5, 5))

    def test_no_known_packages_leaves_target_unset(self) -> None:
        percept = make_percept(
            self_position=(1, 1),
            cells={(1, 1): empty_cell(agent_ids=("alpha",))},
        )

        self.agent.act(percept)

        self.assertIsNone(self.agent.choose_target)


class PathfindingTests(unittest.TestCase):
    """Covers _plan_route: BFS routing around remembered obstacles."""

    def setUp(self) -> None:
        self.agent = CoordinatedAgentTemplate()
        self.agent.reset("alpha")

    def test_plans_a_direct_route_when_nothing_is_in_the_way(self) -> None:
        percept = make_percept(
            self_position=(0, 0),
            cells={(0, 0): empty_cell(agent_ids=("alpha",))},
        )

        move = self.agent._plan_route(percept, (0, 3))

        self.assertEqual(move, Direction.EAST)

    def test_route_detours_through_the_only_known_gap_in_a_wall(self) -> None:
        # Mirrors the starter map's column-3 wall: blocked for rows 0-6,
        # open only at row 7. The agent has already walked the row-7
        # corridor once (so it's fully known) and has stood at the top
        # row (so it knows row -1 is off the grid, not just unexplored).
        for row in range(7):
            self.agent.known_terrain[(row, 3)] = Terrain.OBSTACLE
        self.agent.known_terrain[(7, 3)] = Terrain.EMPTY
        for column in range(-1, 8):
            self.agent.known_out_of_bounds.add((-1, column))

        percept = make_percept(
            self_position=(1, 4),
            cells={(1, 4): empty_cell(agent_ids=("alpha",))},
        )

        move = self.agent._plan_route(percept, (0, 0))

        # Regression check: without known_out_of_bounds, this used to
        # return NORTH -- a fake "shortcut" through row -1 that isn't
        # actually on the map, causing an infinite two-cell oscillation
        # once the agent discovered the off-grid step was illegal.
        self.assertEqual(move, Direction.SOUTH)


class MessagePassingTests(unittest.TestCase):
    def test_claim_message_is_received_by_other_agent(self) -> None:
        world = GridWorld(
            width=3,
            height=3,
            base=(0, 0),
            obstacles=set(),
            packages={(2, 2)},
            agent_positions={"robot-1": (1, 1), "robot-2": (0, 1)},
            horizon=10,
        )
        agent = CoordinatedAgentTemplate()
        agent.reset("robot-1")

        # Simulate a claim message being sent by robot-1.
        world.step(
            {
                "robot-1": Action(
                    message=Message(MessageKind.CLAIM, package_location=(2, 2))
                ),
                "robot-2": Action(),
            }
        )

        self.assertEqual(
            world.observe("robot-2").messages,
            (Message(MessageKind.CLAIM, package_location=(2, 2), sender="robot-1"),),
        )
        
if __name__ == "__main__":
    unittest.main()

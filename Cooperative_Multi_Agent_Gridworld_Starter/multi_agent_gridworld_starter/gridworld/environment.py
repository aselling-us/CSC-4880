"""A small, deterministic cooperative gridworld environment.

This file implements the mechanics required for the lab.  It deliberately
does not decide how agents should coordinate; that policy belongs in student
agent code.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from .models import (
    Action,
    ActionResult,
    AgentState,
    CellView,
    Direction,
    EpisodeResult,
    Event,
    Interaction,
    InteractionResult,
    Message,
    MovementResult,
    Percept,
    Position,
    Terrain,
)


class GridWorld:
    """An 8 x 8-style gridworld with local perception and simultaneous motion.

    Scores are applied exactly as specified in the lab: +10 for a delivery,
    -1 per attempted move, -2 for an invalid move or interaction, -3 for each
    collision attempt, and -5 for each package left unfinished at episode end.
    """

    def __init__(
        self,
        *,
        width: int,
        height: int,
        base: Position,
        obstacles: set[Position],
        packages: set[Position],
        agent_positions: Mapping[str, Position],
        horizon: int = 60,
    ) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive")
        if horizon <= 0:
            raise ValueError("horizon must be positive")
        if len(agent_positions) < 2:
            raise ValueError("the lab scenario requires at least two agents")

        self.width = width
        self.height = height
        self.base = base
        self.obstacles = set(obstacles)
        self.initial_packages = set(packages)
        self.initial_agent_positions = dict(agent_positions)
        self.horizon = horizon

        self._validate_initial_world()
        self.reset()

    @property
    def agent_ids(self) -> tuple[str, ...]:
        return tuple(self.states)

    def reset(self) -> None:
        """Restore the initial map and clear the score and event log."""

        self.states: dict[str, AgentState] = {
            agent_id: AgentState(position)
            for agent_id, position in self.initial_agent_positions.items()
        }
        self.remaining_packages = set(self.initial_packages)
        self.delivered_packages: list[Position] = []
        self.score = 0
        self.collision_attempts = 0
        self.time = 0
        self.events: list[Event] = []
        self._finalized = False

    def observe(self, agent_id: str) -> Percept:
        """Return a local 3 x 3 percept without exposing the whole map.

        Messages sent during time t become visible in the next decision cycle,
        after ``step`` has advanced the clock to t + 1.
        """

        state = self._require_agent(agent_id)
        visible_cells: dict[Position, CellView] = {}
        occupants = self._occupants_by_position()
        row, column = state.position
        for view_row in range(row - 1, row + 2):
            for view_column in range(column - 1, column + 2):
                position = (view_row, view_column)
                if not self._in_bounds(position):
                    continue
                visible_cells[position] = CellView(
                    terrain=self._terrain_at(position),
                    package_present=position in self.remaining_packages,
                    agent_ids=tuple(sorted(occupants.get(position, []))),
                )

        return Percept(
            time=self.time,
            self_position=state.position,
            visible_cells=visible_cells,
            carrying=state.carried_package is not None,
            last_result=state.last_result,
            messages=tuple(state.inbox),
        )

    def step(
        self,
        actions: Mapping[str, Action],
        percept_summaries: Mapping[str, str] | None = None,
    ) -> tuple[Event, ...]:
        """Resolve every agent action simultaneously and return log entries.

        Missing actions are treated as ``WAIT``.  An invalid move leaves the
        agent in place.  Same-destination conflicts, attempted swaps, and
        moves into an agent that remains in place are blocked as collisions.
        """

        if self._finalized:
            raise RuntimeError("cannot step after finish(); call reset() first")
        unknown_agents = set(actions) - set(self.states)
        if unknown_agents:
            raise KeyError(f"action supplied for unknown agent(s): {sorted(unknown_agents)}")

        percept_summaries = percept_summaries or {}
        resolved_actions = {
            agent_id: actions.get(agent_id, Action()) for agent_id in self.agent_ids
        }
        positions_before = {
            agent_id: state.position for agent_id, state in self.states.items()
        }
        inboxes_before = {
            agent_id: tuple(state.inbox) for agent_id, state in self.states.items()
        }

        intended = dict(positions_before)
        movement_results: dict[str, MovementResult] = {}
        valid_movers: set[str] = set()

        for agent_id, action in resolved_actions.items():
            if action.move is Direction.WAIT:
                movement_results[agent_id] = MovementResult.WAITED
                continue

            self.score -= 1
            candidate = self._translate(positions_before[agent_id], action.move)
            if not self._in_bounds(candidate) or candidate in self.obstacles:
                self.score -= 2
                movement_results[agent_id] = MovementResult.INVALID_MOVE
                continue

            intended[agent_id] = candidate
            valid_movers.add(agent_id)
            movement_results[agent_id] = MovementResult.MOVED

        blocked = self._find_collision_blocks(
            positions_before=positions_before,
            intended=intended,
            valid_movers=valid_movers,
        )
        for agent_id in blocked:
            movement_results[agent_id] = MovementResult.BLOCKED_COLLISION
            self.score -= 3
            self.collision_attempts += 1

        for agent_id, state in self.states.items():
            if agent_id in valid_movers and agent_id not in blocked:
                state.position = intended[agent_id]

        interaction_results: dict[str, InteractionResult] = {}
        for agent_id, action in resolved_actions.items():
            interaction_results[agent_id] = self._resolve_interaction(
                self.states[agent_id], action.interaction
            )

        # Every message in the inbox belonged to the just-completed decision.
        # Clear it before adding broadcasts for the next decision cycle.
        for state in self.states.values():
            state.inbox.clear()

        sent_messages: dict[str, Message | None] = {}
        for agent_id, action in resolved_actions.items():
            message = action.message
            if message is None:
                sent_messages[agent_id] = None
                continue
            stamped_message = replace(message, sender=agent_id)
            sent_messages[agent_id] = stamped_message
            for recipient_id, recipient_state in self.states.items():
                if recipient_id != agent_id:
                    recipient_state.inbox.append(stamped_message)

        step_events: list[Event] = []
        for agent_id, state in self.states.items():
            result = ActionResult(
                movement=movement_results[agent_id],
                interaction=interaction_results[agent_id],
            )
            state.last_result = result
            step_events.append(
                Event(
                    time=self.time,
                    agent_id=agent_id,
                    percept_summary=percept_summaries.get(agent_id, "(not recorded)"),
                    received_messages=inboxes_before[agent_id],
                    sent_message=sent_messages[agent_id],
                    action=resolved_actions[agent_id],
                    result=result,
                    final_position=state.position,
                )
            )

        self.events.extend(step_events)
        self.time += 1
        return tuple(step_events)

    def is_complete(self) -> bool:
        """True after every package has been deposited at the base."""

        return not self.remaining_packages and all(
            state.carried_package is None for state in self.states.values()
        )

    def finish(self) -> EpisodeResult:
        """Apply the terminal undelivered-package penalty once and report results."""

        if not self._finalized:
            unfinished = len(self.remaining_packages) + sum(
                state.carried_package is not None for state in self.states.values()
            )
            self.score -= 5 * unfinished
            self._finalized = True

        return EpisodeResult(
            score=self.score,
            delivered_count=len(self.delivered_packages),
            collision_attempts=self.collision_attempts,
            steps=self.time,
            events=tuple(self.events),
        )

    def _resolve_interaction(
        self, state: AgentState, interaction: Interaction
    ) -> InteractionResult:
        if interaction is Interaction.NONE:
            return InteractionResult.NOT_ATTEMPTED

        if interaction is Interaction.PICKUP:
            if state.carried_package is None and state.position in self.remaining_packages:
                self.remaining_packages.remove(state.position)
                state.carried_package = state.position
                return InteractionResult.PICKED_UP
            self.score -= 2
            return InteractionResult.INVALID_INTERACTION

        if interaction is Interaction.DROP:
            if state.carried_package is not None and state.position == self.base:
                self.delivered_packages.append(state.carried_package)
                state.carried_package = None
                self.score += 10
                return InteractionResult.DROPPED
            self.score -= 2
            return InteractionResult.INVALID_INTERACTION

        raise ValueError(f"unsupported interaction: {interaction}")

    def _find_collision_blocks(
        self,
        *,
        positions_before: Mapping[str, Position],
        intended: Mapping[str, Position],
        valid_movers: set[str],
    ) -> set[str]:
        """Return movers whose simultaneous movement must be blocked.

        This deliberately uses a small, explicit resolver rather than a global
        planner: resolving traffic is part of the environment, while choosing
        a cooperative policy remains the students' task.
        """

        blocked: set[str] = set()
        mover_ids = tuple(valid_movers)

        # Two or more agents cannot enter the same cell.
        for index, first_id in enumerate(mover_ids):
            for second_id in mover_ids[index + 1 :]:
                if intended[first_id] == intended[second_id]:
                    blocked.update((first_id, second_id))

        # Direct exchanges of positions are blocked.
        for index, first_id in enumerate(mover_ids):
            for second_id in mover_ids[index + 1 :]:
                if (
                    intended[first_id] == positions_before[second_id]
                    and intended[second_id] == positions_before[first_id]
                ):
                    blocked.update((first_id, second_id))

        # If a mover targets an agent that ultimately stays put, it too blocks.
        # Repeat because blocking one mover can make a following mover invalid.
        changed = True
        while changed:
            changed = False
            successfully_moving = valid_movers - blocked
            for mover_id in successfully_moving:
                target = intended[mover_id]
                for occupant_id, occupant_position in positions_before.items():
                    if occupant_id == mover_id or occupant_position != target:
                        continue
                    if occupant_id not in successfully_moving:
                        blocked.add(mover_id)
                        changed = True
                        break

        return blocked

    def _occupants_by_position(self) -> dict[Position, list[str]]:
        occupants: dict[Position, list[str]] = {}
        for agent_id, state in self.states.items():
            occupants.setdefault(state.position, []).append(agent_id)
        return occupants

    def _terrain_at(self, position: Position) -> Terrain:
        if position == self.base:
            return Terrain.BASE
        if position in self.obstacles:
            return Terrain.OBSTACLE
        return Terrain.EMPTY

    def _translate(self, position: Position, direction: Direction) -> Position:
        row_delta, column_delta = direction.delta
        return (position[0] + row_delta, position[1] + column_delta)

    def _in_bounds(self, position: Position) -> bool:
        row, column = position
        return 0 <= row < self.height and 0 <= column < self.width

    def _require_agent(self, agent_id: str) -> AgentState:
        try:
            return self.states[agent_id]
        except KeyError as error:
            raise KeyError(f"unknown agent: {agent_id}") from error

    def _validate_initial_world(self) -> None:
        named_positions = {"base": {self.base}, "obstacles": self.obstacles, "packages": self.initial_packages}
        for label, positions in named_positions.items():
            for position in positions:
                if not self._in_bounds(position):
                    raise ValueError(f"{label} contains an out-of-bounds position: {position}")
        if self.base in self.obstacles:
            raise ValueError("base cannot also be an obstacle")
        if self.initial_packages & self.obstacles:
            raise ValueError("packages cannot be placed in obstacles")
        occupied_positions = list(self.initial_agent_positions.values())
        if len(set(occupied_positions)) != len(occupied_positions):
            raise ValueError("agents must start in distinct cells")
        for agent_id, position in self.initial_agent_positions.items():
            if not self._in_bounds(position):
                raise ValueError(f"agent {agent_id!r} starts out of bounds at {position}")
            if position in self.obstacles:
                raise ValueError(f"agent {agent_id!r} starts in an obstacle")

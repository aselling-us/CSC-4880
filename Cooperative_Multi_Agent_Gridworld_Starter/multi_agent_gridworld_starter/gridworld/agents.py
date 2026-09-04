"""An intentionally simple independent agent and a coordination template."""

from __future__ import annotations

from collections import deque

from .models import (
    Action,
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


class ExampleBaselineAgent:
    """A deliberately limited agent for the independent-policy baseline.

    It remembers packages and the base only after seeing them in a local
    percept.  It sends no messages, does not claim work, and has no global map
    or path planner.  Students should use it as a comparison point, not as a
    coordinated solution.
    """

    def __init__(self, exploration_order: tuple[Direction, ...] | None = None) -> None:
        self.exploration_order = exploration_order or (
            Direction.NORTH,
            Direction.EAST,
            Direction.SOUTH,
            Direction.WEST,
        )
        if not self.exploration_order or Direction.WAIT in self.exploration_order:
            raise ValueError("exploration_order must contain non-WAIT directions")
        self.reset("")

    def reset(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.known_packages: set[Position] = set()
        self.base_location: Position | None = None
        self._exploration_cursor = 0

    def act(self, percept: Percept) -> Action:
        """Choose one purely local, non-communicating action."""

        self._update_memory(percept)

        if percept.carrying:
            if percept.self_position == self.base_location:
                return Action(interaction=Interaction.DROP)
            if self.base_location is not None:
                return Action(move=self._move_toward(percept, self.base_location))
            return Action(move=self._explore(percept))

        current_cell = percept.visible_cells[percept.self_position]
        if current_cell.package_present:
            return Action(interaction=Interaction.PICKUP)

        if self.known_packages:
            target = min(
                self.known_packages,
                key=lambda position: self._manhattan(percept.self_position, position),
            )
            if target != percept.self_position:
                move = self._move_toward(percept, target)
                if move is not Direction.WAIT:
                    return Action(move=move)

        return Action(move=self._explore(percept))

    def _update_memory(self, percept: Percept) -> None:
        for position, cell in percept.visible_cells.items():
            if cell.terrain is Terrain.BASE:
                self.base_location = position
            if cell.package_present:
                self.known_packages.add(position)
            elif position in self.known_packages:
                # This handles packages that another agent has picked up once
                # their former location becomes locally visible.
                self.known_packages.remove(position)

    def _move_toward(self, percept: Percept, target: Position) -> Direction:
        row, column = percept.self_position
        target_row, target_column = target
        preferred: list[Direction] = []
        if target_row < row:
            preferred.append(Direction.NORTH)
        elif target_row > row:
            preferred.append(Direction.SOUTH)
        if target_column < column:
            preferred.append(Direction.WEST)
        elif target_column > column:
            preferred.append(Direction.EAST)

        for direction in (*preferred, *self.exploration_order):
            if self._can_enter(percept, direction):
                return direction
        return Direction.WAIT

    def _explore(self, percept: Percept) -> Direction:
        for offset in range(len(self.exploration_order)):
            index = (self._exploration_cursor + offset) % len(self.exploration_order)
            direction = self.exploration_order[index]
            if self._can_enter(percept, direction):
                self._exploration_cursor = (index + 1) % len(self.exploration_order)
                return direction
        return Direction.WAIT

    @staticmethod
    def _can_enter(percept: Percept, direction: Direction) -> bool:
        row_delta, column_delta = direction.delta
        destination = (
            percept.self_position[0] + row_delta,
            percept.self_position[1] + column_delta,
        )
        cell = percept.visible_cells.get(destination)
        if cell is None or cell.terrain is Terrain.OBSTACLE:
            return False
        return not cell.agent_ids

    @staticmethod
    def _manhattan(first: Position, second: Position) -> int:
        return abs(first[0] - second[0]) + abs(first[1] - second[1])


class CoordinatedAgentTemplate:
    """A safe, incomplete shell for the student coordination policy.

    The method intentionally returns WAIT until students add their own local
    memory, claim rules, DISCOVER/CLAIM/RELEASE messages, and collision-aware
    action selection.  It is not a hidden solution.
    """

    def __init__(self, exploration_order: tuple[Direction, ...] | None = None) -> None:
        self.exploration_order = exploration_order or (
            Direction.NORTH,
            Direction.EAST,
            Direction.SOUTH,
            Direction.WEST,
        )
        if not self.exploration_order or Direction.WAIT in self.exploration_order:
            raise ValueError("exploration_order must contain non-WAIT directions")
        self.reset("")

    def reset(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.known_packages: set[Position] = set()
        self.claimed_by: dict[Position, str] = {}
        self.base_location: Position | None = None
        self._exploration_cursor = 0
        self.my_claim: Position | None = None
        # Terrain this agent has actually observed, for pathfinding around
        # obstacles it has already seen (e.g. the column-3 wall). Cells never
        # observed are treated as optimistically passable in _plan_route.
        self.known_terrain: dict[Position, Terrain] = {}
        # Cells confirmed off the map: visible_cells always contains every
        # in-bounds cell in the local 3x3 window, so a cardinal neighbor
        # missing from it is off-grid, not just unexplored. Without this,
        # _plan_route treats unseen space past the edge as a free shortcut.
        self.known_out_of_bounds: set[Position] = set()
        # The direction actually attempted last step, for _resolve_blocked_move.
        # Anchoring on this (rather than recomputing it fresh) lets repeated
        # blocks keep advancing around exploration_order instead of re-deriving
        # the same "primary -> first alternative" jump forever.
        self._last_move: Direction = Direction.WAIT


    def act(self, percept: Percept) -> Action:
        # TODO 1: update only local memory from percept.visible_cells.
        known_packages_before = set(self.known_packages)
        self._update_memory(percept)
        # TODO 2: process messages received at the start of this decision.
        
        for message in percept.messages:
            loc = message.package_location
            if loc is None:
                continue
            if message.kind is MessageKind.DISCOVER:
                self.known_packages.add(loc)
            elif message.kind is MessageKind.CLAIM:
                current = self.claimed_by.get(loc)
                if current is None or message.sender < current:
                    self.claimed_by[loc] = message.sender

            elif message.kind is MessageKind.RELEASE:
                if self.claimed_by.get(loc) == message.sender:
                    del self.claimed_by[loc]
        
        # TODO 3: choose a target that respects claims and avoids local traffic.
        self.choose_target = None
        if percept.carrying:
            if self.base_location is not None:
                self.choose_target = self.base_location
        else:
            # are we standing on a package cell?
            current_cell = percept.visible_cells[percept.self_position]
            if current_cell.package_present:
                self.choose_target = percept.self_position
            else:
                # find the closest unclaimed package
                    # TODO 3
                candidates = [
                    p for p in self.known_packages
                    if p not in self.claimed_by or self.claimed_by[p] == self.agent_id
                ]

                if candidates:
                    self.choose_target = min(
                        candidates,
                        key=lambda position: self._manhattan(percept.self_position, position),
                    )
                else:                
                    self.choose_target = None

        # TODO 4: send DISCOVER, CLAIM, or RELEASE when the protocol requires it.

        # detect what changed since last step 
        new_pkg = self.known_packages - known_packages_before
        is_delivery_happened = percept.last_result.interaction is InteractionResult.DROPPED
        claim_abandoned = self.my_claim is not None and (
            self.choose_target != self.my_claim
            or self.my_claim not in self.known_packages
        )

        message_to_send: Message | None = None
        

        if is_delivery_happened or claim_abandoned:
            released = self.my_claim
            self.my_claim = None
            if released is not None:
                message_to_send = Message(MessageKind.RELEASE, package_location=released)
        elif (self.choose_target is not None and self.choose_target != self.base_location and self.choose_target != self.my_claim):
            self.my_claim = self.choose_target
            self.claimed_by[self.choose_target] = self.agent_id
            message_to_send = Message(MessageKind.CLAIM, package_location=self.choose_target)
        elif new_pkg:
            discovery = min(
                new_pkg,
                key=lambda position: self._manhattan(percept.self_position, position),
            )
            message_to_send = Message(MessageKind.DISCOVER, package_location=discovery)

        # TODO 5: return one Action(move=..., interaction=..., message=...).
        move = Direction.WAIT
        interaction = Interaction.NONE

        if self.choose_target == percept.self_position:
            # Already at the target: interact instead of moving.
            interaction = Interaction.DROP if percept.carrying else Interaction.PICKUP
        elif self.choose_target is not None:
            move = self._move_toward(percept, self.choose_target)
            move = self._resolve_blocked_move(percept, move)
        else:
            move = self._explore(percept)
            move = self._resolve_blocked_move(percept, move)

        self._last_move = move
        return Action(move=move, interaction=interaction, message=message_to_send)

    def _resolve_blocked_move(self, percept: Percept, move: Direction) -> Direction:
        """Don't repeat a move that was just blocked by a collision.

        percept.last_result reflects the outcome of last step's action. If
        it was BLOCKED_COLLISION, retrying the identical direction just
        repeats the same standoff forever -- nothing about either agent's
        state changes in response to being blocked otherwise. Instead,
        advance to the next direction in this agent's own exploration_order.
        Since robot-1 and robot-2 have different orders, they won't both
        pick the same "next" direction, so a head-on standoff resolves in
        a step or two instead of looping indefinitely.

        Anchored on self._last_move (the direction actually attempted last
        step), not the freshly recomputed `move` -- the planner recomputes
        the identical "ideal" move every step regardless of being blocked,
        so anchoring on that would re-derive the same first alternative
        forever instead of advancing further around exploration_order when
        that alternative turns out to be contested too.
        """
        if percept.last_result.movement is not MovementResult.BLOCKED_COLLISION:
            return move

        anchor = self._last_move if self._last_move in self.exploration_order else move
        start_index = self.exploration_order.index(anchor)
        for offset in range(1, len(self.exploration_order) + 1):
            candidate = self.exploration_order[(start_index + offset) % len(self.exploration_order)]
            if self._can_enter(percept, candidate):
                return candidate
        return Direction.WAIT

    def _update_memory(self, percept: Percept) -> None:
        for position, cell in percept.visible_cells.items():
            self.known_terrain[position] = cell.terrain
            if cell.terrain is Terrain.BASE:
                self.base_location = position
            if cell.package_present:
                self.known_packages.add(position)
            elif position in self.known_packages:
                # This handles packages that another agent has picked up once
                # their former location becomes locally visible.
                self.known_packages.remove(position)

        row, column = percept.self_position
        for direction in (Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST):
            row_delta, column_delta = direction.delta
            neighbor = (row + row_delta, column + column_delta)
            if neighbor not in percept.visible_cells:
                self.known_out_of_bounds.add(neighbor)

    def _move_toward(self, percept: Percept, target: Position) -> Direction:
        planned = self._plan_route(percept, target)
        if planned is not None and self._can_enter(percept, planned):
            return planned

        # No known route around an obstacle yet (target or the way to it is
        # still unexplored) or the planned cell is occupied right now: fall
        # back to the local greedy heuristic.
        row, column = percept.self_position
        target_row, target_column = target
        preferred: list[Direction] = []
        if target_row < row:
            preferred.append(Direction.NORTH)
        elif target_row > row:
            preferred.append(Direction.SOUTH)
        if target_column < column:
            preferred.append(Direction.WEST)
        elif target_column > column:
            preferred.append(Direction.EAST)

        for direction in (*preferred, *self.exploration_order):
            if self._can_enter(percept, direction):
                return direction
        return Direction.WAIT

    def _plan_route(self, percept: Percept, target: Position) -> Direction | None:
        """BFS over remembered terrain; returns the first step, or None.

        Cells this agent has never observed are treated as optimistically
        passable, so it can still head toward unexplored territory. Anything
        actually seen as Terrain.OBSTACLE is avoided. This replans from
        scratch every call, so a newly observed wall corrects the route
        immediately instead of causing the greedy heuristic's dead-end
        oscillation.
        """
        start = percept.self_position
        if start == target:
            return None

        rows = [p[0] for p in self.known_terrain] + [start[0], target[0]]
        columns = [p[1] for p in self.known_terrain] + [start[1], target[1]]
        margin = 3
        row_lo, row_hi = min(rows) - margin, max(rows) + margin
        col_lo, col_hi = min(columns) - margin, max(columns) + margin

        directions = (Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST)
        frontier: deque[Position] = deque([start])
        came_from: dict[Position, Position] = {}
        found = False
        while frontier:
            current = frontier.popleft()
            if current == target:
                found = True
                break
            for direction in directions:
                row_delta, column_delta = direction.delta
                neighbor = (current[0] + row_delta, current[1] + column_delta)
                if neighbor == start or neighbor in came_from:
                    continue
                if not (row_lo <= neighbor[0] <= row_hi and col_lo <= neighbor[1] <= col_hi):
                    continue
                if neighbor in self.known_out_of_bounds:
                    continue
                if self.known_terrain.get(neighbor) is Terrain.OBSTACLE:
                    continue
                came_from[neighbor] = current
                frontier.append(neighbor)

        if not found:
            return None

        # Walk the path back from target to the first step out of start.
        step = target
        while came_from[step] != start:
            step = came_from[step]
        row_delta = step[0] - start[0]
        column_delta = step[1] - start[1]
        for direction in directions:
            if direction.delta == (row_delta, column_delta):
                return direction
        return None

    def _explore(self, percept: Percept) -> Direction:
        # Commit to the current heading and only rotate to the next
        # direction in exploration_order when it's actually blocked. A
        # round-robin cursor that advances every step traces a small closed
        # loop in open space; holding a heading lets the agent cover ground.
        for offset in range(len(self.exploration_order)):
            index = (self._exploration_cursor + offset) % len(self.exploration_order)
            direction = self.exploration_order[index]
            if self._can_enter(percept, direction):
                self._exploration_cursor = index
                return direction
        return Direction.WAIT

    @staticmethod
    def _can_enter(percept: Percept, direction: Direction) -> bool:
        row_delta, column_delta = direction.delta
        destination = (
            percept.self_position[0] + row_delta,
            percept.self_position[1] + column_delta,
        )
        cell = percept.visible_cells.get(destination)
        if cell is None or cell.terrain is Terrain.OBSTACLE:
            return False
        return not cell.agent_ids

    @staticmethod
    def _manhattan(first: Position, second: Position) -> int:
        return abs(first[0] - second[0]) + abs(first[1] - second[1])

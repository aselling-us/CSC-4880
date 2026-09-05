# CSC4880 Cooperative Multi-Agent Gridworld — Starter Code

This package accompanies the **Cooperative Multi-Agent Gridworld** lab.  It
implements a small environment in which two robots collect packages and return
them to a common base.  The design follows the Russell and Norvig agent model:
each agent receives a local percept, retains any internal state it chooses,
and returns one action at each time step.

The included `ExampleBaselineAgent` is an intentionally weak, independent
agent.  It has local memory and a simple exploration rule, but it does **not**
communicate, claim packages, or coordinate traffic.  It is a comparison point,
not a solution to the lab.  `CoordinatedAgentTemplate` is a runnable shell
with the coordination work left as TODOs for students.

## Run it

The project uses only the Python standard library and Python 3.10 or later.
From this directory, run:

```bash
python run_demo.py
python -m unittest discover -s tests -v
```

## What is included

| Path | Purpose |
| --- | --- |
| `gridworld/environment.py` | Environment mechanics, scoring, local perception, simultaneous moves, messages, and event logs. |
| `gridworld/models.py` | The `Percept`, `Action`, `Message`, and result data structures. |
| `gridworld/agents.py` | The independent baseline example and the incomplete coordinated-agent template. |
| `gridworld/runner.py` | A loop that asks each agent for its own action, then advances the world. |
| `gridworld/scenarios.py` | One 8 x 8 starter map with four packages, obstacles, and a bottleneck. |
| `tests/test_environment.py` | Mechanics checks students can run while extending their policy. |

## Environment contract

- Coordinates are `(row, column)`; row 0 is north and column 0 is west.
- Each agent sees only in-bounds cells in a local 3 x 3 window, its carrying
  state, its last action result, the current time, and any incoming messages.
- An `Action` can request a move, a pickup/drop interaction, and one optional
  broadcast message in the same time step.
- Moves resolve simultaneously.  Same-destination moves, swaps, and moves into
  an agent that stays in place are blocked and logged as collision attempts.
- A message sent in time `t` is available when the recipient next chooses an
  action at time `t + 1`.
- The team score is: `+10` per delivered package, `-1` per attempted move,
  `-2` per invalid move or interaction, `-3` per collision attempt, and `-5`
  per unfinished package at the end of the episode.

`run_demo.py` prints a short event log.  The full log is available as
`EpisodeResult.events`; each event records the time, agent, percept summary,
received/sent messages, action, result, and final position.

## Student starting point

1. Run the supplied independent baseline and record its deliveries, score,
   collision attempts, and steps.
2. Implement the TODOs in `CoordinatedAgentTemplate` (or create your own agent
   class with the same `reset()` and `act()` methods).
3. Define local rules for `DISCOVER`, `CLAIM`, and `RELEASE` messages.  Keep
   package knowledge and claims in each agent's own state; do not read the
   whole environment from the agent.
4. Compare your policy against the baseline on the starter map and on the
   additional fixed maps or seeds required by the lab.
5. Extend the tests if you add behavior that needs a contract check.

The environment intentionally does not enforce a particular claim policy.
Deciding how claims are made, respected, released, or repaired after a failed
attempt is the core multi-agent design problem for the lab.


## PEAS and Task-Environment Classification

**Performance measure.** A single team score shared by both agents:
`+10` per delivered package, `-1` per attempted move regardless of outcome,
an additional `-2` for an invalid move or invalid interaction, an
additional `-3` for a collision attempt, and `-5` for each package still
undelivered when the episode ends (`environment.py`). Because the score is
shared rather than per-agent, an individual agent's rational behavior
includes not interfering with its teammate — there's no way to "win"
locally at the other agent's expense.

**Environment.** An 8 x 8 grid (`gridworld/scenarios.py`) with one base,
an obstacle wall forming one intentional single-gap bottleneck, four
packages, two agents, and a 60-step horizon.

**Actuators.** Each `Action` bundles, in the same time step: one move
(`NORTH`/`SOUTH`/`EAST`/`WEST`/`WAIT`), one interaction (`PICKUP`/`DROP`/
`NONE`), and at most one broadcast message (`DISCOVER`/`CLAIM`/`RELEASE`)
(`models.py`).

**Sensors.** Each `Percept` provides only the local 3 x 3 `visible_cells`
window (terrain, package presence, and occupying agent ids for in-bounds
neighbors), `self_position`, `carrying`, `last_result` (the outcome of its
*own* previous action), `time`, and any `messages` delivered this step —
nothing about the rest of the map and nothing about the other agent's
plans.

**Task-environment properties**, each grounded in the simulator rather
than asserted:

- **Discrete** — grid coordinates, a fixed enum of moves/interactions/
  message kinds, and one decision per integer `time` step.
- **Sequential** — `GridWorld.step()` carries state forward (positions,
  remaining packages, in-flight claims); the current action shapes every
  later percept.
- **Partially observable** — `observe()` returns only the local 3 x 3
  window, so an agent can't see a package or the base until it's nearby.
  `CoordinatedAgentTemplate._update_memory` exists specifically to
  compensate: it accumulates `known_packages`, `known_terrain`, and
  `known_out_of_bounds` across steps because the live percept alone isn't
  enough to plan a route or remember a package once it's out of view.
- **Dynamic** — the world changes between one agent's decisions for
  reasons other than its own actions: the other agent moves, picks up or
  delivers packages, and sends messages that change what's true
  (`claimed_by`) independent of anything this agent did.
- **Cooperative multi-agent** — both agents optimize one shared score, and
  the environment provides a message channel (`DISCOVER`/`CLAIM`/
  `RELEASE`) plus simultaneous joint-action resolution specifically so
  they can coordinate; `claimed_by`/`my_claim` exist to keep the two
  agents from working the same package or blocking each other's path.

## Independent Baseline

`ExampleBaselineAgent` (`gridworld/agents.py`) uses only local percepts and
its own memory — it never sends or reads a message and has no concept of
a claim.

- **Local memory**: `known_packages` (any package it has personally seen,
  forgotten again once seen empty — i.e. someone else took it) and
  `base_location`, both populated by `_update_memory` from
  `percept.visible_cells` alone.
- **Decision rule**: if carrying, walk toward `base_location` and drop
  once there (or wander, `_explore`, if the base hasn't been seen yet); if
  standing on a package, pick it up; otherwise walk toward the nearest
  *known* package by straight-line (Manhattan) distance, or wander if none
  are known yet.
- **Limitations by design**: no messages means two baseline agents can
  both head for the same package with neither aware of the other — the
  only thing that stops them is the environment's own collision block,
  which the agent doesn't try to avoid or recover from. It also has no
  obstacle-aware pathfinding — `_move_toward` only ever asks "which
  legal move reduces Manhattan distance," so a wall it can't see around
  will make it wander rather than deliberately detour.

## Coordinated Policy

`CoordinatedAgentTemplate` (`gridworld/agents.py`) extends the same
`reset()`/`act()` shape with local memory it builds from percepts *and*
messages, plus a claim protocol so the two agents divide work instead of
duplicating or blocking it.

**Memory**: `known_packages` and `base_location` (as in the baseline),
plus `known_terrain` (every terrain type ever observed, for pathfinding),
`known_out_of_bounds` (cells inferred to be off the grid — see
Pathfinding below), `claimed_by` (position → claiming agent id, built
from both its own claims and teammates' messages), and `my_claim` (the
one position this agent currently owns).

**Messages** (`act()`'s TODO 4 block), at most one sent per step, checked
in this priority order so only one ever fires:

1. **RELEASE** — sent when a delivery just completed (`last_result`
   shows `DROPPED`) or the agent's own claimed target became unreachable
   or was reassigned (`choose_target != my_claim`). Frees the claim for
   someone else.
2. **CLAIM** — sent when the agent commits to a new package target it
   doesn't already own. It also self-registers in its own `claimed_by`
   immediately, since it will never receive its own broadcast back.
3. **DISCOVER** — sent when a package enters `known_packages` this step
   that wasn't there before, so a teammate who can't see it yet still
   learns it exists.

**Claim tie-break rule.** Two agents can independently claim the same
package in the same step, before either has heard from the other (see
the event-log excerpt below). The rule, applied when processing an
incoming `CLAIM`: **the lower `agent_id` wins.** An incoming claim only
overwrites what's on record if `message.sender < current_holder`
(`agents.py`, the `MessageKind.CLAIM` branch) — so an agent that already
registered its own claim never loses it to a later, alphabetically-higher
challenger, and the challenger correctly yields once it hears back.

**Target selection** (TODO 3) prefers, in order: the base (if carrying),
the current cell (if it holds a package), else the nearest *unclaimed*
known package — "unclaimed" meaning `claimed_by` has no entry, or the
entry names this agent itself (so an agent doesn't lose its own claimed
target to its own filter).

**Pathfinding** (`_plan_route`) replaces the baseline's straight-line
heuristic with a fresh breadth-first search every step over
`known_terrain`. Cells never observed are treated as passable so the
agent can still plan toward unexplored territory; cells confirmed
`Terrain.OBSTACLE` are avoided. `known_out_of_bounds` exists because
`visible_cells` is guaranteed to contain every in-bounds cell in the
local window — so a cardinal neighbor missing from it means "off the
grid," not "unexplored," and without tracking that the planner can
compute fake shortcuts through space that isn't actually on the map.

**Known limitation — collision recovery is partial.** `_resolve_blocked_move`
reacts to a `BLOCKED_COLLISION` result by advancing to the next direction
in the agent's own `exploration_order` rather than repeating the exact
move that just failed, which resolves a simple head-on standoff. It does
not fully solve a narrow-doorway conflict where both agents' shortest
path keeps pulling them back to the same contested cell after backing
off — see the Analysis write-up for a traced example.

## Results

Three fixed maps, per the lab's requirement — `starter_world()`,
`map2_world()`, and `map3_world()` in `gridworld/scenarios.py`. Each has a
different base corner, wall orientation/gap position, and package split
between "same side as base" and "must cross the bottleneck."

| Run | Policy | Deliveries | Score | Collision attempts | Steps |
|---|---|---|---|---|---|
| Map 1 (starter) | Baseline (`ExampleBaselineAgent`) | 1 | -123 | 0 | 60 |
| Map 1 (starter) | Coordinated (`CoordinatedAgentTemplate`) | 3 | -89 | 0 | 60 |
| Map 2 | Baseline | 1 | -123 | 0 | 60 |
| Map 2 | Coordinated | 2 | -214 | 36 | 60 |
| Map 3 | Baseline | 0 | -500 | 120 | 60 |
| Map 3 | Coordinated | 2 | -184 | 26 | 60 |

Two results stand out:

- **Map 3, Baseline — 120/120 decisions blocked.** Both agents' greedy
  targeting converges on the same package, `(1, 6)`, from opposite
  directions, and `ExampleBaselineAgent` has no way to recover from a
  block — so it never breaks. The baseline's designed weakness, on full
  display.
- **Map 2, Coordinated — 36 collisions.** The same narrow-doorway limit
  cycle described under Coordinated Policy's known limitation: both
  agents contest the cell next to base, briefly diverge and succeed, then
  walk right back into it since the planner has no memory of the failed
  attempt. Reproducible here, unlike the deleted random seed that first
  found it.

## Selected Event Log

**The simultaneous-claim race and its tie-break, package `(1, 1)`:**

```
t=00 robot-1  pos=(0,1)  recv=[]                              sent=claim@(1,1)    action=(SOUTH,NONE)  -> (1,1)
t=00 robot-2  pos=(2,0)  recv=[]                              sent=claim@(1,1)    action=(NORTH,NONE)  -> (1,0)
t=01 robot-1  pos=(1,1)  recv=[claim@(1,1) from robot-2]      sent=-              action=(WAIT,PICKUP) -> picked up
t=01 robot-2  pos=(1,0)  recv=[claim@(1,1) from robot-1]      sent=release@(1,1)  action=(SOUTH,NONE)  -> (2,0)
```

Both agents claim `(1, 1)` at `t=0`, before either has heard from the
other. At `t=1` each processes the other's message: `robot-1`'s own
recorded claim survives (`"robot-2" < "robot-1"` is false), `robot-2`'s
loses (`"robot-1" < "robot-2"` is true), so `robot-2` releases and
`robot-1` proceeds to pick up the package that same step.

**A DISCOVER causing a teammate to claim a package it hadn't seen,
`(5, 6)`:**

```
t=15 robot-2  pos=(6,6)  carrying=True   sent=discover@(5,6)
t=16 robot-1  pos=(7,0)  recv=[discover@(5,6) from robot-2]  sent=claim@(5,6)
```

`robot-1` is on the far side of the map at `(7, 0)` with no way to see
`(5, 6)` itself; the DISCOVER message is the only reason it learns the
package exists at all, and it claims it the very next step.

## Testing

`python -m unittest discover -s tests -v` runs 23 tests. The lab's
required categories map onto:

| Required category | Covered by |
|---|---|
| Collision resolution | `GridWorldContractTests.test_same_destination_blocks_both_agents`, `test_attempted_swap_is_also_blocked` |
| Exactly-once delivery | `GridWorldContractTests.test_a_package_is_delivered_exactly_once` |
| Message timing | `GridWorldContractTests.test_message_sent_at_t_is_available_at_the_next_decision` |
| Respecting an existing claim | `ChooseTargetTests.test_a_package_claimed_by_another_agent_is_skipped` |
| Claim message delivery | `MessagePassingTests.test_claim_message_is_received_by_other_agent` |
| Local memory (perceive cells) | `PerceiveCellsTests`, `PerceiveCellsIntegrationTests` |
| Pathfinding around obstacles | `PathfindingTests` |

# Lab 2 Write-Up Outline

Scaffold mapped directly to the PDF's required sections and the Evaluation
Criteria table. Fill in the bracketed placeholders; the bullets under each
are what the PDF explicitly asks that section to contain. Where this
session already produced usable evidence, it's noted inline — pull the
exact numbers from your own latest run before citing them, since they'll
shift as you keep changing the agent.

---

## Deliverable A — Source Code

- [ ] Environment (`gridworld/environment.py`) — done, unmodified this session.
- [ ] Agent policies (`gridworld/agents.py`) — `ExampleBaselineAgent` (unmodified
      baseline) + `CoordinatedAgentTemplate` (TODOs 1-5 implemented).
- [ ] Automated tests (`tests/`) — 23 tests across `test_environment.py` and
      `test_coordinated_agent.py`. List what each class covers when you
      write the "Test outcomes" section below.

## Deliverable B — README and Evidence

Checklist items below map to the PDF's "Final Submission Checklist." Add
whichever of these aren't already in `README.md`.

### 1. PEAS and Task-Environment Classification

- [ ] **Performance** — the score formula (+10 delivery, -1 move, -2
      invalid, -3 collision, -5 undelivered at horizon).
- [ ] **Environment** — 8x8 grid, one base, obstacles incl. one intentional
      bottleneck, 4 packages, 2 agents, 60-step horizon.
- [ ] **Actuators** — move N/S/E/W/WAIT, PICKUP, DROP, one message per step.
- [ ] **Sensors** — local 3x3 `visible_cells`, `carrying`, `last_result`,
      `time`, `messages`.
- [ ] **Task-environment properties**, each justified from the simulator,
      not asserted:
  - Discrete (grid cells, discrete actions, discrete time steps)
  - Sequential (current action affects future percepts/state)
  - Partially observable (only a 3x3 window; `known_terrain`,
    `known_packages` in the agent are memory compensating for this —
    cite `_update_memory`)
  - Dynamic (the other agent changes the world between your decisions —
    positions, packages, claims)
  - Cooperative multi-agent (shared team score, message protocol,
    `claimed_by` used to avoid interference)

### 2. Independent Baseline

- [ ] Describe `ExampleBaselineAgent`'s percepts/local memory/rule from its
      docstring and `act()`: no messages, no claims, nearest-known-package
      greedy targeting, round-robin `_explore()`.
- [ ] State its limitations plainly (this is the point of the baseline):
      no coordination, so two agents can converge on the same package with
      neither aware, and it has no obstacle-aware pathfinding at all.
- [ ] Run it once on the starter map and record: deliveries, score,
      collisions, steps, for the results table below.

### 3. Coordinated Policy

- [ ] **Messages**: DISCOVER (new local sighting), CLAIM (committing to a
      target), RELEASE (delivery or abandoned goal) — cite the exact
      trigger logic in `act()`'s TODO 4 block.
- [ ] **Memory**: `known_packages`, `known_terrain`, `known_out_of_bounds`,
      `claimed_by`, `my_claim` — what each one is for.
- [ ] **Claim tie-break rule** (document this explicitly, the PDF requires
      it by name): lowest `agent_id` wins a simultaneous CLAIM conflict —
      `agents.py`'s `MessageKind.CLAIM` handler, `if current is None or
      message.sender < current`.
- [ ] **Pathfinding**: BFS over remembered terrain (`_plan_route`),
      replanned every step, treating unseen cells as passable except
      confirmed off-grid ones (`known_out_of_bounds`) — this is what lets
      it route around the wall instead of the greedy heuristic oscillating.
- [ ] Note the environment's own collision rule (same-destination, swap,
      and move-into-a-stationary-agent are all blocked) vs. what the agent
      does about it — the `_resolve_blocked_move` reactive diversion, and
      its known limit (see Limitations).

### 4. Results Table

Done — `map2_world()` and `map3_world()` are now in `scenarios.py`
alongside `starter_world()`, and the full table is in the README's
Results section (copy it from there rather than retyping). Two results
in it are flagged with an explanation, not just numbers: Map 3's baseline
run hits 120/120 collisions (a total, permanent deadlock — see the
README for why), and Map 2's coordinated run reproduces the same
narrow-doorway limit cycle the "Known limitation" note under Coordinated
Policy describes, now on a map that stays in the repo instead of a
deleted random seed.

| Run | Policy | Deliveries | Score | Collisions | Steps |
|---|---|---|---|---|---|
| Map 1 (starter) | Baseline | 1 | -123 | 0 | 60 |
| Map 1 (starter) | Coordinated | 3 | -89 | 0 | 60 |
| Map 2 | Baseline | 1 | -123 | 0 | 60 |
| Map 2 | Coordinated | 2 | -214 | 36 | 60 |
| Map 3 | Baseline | 0 | -500 | 120 | 60 |
| Map 3 | Coordinated | 2 | -184 | 26 | 60 |

### 5. Event Log Excerpts

Pull 10-20 lines showing message-to-action causality, not just raw noise.
Good candidates from this session's traces:

- The simultaneous-claim race and its resolution: both robots CLAIM
  `(1, 1)` at `t=0`; the tie-break (lower `agent_id`) is decided when each
  processes the other's message at `t=1`; the loser sends RELEASE.
- A DISCOVER causing the *other* agent to claim and deliver a package it
  never would have seen on its own (`t=15` DISCOVER `(5, 6)` → `t=16`
  CLAIM by the other robot in the actual trace).
- One collision-log entry showing `BLOCKED_COLLISION` and the resulting
  `-3` penalty, if your chosen maps produce one.

### 6. Test Outcomes

List the required categories and which test class covers each:

- [ ] **Collision** — `GridWorldContractTests.test_same_destination_blocks_both_agents`,
      `test_attempted_swap_is_also_blocked`.
- [ ] **Delivery exactly once** — `test_a_package_is_delivered_exactly_once`.
- [ ] **Message timing** — `test_message_sent_at_t_is_available_at_the_next_decision`.
- [ ] **Claim behavior** — `PathfindingTests`, `ChooseTargetTests`
      (respecting claims), `MessagePassingTests`, plus the CLAIM tie-break
      itself (not currently under a dedicated test — worth adding one that
      exercises the `message.sender < current` branch directly if you
      want it "tested," not just "observed in a full-map run").

---

## Analysis (750-1000 words, separate document)

Follow the PDF's six-part structure — it's also the grading rubric. This
version threads one central thesis through it, per your call to lead with
it: **the bottleneck's geometry, not agent intelligence, caps the team
score below zero on this map.** Word budgets below are a starting split
of the 750-1000 total, not a hard rule.

### 1. PEAS and classification (~120 words)

Condense the README's PEAS section into prose. Plant the thesis here as a
single forward-pointing sentence while describing the **Environment**
property — the PDF requires "one intentional bottleneck" as a map
feature; note here that this bottleneck turns out to do more than add
difficulty (developed fully in §6). Don't argue it yet, just flag it so
the reader isn't surprised later.

### 2. Independent baseline (~90 words)

Condense the README's Independent Baseline section: local-only memory,
greedy Manhattan targeting, no obstacle-awareness, no coordination.

### 3. Coordinated policy (~160 words)

Condense the README's Coordinated Policy section. Must explicitly name
the **claim tie-break rule** (lower `agent_id` wins) — the PDF requires
this named, not just implied. Cover messages (DISCOVER/CLAIM/RELEASE
triggers), the claim-respecting target selection, and the BFS pathfinding
briefly.

### 4. Results (~140 words)

Present the results table (fill in all three maps/seeds — see the gap
noted in §4 of the README section above). Then interpret it, don't just
report it: coordination roughly tripled deliveries and cut the deficit by
about a third (`-123 → -89` on the starter map) — a large *relative*
improvement. But note the number that sets up §6: **both runs are deeply
negative**, and the gap between "bad" (-123) and "much better" (-89) is
still nowhere near zero. That's the pivot into the bottleneck argument:
if even the improved policy stays this negative, ask whether more
coordination could ever close the rest of the gap.

### 5. Causal evidence (~110 words)

Cite one message-to-action pair with an exact time step from the README's
Selected Event Log — the `(1, 1)` simultaneous-claim tie-break (`t=0`→`t=1`)
is the cleaner one since it shows the *rule* deciding an outcome, not just
information sharing. Keep this section focused on this one requirement;
save the bottleneck argument for §6 so the two don't get tangled.

### 6. Limitations / extension — the bottleneck argument (~250-300 words)

This is the section to lead with the thesis and prove it, not just
mention it as one bullet among several:

1. **State the claim plainly first**: on this map, no policy — however
   well-coordinated — can achieve a positive score. This is a structural
   property of the task environment, not a defect in the agent.
2. **Show the ceiling on the reward side**: only `+10` per delivery exists
   as a positive term, and there are exactly 4 packages, so `+40` is the
   hard maximum any run can ever earn, independent of policy.
3. **Show the floor on the cost side**, with the actual numbers computed
   this session:
   - Base is fixed at `(0, 0)`; the wall's only gap is at `(7, 3)`; every
     west↔east crossing must pass through that one cell.
   - Carry capacity is 1 and `DROP` only succeeds at `(0, 0)` exactly —
     no relay between agents, no secondary depot — so every delivery is
     an independent full round trip.
   - Round-trip distances (shortest path respecting obstacles, not raw
     Manhattan): `(1,1)`→4, `(0,6)`→40, `(5,6)`→30, `(7,6)`→26. Sum ≈ 100
     moves minimum to deliver all four, even for a perfect omniscient
     planner making zero wasted steps.
   - `40 - 100 = -60`: the ceiling, before counting any collision,
     invalid-move, or undelivered-package penalty at all.
4. **Connect it back to the task-environment classification from §1**:
   this is exactly the kind of thing "distinguish observed behavior from
   assumptions about agent reasoning" (an explicit PDF instruction) is
   asking for — a naive read of the `-89` result says "the policy is bad
   at this task"; the math says the task itself is unwinnable by score,
   and `-89` is actually *closer* to the `-60` ceiling than it looks once
   you count the delivery count achieved.
5. **Extension**: name what would have to change in the *environment*,
   not the agent, for a positive score to become reachable — e.g. a
   second drop-off point nearer the east side, rebalanced move/delivery
   weights in the score formula, or fewer mandatory long-haul packages.
   This doubles as your answer to "how would the design change in a
   competitive setting" if you want to fold that analytical question in
   here instead of a separate paragraph.

### Analytical questions to make sure the prose answers somewhere

- [ ] What did each agent know, and what was missing because sensing was local?
- [ ] How did a message or claim allocate work or prevent interference?
- [ ] Which score terms explain the performance difference? — **this is
      the bottleneck argument's real home**: most of the `-89` is the
      unavoidable `-1`-per-move cost of a ~100-move minimum job, not
      penalties a smarter policy could have avoided.
- [ ] What failure or edge case remains, and why? — the bottleneck ceiling
      *is* a valid answer here, distinct from the narrow-doorway deadlock
      (a real but separate, policy-level bug you could mention as a
      secondary point if word count allows).
- [ ] How would the design change in a competitive setting? — can double
      up with the extension paragraph in §6.

---

## Final Submission Checklist (verbatim from the PDF — check each)

- [ ] Environment includes the required grid, base, obstacles, packages, and bottleneck.
- [ ] Independent and coordinated policies use the same environment and maps or seeds.
- [ ] Collision, delivery, message-timing, and claim tests pass.
- [ ] Event logs include time, agent, percept, message, action, and result.
- [ ] Results table reports deliveries, score, collision attempts, and steps.
- [ ] PEAS and task-environment classification are in the README or report.
- [ ] Analysis cites specific log entries and compares both policies.
- [ ] README explains how to run the simulator, tests, and experiments.

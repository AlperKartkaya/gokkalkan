# Çelikkubbe Final Phase Simulation Specification

**Purpose of this file:** define what a coding agent should build when creating a simulator for the **final phase** of the TEKNOFEST 2026 Çelikkubbe Hava Savunma Sistemleri competition.

This is **not** a fictional scenario script. The simulator must reproduce the **real final competition flow** as specified in `sartname_v5.pdf`, especially the three final stages, the manual/autonomous mode differences, the parkour diagrams, the scoring rules, and the interaction requirements.

The simulator should behave like a practice environment for competitors. It should visualize the targets on the real competition-style parkour map, move them along the same conceptual paths shown in the specification diagrams, apply the same scoring logic, and guide the user with an optional contextual onboarding/tutorial.

---

## 1. Core Product Goal

Build an interactive simulation of the final competition where:

1. The user can play through **Stage 1, Stage 2, and Stage 3**.
2. The simulator uses the **parkour/map visuals from the official specification** as the visual reference.
3. Aircraft/targets move along the paths shown in the official parkour diagrams.
4. The simulator assumes perfect sensing:
   - radar/lidar/vision always detects target position correctly,
   - dost/düşman classification is always correct,
   - target type classification is always correct where the competition requires it.
5. The simulator does **not** invent a custom story. It reproduces the competition mechanics.
6. User interaction must match the competition mode:
   - Stage 1 requires manual aiming/fire behavior.
   - Stage 2 is autonomous in the real competition, so the simulator should model automatic target tracking/engagement unless the simulator is being used in an optional manual-practice mode.
   - Stage 3 is autonomous target selection/engagement, with correct dost/düşman and target-type logic.
7. Scoring must be calculated as close as possible to the official rules.
8. Any missing physical details from the official document must be explicit, configurable, and marked as **not specified in the source document**.

---

## 2. Important Source-Document Constraints

The official specification gives some dimensions and behavior, but it does **not** fully define every physical simulation parameter.

### 2.1 Explicitly specified

The document explicitly specifies:

- The competition has **3 final task stages**.
- The air defense system starts each test with:
  - elevation axis: `0°`
  - lateral/yaw axis: `0°`
- Stage 1 is fully **manual**.
- Stage 2 is **autonomous**.
- Stage 3 is also autonomous-like in operation: it must detect the hostile target among incoming targets, select the correct target, and destroy it at the correct distance.
- Before the competition, teams get **30 minutes** for setup and preparation.
- Teams may perform test shots during preparation.
- Maintenance breaks may be requested after competition start:
  - total maintenance budget across all 3 stages: `10 minutes`
  - every maintenance request consumes at least `30 seconds`
  - longer maintenance consumes the real elapsed maintenance time
- Emergency stop is required.
- Explosives are forbidden as target destruction solution.
- The competition uses target distances / range bands:
  - `5 m`
  - `10 m`
  - `15 m`
- Stage 1 target distances are approximately `5 m`, `10 m`, and `15 m`.
- Stage 2 and Stage 3 parkour diagrams include range markers labeled:
  - `15 metre`
  - `10 metre`
  - `5 metre`
- Stage 2 uses 3 lanes/branches.
- Stage 2 has 4 rounds.
- Stage 2 has 3 targets per round, one target per lane/branch.
- Stage 3 has 8 rounds.
- Stage 3 has 3 moving targets per round:
  - 1 hostile target that must be destroyed,
  - 2 friendly targets that must not be destroyed.
- Stage 3 uses red arrows for hostile targets and blue arrows for friendly targets in the official diagram.
- For Stage 3, valid engagement distances depend on target type:
  - F16: valid from `10 m` to `15 m`; hits closer than 10 m do not count.
  - Helicopter and Ballistic Missile: valid from `5 m` to `15 m`; hits closer than 5 m do not count.
  - Mini/Micro UAV: valid from `0 m` to `15 m`.

### 2.2 Not specified and therefore must be configurable

The document does **not** precisely specify:

- exact physical parkour width and length,
- exact target physical dimensions,
- exact aircraft/target speed,
- exact route coordinates,
- exact turn radii,
- exact target acceleration/deceleration,
- exact simulation frame rate,
- exact size of the balloon attached to targets,
- exact image pixel positions for the map,
- exact weapon projectile model,
- exact hit radius / hitbox tolerance,
- exact firing cooldown,
- exact target spawn schedule within a round, except that Stage 2 and Stage 3 describe targets moving from A to B and one full A-to-B traversal as one round.

Therefore, implement these as configuration values. Do **not** hard-code invented “official” values. Use reasonable defaults, but label them as simulator defaults.

---

## 3. Required Visual Approach

### 3.1 Use official parkour images as map backgrounds

The simulator should use the official diagrams as the visual basis:

- **Stage 2 map:** page 17, Figure 4, “Aşama 2 Temsili Gösterim”
- **Stage 3 map:** page 19, Figure 5, “Aşama 3 Temsili Gösterim”
- **Stage 1 map:** page 15, Figure 2, “Aşama 1 Temsili Gösterim”

For Stage 2 and Stage 3, the document shows two views:

1. a 3D perspective representation of the parkour,
2. a top-down map representation.

The simulator should use the **top-down map** as the playable background because it is easier to map coordinates, paths, range bands, target positions, and user interactions.

### 3.2 Do not draw a different fictional parkour

Do not replace the parkour with a generic canvas unless the official image cannot be loaded. The preferred implementation is:

1. Extract/crop the official top-down parkour from the PDF page.
2. Use that cropped image as the canvas/map background.
3. Overlay simulated moving targets on top of it.
4. Overlay the air defense system position.
5. Overlay optional range bands, target paths, and tutorial highlights.

Fallback only if image extraction is not available:

- redraw the map using the same structure:
  - long rectangular arena,
  - three horizontal lanes,
  - left-side start region A,
  - right/top-right end region B,
  - defense system on the right side,
  - range markers 15 m, 10 m, 5 m along the top,
  - wavy paths from left to right,
  - right-side return/exit segment near B.

---

## 4. Coordinate System and Scaling

Use a simulation coordinate system in **meters** and map it to pixels.

### 4.1 Recommended coordinate convention

Use:

```text
x = horizontal distance from the air defense system toward the incoming target field
y = lateral position across the width of the field
```

However, the official top-down diagrams visually place the defense system on the **right side**, while targets generally start on the **left side** and move toward/rightward near the system. So for rendering:

```text
world distance from system = range_m
range_m = 0 at the defense system / near right-side system position
range_m = 15 near the left-side 15 m marker
```

For screen coordinates:

```text
screen_x = map function of range_m, usually reversed:
  larger range_m appears further left
  smaller range_m appears closer to the system on the right

screen_y = lane/branch position
```

### 4.2 Calibration using the map image

Because the exact physical size of the parkour is not fully specified, calibrate the map using the visible range labels in the official image.

The top edge of the Stage 2 and Stage 3 diagrams shows vertical range markers labeled approximately:

```text
15 metre    10 Metre    5 Metre
```

Use these labels as the meter-to-pixel calibration references.

Implementation approach:

```text
Define calibration anchor points on the cropped top-down map:

stageMap.calibration = {
  rangeMarkers: {
    "15m": { pixelX: <x coordinate of 15m marker> },
    "10m": { pixelX: <x coordinate of 10m marker> },
    "5m":  { pixelX: <x coordinate of 5m marker> },
    "0m":  { pixelX: <x coordinate of system/engagement line> } // inferred/configurable
  }
}
```

Important:

- The `15m`, `10m`, and `5m` labels are explicit in the official diagrams.
- The exact `0m` line is not explicitly labeled. Infer it as the region near the air defense system / near right-side blue boundary, but keep it configurable.
- Do not claim that the inferred 0 m line is official.

### 4.3 Scaled target sizes

The user wants “same sizes, scaled of course.” The official document does not provide exact model dimensions. Therefore:

- Use the target images/types from the specification as visual categories.
- Use configurable display sizes for each target type.
- Provide a global scale factor.
- Keep default values symbolic/configurable rather than pretending exact official model dimensions are known.

Example:

```ts
targetVisualScale = {
  ballisticMissile: 1.0,
  helicopter: 1.0,
  f16: 1.0,
  miniMicroUav: 0.75
}
```

If later real measurements are obtained, they should be inserted into the configuration without changing simulation logic.

---

## 5. Stage 1 — Static Targets at Different Ranges

### 5.1 Real competition behavior

Stage 1 is the manual stage.

The system must:

1. Start at yaw/lateral axis `0°` and elevation axis `0°`.
2. Present static targets at approximately:
   - 5 m,
   - 10 m,
   - 15 m.
3. Use the same set of 4 target types across all ranges:
   - Ballistic Missile,
   - Helicopter,
   - Fighter Jet / F16,
   - Mini/Micro UAV.
4. Give the team a random target order in an envelope after preparation.
5. Require the team to destroy targets in that order.
6. Penalize wrong-order destruction.
7. Require manual user commands:
   - aim/turn,
   - fire,
   - move to next target,
   - fire again.

### 5.2 User interaction model

In the simulator, Stage 1 should include:

- target list/order panel,
- current required target indicator,
- manual aiming controls,
- fire button,
- timer,
- score display,
- wrong target warning.

The user must press **Fire**. If the user does not press Fire, no target is destroyed and the timer continues. This matches manual mode.

### 5.3 Stage 1 scoring

Official scoring:

| Event | Points |
|---|---:|
| Near range target destroyed | +5 |
| Medium range target destroyed | +10 |
| Long range target destroyed | +20 |
| Maximum base points | 80 |
| Wrong target destroyed | -5 |
| Time limit | 5 minutes |
| Bonus time points | up to but less than 20 |

Bonus formula:

```text
Bonus Süre Puanı = 20 × (remaining seconds / 300)
```

Only teams that get 80 points receive the time bonus.

Implementation:

```ts
if stage1.baseScore === 80:
    bonus = 20 * (remainingSeconds / 300)
else:
    bonus = 0
stage1.total = baseScore + bonus - penalties
```

Minimum to advance to Stage 2:

```text
30 points
```

### 5.4 Stage 1 edge cases

Implement:

- Firing at empty space: no score change, optional “miss” event.
- Firing at wrong target type/order: `-5` penalty.
- Destroying a correct target but at wrong order should count as wrong-order penalty and should not progress the expected-order pointer unless configured otherwise.
- Time reaches 0: stage ends immediately.
- Perfect score before time ends: end stage and compute bonus.
- Emergency stop: pause/stop according to emergency-stop state.
- Maintenance: pause timer and consume maintenance budget.

---

## 6. Stage 2 — Swarm Attack and Target Destruction

### 6.1 Official behavior

Stage 2 is autonomous.

The team:

1. powers/starts the system,
2. switches to autonomous mode,
3. waits for the system to perform:
   - automatic target detection,
   - automatic target tracking,
   - automatic destruction.

In the simulator, since sensing is assumed perfect, the key simulation should be:

- targets move on the official paths,
- the simulated defense system knows their locations,
- engagement logic can destroy them automatically,
- scoring follows the official rules.

### 6.2 Parkour from page 17 / Figure 4

The Stage 2 diagram shows:

- a long rectangular arena,
- a start point labeled **A** on the left side,
- an end point labeled **B** near the upper-right/right-side end,
- three separate horizontal lanes/branches,
- each lane has a wavy route,
- the three targets move from A-side toward B-side,
- arrows on each lane show target direction,
- the defense system is placed on the right side of the map,
- the top side of the map includes range labels:
  - `15 metre`,
  - `10 Metre`,
  - `5 Metre`,
- the 3D view shows red/orange tracks and green target markers distributed through the lane paths.

### 6.3 Stage 2 route interpretation for simulation

Implement the Stage 2 parkour as three predefined routes:

```text
Route S2-L1: upper lane
Route S2-L2: middle lane
Route S2-L3: lower lane
```

Each route:

- starts near the left/A side,
- follows a wavy path,
- progresses toward the right/B side,
- ends when it exits/reaches the B region,
- represents one target's movement during a round.

A full traversal from A to B equals one round for that target. A competition round ends when all three active targets have either:

- been destroyed, or
- reached/exited B.

### 6.4 Stage 2 targets

Stage 2 uses target mockups planned as:

- Ballistic Missile
- Mini/Micro UAV

The document states that **target type classification is not expected** in this stage.

Therefore:

- do not require the user/system to classify target type in Stage 2,
- every target is simply an enemy target to destroy,
- use target visuals randomly or by configuration from `ballisticMissile` and `miniMicroUav`.

### 6.5 Stage 2 rounds

Official rule:

```text
Stage 2 has 4 rounds.
Each round has 3 targets total.
There is one target in each lane/branch.
At the start of every round, all targets are present in the parkour.
If targets are destroyed in a round, they are replaced before the next round.
```

Simulator behavior:

```text
for round in 1..4:
    spawn 3 hostile targets:
        one on upper route
        one on middle route
        one on lower route
    start all targets at A-side spawn points
    move them toward B
    allow autonomous engagement
    when every target is destroyed or has exited at B:
        calculate round score/penalty
        start next round
```

### 6.6 Stage 2 scoring

Official scoring:

| Round result | Points |
|---|---:|
| 1 target destroyed in a round | +5 |
| 2 targets destroyed in a round | +15 |
| 3 targets destroyed in a round | +30 |
| Maximum total | 120 |
| Target-miss penalty | -5 |

Important interpretation:

- The table gives score **per round**.
- Four perfect rounds = `4 × 30 = 120`.

Implement:

```ts
function scoreStage2Round(destroyedCount: number): number {
  if destroyedCount === 3) return 30;
  if destroyedCount === 2) return 15;
  if destroyedCount === 1) return 5;
  if destroyedCount === 0) return -5; // target miss penalty
}
```

The document says the `-5` is the target-miss penalty applied per round. If the team cannot hit targets for 3 rounds, they fail the stage and receive 0 points for the stage.

Implementation:

```ts
missRounds = number of rounds where destroyedCount === 0

if missRounds >= 3:
    stage2.totalScore = 0
    stage2.failed = true
```

Minimum to advance to Stage 3:

```text
20 points
```

### 6.7 Stage 2 timing and speed

The official document does **not** specify the exact target speed or round duration. It says there is no time limit other than completing 4 rounds.

For the simulator:

- include `targetSpeedMps` as a required configuration value,
- do not hard-code it as official,
- use the same speed for all Stage 2 targets unless configuration says otherwise,
- allow the speed to be adjusted once real competition speed information is available.

Example:

```ts
stage2Config = {
  rounds: 4,
  targetSpeedMps: DEFAULT_CONFIGURABLE_VALUE,
  routeCompletionDefinesRound: true,
  oneTargetPerLane: true
}
```

The prompt says “move exactly in the speed they would in the competition.” Since the official file does not provide the numeric speed, the simulator must support a config slot for the real speed and clearly show when it is using an assumed default.

### 6.8 Stage 2 edge cases

Implement:

- Target exits at B without being destroyed:
  - counts as missed for that target.
- Round ends with 0 hits:
  - apply `-5`.
- 3 rounds with no target hit:
  - stage fails and score becomes 0.
- Firing/engagement at a target already destroyed:
  - no extra points.
- Duplicated hit on same target:
  - count only first valid destruction.
- Target type classification:
  - ignore for scoring.
- User manual fire button in Stage 2:
  - not required in official autonomous mode.
  - If present for debugging/practice, label it clearly as non-official/manual-practice mode.
- Perfect sensing:
  - detection failure should not occur unless explicitly enabling “sensor fault mode,” which should be off by default.

---

## 7. Stage 3 — Moving Targets at Different Layers, Dost/Düşman Logic

### 7.1 Official behavior

Stage 3 requires the system to:

1. observe incoming moving targets,
2. identify the hostile target,
3. avoid friendly targets,
4. determine the hostile target type,
5. destroy it at the correct distance band,
6. repeat over 8 rounds.

### 7.2 Parkour from page 19 / Figure 5

The Stage 3 diagram shows:

- the same general rectangular parkour style as Stage 2,
- three horizontal movement lanes,
- range labels at the top:
  - `15 metre`,
  - `10 Metre`,
  - `5 Metre`,
- the defense system on the right side,
- colored arrow markers on the top-down map:
  - **red arrows = hostile / enemy targets**,
  - **blue arrows = friendly targets**,
- each round contains three incoming targets,
- one red hostile target must be engaged,
- two blue friendly targets must not be engaged,
- target motion again follows A-to-B style traversal as defined in Stage 2.

### 7.3 Stage 3 route interpretation for simulation

Use the same route structure as Stage 2:

```text
Route S3-L1: upper lane
Route S3-L2: middle lane
Route S3-L3: lower lane
```

Each round should spawn:

```text
1 hostile target on one of the three routes
2 friendly targets on the remaining routes
```

The exact lane assignment should be configurable/randomized.

For a faithful practice simulator:

- randomize which lane contains the hostile target each round,
- randomize hostile target type according to config,
- optionally randomize friendly target types/colors,
- keep the distinction visible to the simulator engine but optionally hidden from the competitor UI if desired.

Because the user requested perfect radar/lidar and correct dost/düşman classification, the default UI may show friendly/enemy status correctly. However, to practice real reaction, there can be a toggle:

```text
showClassificationOverlay = true/false
```

Default for this project request:

```text
showClassificationOverlay = true
```

### 7.4 Stage 3 target types and valid engagement distance

Stage 3 scoring depends on hostile target type.

| Hostile target type | Valid engagement range | Points |
|---|---:|---:|
| F16 / Fighter Jet | 10 m to 15 m | +30 |
| Helicopter | 5 m to 15 m | +20 |
| Ballistic Missile | 5 m to 15 m | +20 |
| Mini/Micro UAV | 0 m to 15 m | +10 |

Rules:

- If F16 is destroyed closer than 10 m, it does not count.
- If Helicopter or Ballistic Missile is destroyed closer than 5 m, it does not count.
- Mini/Micro UAV can be destroyed anywhere from 0 m to 15 m.
- Targets beyond 15 m are outside the official scoring range shown in the diagrams and should not count unless configured otherwise.

### 7.5 Stage 3 rounds

Official rule:

```text
Stage 3 is performed over 8 rounds.
Each round has 1 hostile target and 2 friendly targets moving toward the system.
Round definition is identical to Stage 2: target movement from A to B is one full round.
```

Simulator behavior:

```text
for round in 1..8:
    choose hostile lane
    choose hostile target type
    spawn hostile target on hostile lane
    spawn friendly targets on other two lanes
    move all targets along their lane paths
    wait until:
        hostile target is destroyed, or
        all targets exit/reach B, or
        stage is stopped
    score the round
```

### 7.6 Stage 3 scoring

Official scoring:

| Event | Points |
|---|---:|
| F16 hostile target destroyed at valid range | +30 |
| Helicopter hostile target destroyed at valid range | +20 |
| Ballistic Missile hostile target destroyed at valid range | +20 |
| Mini/Micro UAV hostile target destroyed at valid range | +10 |
| Maximum total | 160 |
| Friendly target hit and/or hostile target not hit | -10 max per round |

The document says:

- If a friendly target is hit and/or the hostile target is not hit, penalty applies.
- Maximum penalty per round is limited to `10 points`.
- If the team cannot hit the hostile target for 3 consecutive rounds, it fails the stage and receives 0 points for the stage.
- The team must get at least 10 points in Stage 3 to be considered successful / eligible for prize ranking.

Implementation:

```ts
function scoreStage3Round(round) {
  let score = 0;
  let penalty = 0;

  if (round.hostileDestroyed && round.hostileDestroyedAtValidRange) {
    score += pointsForTargetType(round.hostileType);
  }

  if (round.friendlyHit || !round.hostileDestroyed || !round.hostileDestroyedAtValidRange) {
    penalty = 10;
  }

  return score - penalty;
}
```

Consecutive failure:

```ts
if hostile not validly destroyed in a round:
    consecutiveHostileMisses += 1
else:
    consecutiveHostileMisses = 0

if consecutiveHostileMisses >= 3:
    stage3.totalScore = 0
    stage3.failed = true
```

Minimum success threshold:

```text
Stage 3 success threshold = 10 points
```

### 7.7 Stage 3 edge cases

Implement:

- Friendly target hit:
  - apply penalty, max `-10` per round.
- Hostile target not hit before exit:
  - apply penalty, max `-10` per round.
- Hostile target hit at invalid distance:
  - do not award target points,
  - treat as hostile target not successfully destroyed,
  - apply penalty up to round max.
- Friendly target hit and hostile missed in same round:
  - still max `-10` penalty for that round, not `-20`.
- Hostile hit more than once:
  - count only first valid hit.
- Friendly target hit after hostile already destroyed:
  - still apply penalty for friendly hit in that round.
- Target reaches B:
  - if hostile and not validly destroyed, count as hostile miss.
  - if friendly, no penalty for simply exiting.
- Three consecutive hostile misses:
  - set entire Stage 3 score to 0 and fail stage.
- If a round score would be negative:
  - allow negative round scores unless the final competition system clamps stage score. The official text does not state a lower clamp except failure cases, so keep this configurable:
    `clampNegativeStageScore = false` by default, but allow true.

---

## 8. Exact Map/Parkour Implementation Guidance

### 8.1 Use path overlays, not physics free-movement

Targets should not fly freely. They should follow the lanes/path curves visible in the official diagrams.

Implementation model:

```ts
type Waypoint = {
  rangeM: number;
  laneOffsetM: number;
  screenX?: number;
  screenY?: number;
};

type Route = {
  id: string;
  stage: 2 | 3;
  lane: "upper" | "middle" | "lower";
  waypoints: Waypoint[];
};
```

The route engine should interpolate between waypoints.

Use either:

- Catmull-Rom spline interpolation,
- cubic Bezier segments,
- polyline interpolation with smoothing.

### 8.2 Stage 2 path shape

For Stage 2, create three wavy lanes matching Figure 4:

```text
Upper lane:
- starts from left/A side near the upper lane.
- moves rightward with smooth waves.
- approaches the right-side B region.
- turns upward near the right boundary into/near B.

Middle lane:
- starts from left/A side near the middle lane.
- moves rightward with a gentler wavy line.
- approaches the right-side B region.

Lower lane:
- starts from left/A side near the lower lane.
- moves rightward with smooth waves.
- approaches the right-side boundary.
- curves/turns down or toward the lower right exit/near B path.
```

The exact drawn paths in the PDF are illustrative, not given as numeric coordinates. Therefore, define route waypoints by manually tracing/clicking points on the extracted map image.

### 8.3 Stage 3 path shape

For Stage 3, use the same general three-lane movement model as Stage 2.

The top-down page 19 diagram shows red and blue arrows placed on the lanes, not fixed permanent aircraft positions. Treat these arrows as examples of target positions/directions along the route.

For each round:

- hostile target follows one lane,
- friendly targets follow the other lanes,
- all targets move toward the right/system side,
- targets follow the same route library as Stage 2 unless a specific Stage 3 map-specific route set is manually traced.

### 8.4 Recommended route-authoring workflow for the agent

The agent should implement a small route-authoring/config mode or hardcoded route config.

Best workflow:

1. Load the cropped official top-down image.
2. User/developer clicks route waypoints for each lane.
3. Save them into JSON:
   - `stage2_routes.json`
   - `stage3_routes.json`
4. Simulation uses the saved JSON routes.
5. Add a debug toggle:
   - show/hide route lines,
   - show/hide waypoints,
   - show/hide range bands.

Example route config shape:

```json
{
  "stage": 2,
  "mapImage": "assets/stage2_topdown.png",
  "rangeCalibration": {
    "15m": { "x": 80 },
    "10m": { "x": 300 },
    "5m": { "x": 520 },
    "0m": { "x": 690 }
  },
  "routes": [
    {
      "id": "S2-L1",
      "lane": "upper",
      "waypointsPx": [
        { "x": 40, "y": 115 },
        { "x": 155, "y": 110 },
        { "x": 250, "y": 145 },
        { "x": 380, "y": 185 },
        { "x": 560, "y": 150 },
        { "x": 650, "y": 95 }
      ]
    },
    {
      "id": "S2-L2",
      "lane": "middle",
      "waypointsPx": [
        { "x": 40, "y": 205 },
        { "x": 170, "y": 200 },
        { "x": 310, "y": 215 },
        { "x": 500, "y": 205 },
        { "x": 650, "y": 225 }
      ]
    },
    {
      "id": "S2-L3",
      "lane": "lower",
      "waypointsPx": [
        { "x": 40, "y": 285 },
        { "x": 165, "y": 275 },
        { "x": 305, "y": 255 },
        { "x": 480, "y": 265 },
        { "x": 640, "y": 310 }
      ]
    }
  ]
}
```

The numeric example above is only a placeholder. The agent should replace it with actual traced pixel coordinates from the cropped image.

---

## 9. Competition Flow Engine

### 9.1 Overall flow

Implement the final phase flow as:

```text
LOAD_SIMULATION
→ OPTIONAL_ONBOARDING
→ PREPARATION_PHASE
→ STAGE_1_MANUAL
→ CHECK_STAGE_1_THRESHOLD
→ STAGE_2_AUTONOMOUS
→ CHECK_STAGE_2_THRESHOLD
→ STAGE_3_AUTONOMOUS_DOST_DUSMAN
→ FINAL_SCORE_SUMMARY
```

### 9.2 Preparation phase

Implement a preparation screen/timer:

- 30 minutes setup time.
- Optional test fire mode.
- Does not count toward stage scores.
- Allows the user to understand controls.
- Can be skipped in practice mode.

### 9.3 Stage transition rules

Official thresholds:

```text
Stage 1 -> Stage 2 requires at least 30 points.
Stage 2 -> Stage 3 requires at least 20 points.
Stage 3 success/prize criterion requires at least 10 points.
```

Simulator behavior:

- In strict competition mode:
  - block next stage if threshold is not met.
- In practice mode:
  - allow user to continue but show warning:
    “Officially, you would not advance.”

---

## 10. User Controls

### 10.1 Required controls

Implement:

- Start simulation
- Pause/resume
- Reset stage
- Fire button
- Emergency stop
- Maintenance request
- Mode selector:
  - Manual
  - Autonomous
- Skip onboarding
- Restart onboarding
- Toggle overlays:
  - range bands,
  - target paths,
  - classification labels,
  - score debug,
  - rule explanations.

### 10.2 Stage-specific controls

Stage 1:

- manual aim controls required,
- fire button required,
- user must intentionally fire.

Stage 2:

- official mode: autonomous engagement.
- user should switch to autonomous mode and then watch the system engage.
- fire button can be disabled or marked as “not needed in autonomous official mode.”
- if manual-practice mode is enabled, fire button may be used, but scoring should say this is not strict official behavior.

Stage 3:

- official mode: autonomous target selection and engagement.
- user/system must avoid friendly targets.
- because perfect classification is assumed, hostile/friendly labels may be displayed by default.

---

## 11. Contextual Onboarding / Tutorial

The simulator must include a skippable contextual onboarding system.

### 11.1 Requirements

Onboarding must:

- be skippable at any time,
- be restartable,
- pause the simulation completely while showing instruction steps,
- pause:
  - aircraft movement,
  - timers,
  - scoring updates,
  - target spawning,
  - weapon cooldown,
  - route progression,
- highlight the UI element that the user should interact with,
- use a heart-beat / pulse / bump animation around the highlighted button or UI target,
- provide short contextual explanations tied to the current stage,
- explain what the real competition expects at that moment.

### 11.2 Onboarding behavior model

Use a tutorial overlay system:

```ts
type TutorialStep = {
  id: string;
  stage: "global" | 1 | 2 | 3;
  trigger: TutorialTrigger;
  pauseSimulation: boolean;
  message: string;
  highlightElementId?: string;
  highlightMapRegion?: Rect;
  expectedAction?: UserAction;
  canSkip: boolean;
};
```

When a tutorial step is active:

```ts
simulation.pauseAll("tutorial");
showOverlay(step.message);
highlight(step.highlightElementId or map region);
playPulseAnimation();
wait for expectedAction or Next/Skip;
resume simulation when appropriate;
```

### 11.3 Example onboarding steps

Global intro:

```text
This simulator follows the final competition structure: Stage 1 manual, Stage 2 autonomous swarm destruction, Stage 3 autonomous dost/düşman selection.
```

Stage 1 start:

```text
Stage 1 is manual. You must aim and press Fire yourself. If you do not press Fire, no target is destroyed and the timer continues.
```

Stage 1 fire prompt:

```text
The required target is now aligned. Click Fire to destroy it.
```

The Fire button should pulse until clicked.

Stage 2 start:

```text
Stage 2 is autonomous in the real competition. Your job is to switch the system into autonomous mode. The system then detects, tracks, and destroys targets before they exit at B.
```

Highlight the autonomous mode toggle.

Stage 2 route explanation:

```text
Targets start from A on the left and move toward B on the right. One target appears in each of the three lanes. A full A-to-B traversal is one round.
```

Highlight the A side, B side, and the three lanes on the map.

Stage 3 start:

```text
Stage 3 has one hostile target and two friendly targets per round. Red means hostile and blue means friendly in the official diagram. You must destroy only the hostile target.
```

Highlight hostile/friendly legend.

Stage 3 distance prompt:

```text
This hostile target is an F16. It only scores if destroyed between 10 m and 15 m. Wait until it is inside the valid band, then the autonomous system may engage.
```

If using manual-practice mode, highlight Fire. In official autonomous mode, highlight valid engagement zone and show the upcoming auto-fire condition.

### 11.4 Onboarding and scoring

Tutorial pauses must not change official scoring.

Rules:

- while tutorial is paused, target positions freeze,
- timers freeze,
- no misses occur,
- no target exits,
- no weapon cooldown progresses,
- after tutorial resumes, simulation continues from the exact frozen state.

---

## 12. Scoring Engine Summary

### 12.1 Stage 1

```ts
stage1 = {
  timeLimitSeconds: 300,
  targetDistancesM: [5, 10, 15],
  targetTypes: ["ballisticMissile", "helicopter", "f16", "miniMicroUav"],
  pointsByRange: {
    near: 5,
    medium: 10,
    long: 20
  },
  wrongTargetPenalty: -5,
  maxBaseScore: 80,
  bonusFormula: "20 * remainingSeconds / 300",
  advancementThreshold: 30
}
```

### 12.2 Stage 2

```ts
stage2 = {
  rounds: 4,
  targetsPerRound: 3,
  lanes: 3,
  mode: "autonomous",
  targetTypes: ["ballisticMissile", "miniMicroUav"],
  classificationRequired: false,
  pointsByDestroyedCount: {
    0: -5,
    1: 5,
    2: 15,
    3: 30
  },
  maxScore: 120,
  failIfNoHitRoundsAtLeast: 3,
  advancementThreshold: 20
}
```

### 12.3 Stage 3

```ts
stage3 = {
  rounds: 8,
  targetsPerRound: 3,
  hostileTargetsPerRound: 1,
  friendlyTargetsPerRound: 2,
  mode: "autonomous",
  validRangeByTypeM: {
    f16: [10, 15],
    helicopter: [5, 15],
    ballisticMissile: [5, 15],
    miniMicroUav: [0, 15]
  },
  pointsByHostileType: {
    f16: 30,
    helicopter: 20,
    ballisticMissile: 20,
    miniMicroUav: 10
  },
  maxRoundPenalty: -10,
  maxScore: 160,
  failIfConsecutiveHostileMisses: 3,
  successThreshold: 10
}
```

---

## 13. Event Log Requirements

The simulator should record an event log for debugging and learning.

Each event should include:

```ts
{
  timestampSim: number,
  stage: 1 | 2 | 3,
  round?: number,
  eventType: string,
  targetId?: string,
  targetType?: string,
  affiliation?: "hostile" | "friendly",
  rangeM?: number,
  lane?: string,
  scoreDelta?: number,
  reason?: string
}
```

Example events:

```text
STAGE_STARTED
TARGET_SPAWNED
TARGET_ENTERED_VALID_RANGE
FIRE_BUTTON_CLICKED
AUTO_FIRE_TRIGGERED
TARGET_DESTROYED
FRIENDLY_HIT
HOSTILE_EXITED
ROUND_ENDED
PENALTY_APPLIED
THRESHOLD_FAILED
TUTORIAL_PAUSED
TUTORIAL_RESUMED
EMERGENCY_STOP
MAINTENANCE_STARTED
MAINTENANCE_ENDED
```

---

## 14. Strict Mode vs Practice Mode

Implement at least two modes.

### 14.1 Strict competition mode

- Follows official stage advancement thresholds.
- Uses official scoring.
- Does not allow manual override in Stage 2 or Stage 3.
- Stops advancement if threshold fails.
- Onboarding can still pause because it is a training layer, not part of official scoring.

### 14.2 Practice mode

- Allows replaying stages independently.
- Allows manual fire testing in autonomous stages.
- Can show route lines, target labels, and valid range bands.
- Can continue to later stages even if thresholds fail.
- Must visibly mark practice-only behavior.

---

## 15. Safety and Emergency Stop Logic

Implement emergency stop:

```text
Emergency Stop pressed:
- freeze target movement,
- freeze timers,
- disable firing,
- mark system as emergency stopped,
- require explicit reset/resume action.
```

This is a simulation of the required emergency stop behavior from the competition. The official document says continuation after emergency stop requires referee evaluation; in the simulator, represent this as a “Resume after referee approval” button or modal.

---

## 16. Development Checklist for the Coding Agent

The implementation is acceptable when it can do the following:

- [ ] Load official/cropped parkour map for Stage 2.
- [ ] Load official/cropped parkour map for Stage 3.
- [ ] Show range markers or range-band overlay for 15 m, 10 m, 5 m.
- [ ] Spawn Stage 2 targets on 3 lanes, 4 rounds.
- [ ] Move Stage 2 targets from A to B along traced wavy routes.
- [ ] Score Stage 2 per destroyed target count.
- [ ] Fail Stage 2 if no targets are hit for 3 rounds.
- [ ] Spawn Stage 3 targets on 3 lanes, 8 rounds.
- [ ] Use exactly 1 hostile and 2 friendly targets per Stage 3 round.
- [ ] Use red/blue or equivalent hostile/friendly visualization.
- [ ] Apply Stage 3 distance-valid hit rules by target type.
- [ ] Penalize friendly hits and hostile misses with max -10 per round.
- [ ] Fail Stage 3 after 3 consecutive hostile misses.
- [ ] Implement Stage 1 manual fire and target order logic.
- [ ] Implement tutorial/onboarding that pauses the whole simulation.
- [ ] Tutorial highlights buttons/regions with pulse/heartbeat animation.
- [ ] Tutorial is skippable and restartable.
- [ ] Missing official numeric values are stored as config, not hard-coded as facts.
- [ ] Event log explains scoring decisions.
- [ ] Strict and practice modes are separate.

---

## 17. Key Implementation Warning

Do **not** create a scripted story where aircraft simply appear according to a custom scenario. The required simulator is a **competition-mechanics simulator**:

```text
official map image
+ official stage structure
+ route-following targets
+ official scoring
+ correct mode behavior
+ optional tutorial guidance
```

When exact values are missing in the source document, the simulator should make them configurable and visible to the user as simulator assumptions.

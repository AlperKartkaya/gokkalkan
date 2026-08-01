"""Synthetic sensor replay benchmarks for the deterministic course geometry
tracker and curve-aware intercept predictor.

These tests address ``parkur_geometri_referansi.md`` §11 item 6:

* Route selection accuracy across all three poligon routes.
* Speed-estimation convergence and tracking under varying profiles.
* Intercept-point prediction accuracy along the curve.
* Quantitative curved-vs-chord comparison showing why the curved polyline
  approach materially outperforms naïve straight-line extrapolation.
* Noise robustness across increasing sensor error.
* Multi-pass poligon re-entry and boundary behaviour.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence

import pytest

from gokkalkan_backend.course_geometry import (
    CourseGeometry,
    CoursePoint,
    CourseTrackEstimator,
    load_course_geometry,
)


# ---------------------------------------------------------------------------
# Synthetic replay helpers
# ---------------------------------------------------------------------------

ROUTE_IDS = ("POLIGON_ROUTE_1", "POLIGON_ROUTE_2", "POLIGON_ROUTE_3")


@dataclass
class SensorSample:
    """A single synthetic sensor measurement with known ground truth."""

    time_s: float
    range_m: float
    bearing_base_deg: float
    # ground truth
    gt_route_id: str
    gt_s_m: float
    gt_x_m: float
    gt_y_m: float
    gt_speed_mps: float


def _generate_traversal(
    geometry: CourseGeometry,
    route_id: str,
    *,
    speed_mps: float = 1.0,
    accel_mps2: float = 0.0,
    dt: float = 0.1,
    start_s: float = 0.5,
    noise_range_m: float = 0.0,
    noise_bearing_deg: float = 0.0,
    rng: random.Random | None = None,
) -> list[SensorSample]:
    """Walk along *route_id* at constant or uniformly-accelerating speed.

    Returns synthetic sensor measurements (range + bearing) from the system
    reference together with ground-truth state for each sample.
    """
    rng = rng or random.Random(42)
    route = geometry.route(route_id)
    max_s = route.length_m
    s = start_s
    v = speed_mps
    t = 0.0
    samples: list[SensorSample] = []

    while s < max_s and v >= 0:
        point = geometry.point_at_s(route_id, s)
        if point is None:
            break
        clean_range, clean_bearing = geometry.measurement_for_point(point)
        noisy_range = clean_range + rng.gauss(0, noise_range_m) if noise_range_m > 0 else clean_range
        noisy_bearing = clean_bearing + rng.gauss(0, noise_bearing_deg) if noise_bearing_deg > 0 else clean_bearing
        noisy_range = max(0.01, noisy_range)  # range cannot go negative

        samples.append(SensorSample(
            time_s=t,
            range_m=noisy_range,
            bearing_base_deg=noisy_bearing,
            gt_route_id=route_id,
            gt_s_m=s,
            gt_x_m=point.x_m,
            gt_y_m=point.y_m,
            gt_speed_mps=v,
        ))
        s += v * dt
        v += accel_mps2 * dt
        t += dt

    return samples


def _run_estimator(
    geometry: CourseGeometry,
    samples: Sequence[SensorSample],
    *,
    speed_alpha: float = 0.35,
) -> list[tuple[SensorSample, object]]:
    """Feed samples into a fresh estimator and return (sample, state) pairs."""
    estimator = CourseTrackEstimator(geometry, speed_alpha=speed_alpha)
    results = []
    for sample in samples:
        state = estimator.update(
            "SYNTH",
            sample.range_m,
            sample.bearing_base_deg,
            observed_at_s=sample.time_s,
        )
        results.append((sample, state))
    return results


def _chord_predict(
    geometry: CourseGeometry,
    current_point: CoursePoint,
    current_speed_mps: float,
    tangent_deg: float,
    lead_time_s: float,
) -> CoursePoint:
    """Naïve straight-line (chord) prediction in the course frame."""
    dx = current_speed_mps * lead_time_s * math.cos(math.radians(tangent_deg))
    dy = current_speed_mps * lead_time_s * math.sin(math.radians(tangent_deg))
    return CoursePoint(current_point.x_m + dx, current_point.y_m + dy)


def _point_distance(a: CoursePoint, b: CoursePoint) -> float:
    return math.hypot(a.x_m - b.x_m, a.y_m - b.y_m)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def geometry() -> CourseGeometry:
    return load_course_geometry()


# ---------------------------------------------------------------------------
# 1. Route selection accuracy
# ---------------------------------------------------------------------------

class TestRouteSelection:
    """Verify the estimator selects the correct route_id for all three routes."""

    @pytest.mark.parametrize("route_id", ROUTE_IDS)
    def test_route_selection_accuracy(self, geometry: CourseGeometry, route_id: str) -> None:
        """Generate a noiseless traversal on each route and confirm the estimator
        identifies the correct route in ≥95 % of samples after the first two
        (needed for speed initialisation)."""
        samples = _generate_traversal(geometry, route_id, speed_mps=1.0, dt=0.1)
        results = _run_estimator(geometry, samples)

        # Skip the first 2 samples (transient phase for speed init)
        evaluated = results[2:]
        correct = sum(1 for _, state in evaluated if state.route_id == route_id)
        accuracy = correct / len(evaluated) if evaluated else 0

        assert accuracy >= 0.95, (
            f"Route {route_id}: selection accuracy {accuracy:.2%} < 95 %"
        )

    @pytest.mark.parametrize("route_id", ROUTE_IDS)
    def test_route_selection_with_noise(self, geometry: CourseGeometry, route_id: str) -> None:
        """Even with moderate noise (0.1 m range, 0.5° bearing), route
        selection should stay ≥90 %."""
        samples = _generate_traversal(
            geometry, route_id,
            speed_mps=1.0, dt=0.1,
            noise_range_m=0.1, noise_bearing_deg=0.5,
        )
        results = _run_estimator(geometry, samples)
        evaluated = results[3:]
        correct = sum(1 for _, state in evaluated if state.route_id == route_id)
        accuracy = correct / len(evaluated) if evaluated else 0
        assert accuracy >= 0.90, (
            f"Route {route_id}: noisy selection accuracy {accuracy:.2%} < 90 %"
        )


# ---------------------------------------------------------------------------
# 2. Speed estimation convergence
# ---------------------------------------------------------------------------

class TestSpeedEstimation:
    """Verify ds/dt estimation converges to ground-truth speed."""

    @pytest.mark.parametrize("target_speed", [0.3, 0.5, 1.0, 2.0])
    def test_speed_convergence_constant(
        self, geometry: CourseGeometry, target_speed: float,
    ) -> None:
        """At constant speed, the estimator should converge within 10 %
        relative error after a short transient."""
        samples = _generate_traversal(
            geometry, "POLIGON_ROUTE_2",
            speed_mps=target_speed, dt=0.1,
        )
        results = _run_estimator(geometry, samples)

        # Allow 8 samples of transient (~0.8 s) for the EMA to settle
        settled = results[8:]
        if not settled:
            pytest.skip("Traversal too short for convergence check")

        speed_errors = [
            abs(state.speed_mps - target_speed) / target_speed
            for _, state in settled
            if state.lifecycle == "ACTIVE_IN_POLIGON"
        ]
        mean_relative_error = sum(speed_errors) / len(speed_errors) if speed_errors else 1.0
        assert mean_relative_error < 0.10, (
            f"Speed {target_speed} m/s: mean relative error "
            f"{mean_relative_error:.2%} ≥ 10 %"
        )

    def test_speed_estimation_with_acceleration(
        self, geometry: CourseGeometry,
    ) -> None:
        """An accelerating target (0.5 → ~1.5 m/s over 10 s) should be
        tracked with bounded lag.  The speed error at the end of the transient
        should be < 0.3 m/s (acceptable EMA lag)."""
        samples = _generate_traversal(
            geometry, "POLIGON_ROUTE_2",
            speed_mps=0.5, accel_mps2=0.1, dt=0.1,
        )
        results = _run_estimator(geometry, samples)
        settled = results[10:]
        if not settled:
            pytest.skip("Traversal too short")

        last_errors = [
            abs(state.speed_mps - sample.gt_speed_mps)
            for sample, state in settled[-20:]
            if state.lifecycle == "ACTIVE_IN_POLIGON"
        ]
        if last_errors:
            max_lag = max(last_errors)
            assert max_lag < 0.3, f"Acceleration lag {max_lag:.3f} m/s ≥ 0.3"


# ---------------------------------------------------------------------------
# 3. Intercept prediction accuracy
# ---------------------------------------------------------------------------

class TestInterceptPrediction:

    def test_intercept_prediction_on_curve(self, geometry: CourseGeometry) -> None:
        """Walk along Route 2 and predict where the target will be after a
        known lead time.  Compare against actual ground-truth position."""
        route_id = "POLIGON_ROUTE_2"
        speed = 1.0
        projectile_speed = 100.0
        latency = 0.3  # 300 ms total system latency
        dt = 0.1

        samples = _generate_traversal(
            geometry, route_id, speed_mps=speed, dt=dt,
        )
        estimator = CourseTrackEstimator(geometry, speed_alpha=0.5)

        # Feed enough samples for speed to settle, then predict
        for sample in samples[:15]:
            estimator.update(
                "PREDICT", sample.range_m, sample.bearing_base_deg,
                observed_at_s=sample.time_s,
            )

        state = estimator.state("PREDICT")
        assert state is not None and state.prediction_valid

        prediction = estimator.predict_intercept(
            "PREDICT",
            projectile_speed_mps=projectile_speed,
            fixed_latency_s=latency,
        )
        assert prediction is not None

        # Ground truth: target should be at s_now + speed * flight_time
        gt_s_hit = state.s_m + speed * prediction.flight_time_s
        gt_point = geometry.point_at_s(route_id, gt_s_hit)
        if gt_point is None:
            pytest.skip("Ground truth position outside route")

        error = _point_distance(prediction.point, gt_point)
        assert error < 0.5, (
            f"Intercept prediction error {error:.3f} m ≥ 0.5 m"
        )


# ---------------------------------------------------------------------------
# 4. Curved vs chord comparison — KEY BENCHMARK
# ---------------------------------------------------------------------------

class TestCurvedVsChord:
    """Quantitatively demonstrate the advantage of curve-aware prediction
    over naïve straight-line (chord) extrapolation."""

    @pytest.mark.parametrize("route_id", ROUTE_IDS)
    def test_curved_beats_chord(
        self, geometry: CourseGeometry, route_id: str,
    ) -> None:
        """For each route, compare curved and chord predictions at multiple
        points and assert the curved approach has lower mean error."""
        speed = 1.0
        projectile_speed = 100.0
        latency = 0.3
        dt = 0.1

        samples = _generate_traversal(
            geometry, route_id, speed_mps=speed, dt=dt,
        )

        curved_errors: list[float] = []
        chord_errors: list[float] = []

        # Test predictions at several points along the route
        for eval_idx in range(15, len(samples) - 20, 5):
            estimator = CourseTrackEstimator(geometry, speed_alpha=0.5)

            # Prime estimator with preceding samples
            for sample in samples[max(0, eval_idx - 12) : eval_idx + 1]:
                estimator.update(
                    "CMP", sample.range_m, sample.bearing_base_deg,
                    observed_at_s=sample.time_s,
                )

            state = estimator.state("CMP")
            if state is None or not state.prediction_valid or state.speed_mps <= 0:
                continue

            # Curved prediction
            prediction = estimator.predict_intercept(
                "CMP",
                projectile_speed_mps=projectile_speed,
                fixed_latency_s=latency,
            )
            if prediction is None:
                continue

            # Ground truth
            gt_s = state.s_m + speed * prediction.flight_time_s
            gt_point = geometry.point_at_s(route_id, gt_s)
            if gt_point is None:
                continue

            curved_error = _point_distance(prediction.point, gt_point)
            curved_errors.append(curved_error)

            # Chord (straight-line) prediction
            if state.projected_point is not None and state.tangent_course_deg is not None:
                chord_point = _chord_predict(
                    geometry,
                    state.projected_point,
                    state.speed_mps,
                    state.tangent_course_deg,
                    prediction.flight_time_s,
                )
                chord_error = _point_distance(chord_point, gt_point)
                chord_errors.append(chord_error)

        assert len(curved_errors) >= 5, "Not enough evaluation points"

        mean_curved = sum(curved_errors) / len(curved_errors)
        mean_chord = sum(chord_errors) / len(chord_errors)
        max_curved = max(curved_errors)
        max_chord = max(chord_errors)

        # Print quantitative comparison for report / KTR evidence
        print(f"\n{'='*60}")
        print(f"  CURVED vs CHORD — {route_id}")
        print(f"  Mean error  : curved={mean_curved:.4f} m  chord={mean_chord:.4f} m")
        print(f"  Max error   : curved={max_curved:.4f} m  chord={max_chord:.4f} m")
        print(f"  Improvement : {(1 - mean_curved / mean_chord) * 100:.1f} % mean reduction")
        print(f"  Eval points : {len(curved_errors)}")
        print(f"{'='*60}")

        assert mean_curved <= mean_chord, (
            f"{route_id}: curved ({mean_curved:.4f}) should not be worse "
            f"than chord ({mean_chord:.4f})"
        )


# ---------------------------------------------------------------------------
# 5. Noise robustness
# ---------------------------------------------------------------------------

class TestNoiseRobustness:

    @pytest.mark.parametrize("noise_m", [0.0, 0.05, 0.1, 0.2])
    def test_graceful_degradation(
        self, geometry: CourseGeometry, noise_m: float,
    ) -> None:
        """Increasing range noise should degrade speed accuracy gracefully
        and never cause crashes."""
        route_id = "POLIGON_ROUTE_2"
        speed = 1.0
        samples = _generate_traversal(
            geometry, route_id,
            speed_mps=speed, dt=0.1,
            noise_range_m=noise_m,
            noise_bearing_deg=noise_m * 5,  # proportional bearing noise
        )

        results = _run_estimator(geometry, samples)
        settled = results[10:]
        if not settled:
            pytest.skip("Too short")

        active_results = [
            (sample, state) for sample, state in settled
            if state.lifecycle == "ACTIVE_IN_POLIGON"
        ]
        if not active_results:
            pytest.skip("No active-in-poligon states")

        speed_errors = [
            abs(state.speed_mps - speed) for _, state in active_results
        ]
        mean_speed_error = sum(speed_errors) / len(speed_errors)

        route_correct = sum(
            1 for _, state in active_results
            if state.route_id == route_id
        )
        route_accuracy = route_correct / len(active_results)

        # With 0.2 m noise, route selection should still work
        assert route_accuracy >= 0.85, (
            f"Noise {noise_m}: route accuracy {route_accuracy:.2%} < 85 %"
        )
        # Speed error should scale roughly with noise, not explode
        if noise_m <= 0.1:
            assert mean_speed_error < 0.8, (
                f"Noise {noise_m}: speed error {mean_speed_error:.3f} ≥ 0.8"
            )


# ---------------------------------------------------------------------------
# 6. Multi-pass re-entry
# ---------------------------------------------------------------------------

class TestMultiPassReentry:

    def test_reentry_increments_pass_index(self, geometry: CourseGeometry) -> None:
        """Simulate target exiting poligon, going off-screen, then
        re-entering.  Pass index should increment and s should reset."""
        route_id = "POLIGON_ROUTE_1"
        route = geometry.route(route_id)
        estimator = CourseTrackEstimator(geometry)

        # Pass 1: traverse from entry to near exit
        entry_point = geometry.point_at_s(route_id, 0.5)
        mid_point = geometry.point_at_s(route_id, 5.0)
        near_exit = geometry.point_at_s(route_id, route.length_m - 0.2)

        for idx, pt in enumerate([entry_point, mid_point, near_exit]):
            assert pt is not None
            r, b = geometry.measurement_for_point(pt)
            estimator.update("REENTRY", r, b, observed_at_s=float(idx))

        state = estimator.state("REENTRY")
        assert state is not None
        assert state.pass_index == 1

        # Exit: far outside poligon
        outside_state = estimator.update(
            "REENTRY", range_m=30.0, bearing_base_deg=0.0,
            observed_at_s=10.0,
        )
        assert outside_state.lifecycle == "OUTSIDE_POLIGON"
        assert outside_state.prediction_valid is False

        # Re-enter: near poligon entry
        reentry_pt = geometry.point_at_s(route_id, 0.1)
        assert reentry_pt is not None
        r, b = geometry.measurement_for_point(reentry_pt)
        reentry_state = estimator.update("REENTRY", r, b, observed_at_s=11.0)

        assert reentry_state.lifecycle == "ACTIVE_IN_POLIGON"
        assert reentry_state.pass_index == 2
        assert reentry_state.s_m < 1.0  # near entry


# ---------------------------------------------------------------------------
# 7. Boundary behaviour
# ---------------------------------------------------------------------------

class TestBoundaryBehaviour:

    def test_entry_boundary_transition(self, geometry: CourseGeometry) -> None:
        """First measurement at the poligon entry should produce
        ACTIVE_IN_POLIGON."""
        route_id = "POLIGON_ROUTE_3"
        entry_pt = geometry.point_at_s(route_id, 0.0)
        assert entry_pt is not None
        r, b = geometry.measurement_for_point(entry_pt)

        estimator = CourseTrackEstimator(geometry)
        state = estimator.update("BOUNDARY", r, b, observed_at_s=0.0)
        assert state.lifecycle == "ACTIVE_IN_POLIGON"
        assert state.inside_poligon is True

    def test_exit_boundary_still_valid(self, geometry: CourseGeometry) -> None:
        """The very last waypoint should still be ACTIVE_IN_POLIGON."""
        route_id = "POLIGON_ROUTE_2"
        route = geometry.route(route_id)
        exit_pt = geometry.point_at_s(route_id, route.length_m)
        assert exit_pt is not None
        r, b = geometry.measurement_for_point(exit_pt)

        estimator = CourseTrackEstimator(geometry)
        state = estimator.update("EXIT", r, b, observed_at_s=0.0)
        assert state.lifecycle == "ACTIVE_IN_POLIGON"

    def test_outside_measurement_rejected(self, geometry: CourseGeometry) -> None:
        """A measurement clearly outside the poligon should be OUTSIDE."""
        estimator = CourseTrackEstimator(geometry)
        state = estimator.update(
            "FAR", range_m=50.0, bearing_base_deg=45.0, observed_at_s=0.0,
        )
        assert state.inside_poligon is False
        assert state.prediction_valid is False


# ---------------------------------------------------------------------------
# 8. Comprehensive summary statistics
# ---------------------------------------------------------------------------

class TestTraversalStatistics:

    def test_all_routes_statistics_summary(self, geometry: CourseGeometry) -> None:
        """Run all routes at 1.0 m/s and collect route-selection, speed and
        intercept error statistics.  Prints a summary table for KTR/video
        evidence and asserts reasonable bounds on all metrics."""
        speed = 1.0
        projectile_speed = 100.0
        latency = 0.3

        stats: dict[str, dict] = {}

        for route_id in ROUTE_IDS:
            samples = _generate_traversal(
                geometry, route_id, speed_mps=speed, dt=0.1,
            )
            estimator = CourseTrackEstimator(geometry, speed_alpha=0.5)

            route_correct = 0
            total_active = 0
            speed_errors: list[float] = []
            intercept_errors: list[float] = []

            for i, sample in enumerate(samples):
                state = estimator.update(
                    "STATS", sample.range_m, sample.bearing_base_deg,
                    observed_at_s=sample.time_s,
                )

                if i < 3:  # skip transient
                    continue
                if state.lifecycle != "ACTIVE_IN_POLIGON":
                    continue

                total_active += 1
                if state.route_id == route_id:
                    route_correct += 1
                speed_errors.append(abs(state.speed_mps - speed))

                # Try intercept prediction at every 10th sample
                if i % 10 == 0 and state.speed_mps > 0:
                    prediction = estimator.predict_intercept(
                        "STATS",
                        projectile_speed_mps=projectile_speed,
                        fixed_latency_s=latency,
                    )
                    if prediction is not None:
                        gt_s = state.s_m + speed * prediction.flight_time_s
                        gt_pt = geometry.point_at_s(route_id, gt_s)
                        if gt_pt is not None:
                            intercept_errors.append(
                                _point_distance(prediction.point, gt_pt)
                            )

            route_accuracy = route_correct / total_active if total_active else 0
            mean_speed_err = (
                sum(speed_errors) / len(speed_errors) if speed_errors else float("nan")
            )
            max_speed_err = max(speed_errors) if speed_errors else float("nan")
            mean_intercept_err = (
                sum(intercept_errors) / len(intercept_errors)
                if intercept_errors else float("nan")
            )
            max_intercept_err = (
                max(intercept_errors) if intercept_errors else float("nan")
            )

            stats[route_id] = {
                "route_accuracy": route_accuracy,
                "mean_speed_err": mean_speed_err,
                "max_speed_err": max_speed_err,
                "mean_intercept_err": mean_intercept_err,
                "max_intercept_err": max_intercept_err,
                "samples": total_active,
            }

        # Print summary table
        print("\n" + "=" * 80)
        print("  SYNTHETIC REPLAY BENCHMARK SUMMARY")
        print("=" * 80)
        print(f"  {'Route':<22} {'RouteAcc':>9} {'MeanSpd':>9} {'MaxSpd':>9} "
              f"{'MeanInt':>9} {'MaxInt':>9} {'N':>5}")
        print("-" * 80)
        for route_id, s in stats.items():
            short_id = route_id.replace("POLIGON_ROUTE_", "R")
            print(f"  {short_id:<22} {s['route_accuracy']:>8.1%} "
                  f"{s['mean_speed_err']:>8.4f} {s['max_speed_err']:>8.4f} "
                  f"{s['mean_intercept_err']:>8.4f} {s['max_intercept_err']:>8.4f} "
                  f"{s['samples']:>5}")
        print("=" * 80)

        # Assert overall quality
        for route_id, s in stats.items():
            assert s["route_accuracy"] >= 0.95, f"{route_id}: low route accuracy"
            assert s["mean_speed_err"] < 0.15, f"{route_id}: high mean speed error"
            assert s["mean_intercept_err"] < 0.5, f"{route_id}: high intercept error"

#!/usr/bin/env python
"""
Consolidated Demo Script for Judges Presentation
=================================================

Usage:
    python scripts/demo.py              # Full demo: reset → inject → optimize → verify
    python scripts/demo.py --reset      # Reset only (clear delays + optimization logs)
    python scripts/demo.py --inject     # Inject conflicts only
    python scripts/demo.py --optimize   # Run optimization only
    python scripts/demo.py --verify     # Verify explanation only

Requires the backend server to be running on localhost:8010.
"""

import argparse
import json
import sys
import time

import requests

API_BASE = "http://localhost:8010/api/v1"


def print_header(text: str) -> None:
    print("\n" + "=" * 80)
    print(text.center(80))
    print("=" * 80)


def print_step(step: str, text: str) -> None:
    print(f"\n[{step}] {text}")


def check_server() -> bool:
    """Verify the backend is reachable."""
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def reset_system() -> bool:
    """Reset all train delays and optimization history."""
    print_step("RESET", "Resetting system to clean state...")
    try:
        r = requests.post(f"{API_BASE}/conflicts/reset", timeout=10)
        if r.status_code == 200:
            result = r.json()
            print(f"    OK  Reset {result.get('trains_reset', 0)} trains")
            return True
        else:
            print(f"    WARN  Reset endpoint returned {r.status_code}")
            return True  # Non-fatal
    except Exception as e:
        print(f"    WARN  Could not reset (may not be needed): {e}")
        return True


def inject_conflicts() -> bool:
    """Inject sample conflicts via API."""
    print_step("INJECT", "Injecting realistic conflicts...")
    try:
        r = requests.post(f"{API_BASE}/conflicts/inject", timeout=10)
        result = r.json()
        print(f"    OK  {result.get('message', 'Conflicts injected')}")
        print(f"    OK  Trains affected: {result.get('trains_affected', 0)}")

        if result.get("injected_conflicts"):
            print(f"\n    Injected conflicts:")
            for conflict in result["injected_conflicts"][:4]:
                print(
                    f"      - {conflict.get('train_number', 'N/A')}: "
                    f"+{conflict.get('delay_added_minutes', 0)} min delay"
                )
        return True
    except Exception as e:
        print(f"    FAIL  Failed to inject conflicts: {e}")
        return False


def run_optimization() -> bool:
    """Trigger an optimization cycle."""
    print_step("OPTIMIZE", "Running optimization with explanation generation...")
    try:
        r = requests.post(
            f"{API_BASE}/optimization/run",
            json={"include_predictions": True},
            timeout=60,
        )
        result = r.json()

        if result.get("status") == "success" or result.get("optimization_success"):
            print(f"    OK  Optimization complete")
            print(f"      - Conflicts resolved: {result.get('conflicts_resolved', 0)}")
            print(f"      - Total weighted delay: {result.get('total_weighted_delay', 0):.1f} min")
            print(f"      - Solver runtime: {result.get('solver_runtime_seconds', 0):.2f}s")
            return True
        else:
            print(f"    WARN  Optimization status: {result.get('message', 'Unknown')}")
            return True  # Non-fatal — may still have explanation
    except Exception as e:
        print(f"    FAIL  Failed to run optimization: {e}")
        return False


def verify_explanation() -> dict:
    """Fetch and verify the explanation from the latest plan."""
    print_step("VERIFY", "Verifying explanation for dashboard...")
    try:
        r = requests.get(f"{API_BASE}/optimization/latest-plan", timeout=10)
        data = r.json()

        if not data.get("explanation"):
            print("    WARN  No explanation in response (run optimization first)")
            return {}

        exp = data["explanation"]

        conflicts = exp.get("conflicts_detected", [])
        decisions = exp.get("decisions_made", [])
        improvement = exp.get("objective_improvement", {})
        actions = exp.get("train_actions", [])

        print(f"\n    OK  Explanation generated:")
        print(f"      - Conflicts detected: {len(conflicts)}")
        print(f"      - Decisions made: {len(decisions)}")
        print(f"      - Train actions: {len(actions)}")

        if improvement:
            print(f"\n    Delay Reduction Metrics:")
            print(f"      - Improvement: {improvement.get('improvement_percent', 0):.1f}%")
            print(f"      - Minutes saved: {improvement.get('delay_reduction', 0):.1f} min")
            print(f"      - Before: {improvement.get('previous_weighted_delay', 0):.1f} min")
            print(f"      - After: {improvement.get('optimized_weighted_delay', 0):.1f} min")

        if decisions:
            print(f"\n    Sample Decision:")
            d = decisions[0]
            print(f"      Priority: {d.get('priority_train', 'N/A')}")
            print(f"      Yielded: {d.get('yielded_train', 'N/A')}")
            print(f"      Section: {d.get('section_name', 'N/A')}")
            print(f"      -> {d.get('explanation', 'N/A')}")

        return exp

    except Exception as e:
        print(f"    FAIL  Failed to verify explanation: {e}")
        return {}


def full_demo() -> None:
    """Run the complete demo flow."""
    print_header("OPTIMIZATION DEMO FOR JUDGES")

    if not check_server():
        print("\n    FAIL  Backend not reachable at http://localhost:8010")
        print("    Start the backend first:  uvicorn app.main:app --port 8010")
        sys.exit(1)

    reset_system()
    time.sleep(1)

    if not inject_conflicts():
        sys.exit(1)
    time.sleep(2)

    if not run_optimization():
        sys.exit(1)
    time.sleep(1)

    exp = verify_explanation()

    # Summary
    print_header("DEMO READY FOR JUDGES")
    print("\nDashboard: http://localhost:3001")
    print("  1. Open dashboard")
    print("  2. Navigate to 'Optimization Plan' panel")
    print("  3. Show judges the explanation sections")
    print("  4. (Optional) Click 'Force Optimization' to run again")

    if exp:
        print(f"\n--- Full explanation JSON ---")
        print(json.dumps(exp, indent=2, default=str))

    print("\nDemo preparation complete!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Railway optimization demo tool")
    parser.add_argument("--reset", action="store_true", help="Reset system only")
    parser.add_argument("--inject", action="store_true", help="Inject conflicts only")
    parser.add_argument("--optimize", action="store_true", help="Run optimization only")
    parser.add_argument("--verify", action="store_true", help="Verify explanation only")
    args = parser.parse_args()

    # If no specific flag, run full demo
    if not any([args.reset, args.inject, args.optimize, args.verify]):
        full_demo()
        return

    if not check_server():
        print("FAIL  Backend not reachable at http://localhost:8010")
        sys.exit(1)

    if args.reset:
        reset_system()
    if args.inject:
        inject_conflicts()
    if args.optimize:
        run_optimization()
    if args.verify:
        verify_explanation()


if __name__ == "__main__":
    main()

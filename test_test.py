#!/usr/bin/env python3
# ---------------------------------------------------------------------------
#   CS 111 – Lab 3  •  Detailed per‑case test‑suite for Round‑Robin scheduler
#   Generates a *separate* unittest method for every (workload, quantum) pair
# ---------------------------------------------------------------------------

import subprocess, tempfile, unittest, math, itertools, os, random

# ---------------------------------------------------------------------------
# Build `rr` once for the entire module
# ---------------------------------------------------------------------------
MAKE_OK, MAKE_LOG = False, ""
try:
    res = subprocess.run(["make"], capture_output=True, text=True, check=True)
    MAKE_OK, MAKE_LOG = True, res.stdout + res.stderr
except subprocess.CalledProcessError as e:
    MAKE_OK, MAKE_LOG = False, e.stdout + e.stderr
RR_EXE = "./rr"

# ---------------------------------------------------------------------------
# Reference Round‑Robin in pure Python
# ---------------------------------------------------------------------------
def rr_reference(workload, quantum):
    n = len(workload)
    remaining = {p: b for p, a, b in workload}
    first_cpu = {}
    responded = set()
    finished  = {}
    ready, arrived, t = [], set(), 0

    while len(finished) < n:
        for p, a, _ in workload:
            if p not in arrived and a <= t:
                ready.append(p)
                arrived.add(p)

        if not ready:
            t = min(a for p, a, _ in workload if p not in arrived)
            continue

        p = ready.pop(0)
        if p not in responded:
            first_cpu[p] = t
            responded.add(p)

        slice_len = min(quantum, remaining[p])
        start = t
        t += slice_len
        remaining[p] -= slice_len

        for q, a, _ in workload:
            if q not in arrived and start < a <= t:
                ready.append(q)
                arrived.add(q)

        if remaining[p]:
            ready.append(p)
        else:
            finished[p] = t

    total_wait = sum(finished[p] - a - b for p, a, b in workload)
    total_resp = sum(first_cpu[p] - a       for p, a, b in workload)
    return round(total_wait / n, 2), round(total_resp / n, 2)

# ---------------------------------------------------------------------------
# Helper to write skeleton input files
# ---------------------------------------------------------------------------
def write_workload(tmp, tuples):
    tmp.write(f"{len(tuples)}\n".encode())
    for pid, arr, bur in tuples:
        tmp.write(f"{pid}, {arr}, {bur}\n".encode())
    tmp.flush()

# ---------------------------------------------------------------------------
# 10 deliberately varied workloads
# ---------------------------------------------------------------------------
WORKLOADS = {
    # 1. Single job, no context switches
    "SINGLE":      [(1, 0, 9)],
    # 2. All arrive at time‑0 with mixed bursts
    "ALL_AT_0":    [(1, 0, 4), (2, 0, 7), (3, 0, 3), (4, 0, 8)],
    # 3. Huge idle gap before first arrival
    "LATE_START":  [(1, 20, 5), (2, 22, 4), (3, 25, 1)],
    # 4. Bursts exactly multiples of quantum=4
    "MULT_OF_4":   [(1, 0, 8), (2, 1, 4), (3, 2, 12)],
    # 5. Every burst < quantum (should mimic FCFS)
    "SMALL_BURSTS":[(1, 0, 1), (2, 2, 2), (3, 4, 3), (4, 6, 1)],
    # 6. Quantum larger than sum(bursts)
    "HUGE_Q":      [(1, 0, 5), (2, 1, 4), (3, 2, 3)],
    # 7. Long CPU‑hog overlapped by many shorts
    "RATTLER":     [(1, 0, 30)] + [(p, p, 1) for p in range(2, 12)],
    # 8. Ten identical arrivals late in the schedule
    "FLOOD_LATE":  [(p, 40, 2) for p in range(1, 11)],
    # 9. Zig‑zag bursts arriving one per tick
    "ZIGZAG":      [(1, 0, 15), (2, 1, 1), (3, 2, 14), (4, 3, 1),
                    (5, 4, 13), (6, 5, 1)],
    # 10. Zero‑burst edge case (should be finished immediately)
    "ZERO_BURST":  [(1, 0, 0), (2, 0, 5), (3, 3, 2)],
}

QUANTA = [1, 2, 3, 4, 5, 6, 8, 16]

# ---------------------------------------------------------------------------
# Dynamic generation of one test method per (workload, quantum)
# ---------------------------------------------------------------------------
class TestRRDetailed(unittest.TestCase):
    """Auto‑generated per‑case tests."""

# Abort all tests if the build failed
if not MAKE_OK:
    def _build_failure(self):
        self.fail(f"`make` failed, cannot run tests:\n{MAKE_LOG}")
    setattr(TestRRDetailed, "test_build_failed", _build_failure)
else:
    for w_name, tuples in WORKLOADS.items():
        for q in QUANTA:
            def _template(self, t=tuples, qlen=q, name=w_name):
                with tempfile.NamedTemporaryFile() as f:
                    write_workload(f, t)
                    out = subprocess.check_output(
                        (RR_EXE, f.name, str(qlen)), text=True
                    ).splitlines()
                    got_wait = float(out[0].split(":")[1])
                    got_resp = float(out[1].split(":")[1])
                    exp_wait, exp_resp = rr_reference(t, qlen)
                    self.assertTrue(
                        math.isclose(got_wait, exp_wait, abs_tol=0.01) and
                        math.isclose(got_resp, exp_resp, abs_tol=0.01),
                        msg=(
                            f"\nWork‑load: {name}  quantum={qlen}"
                            f"\nExpected wait={exp_wait:.2f} resp={exp_resp:.2f}"
                            f"\nGot      wait={got_wait:.2f} resp={got_resp:.2f}\n"
                        )
                    )
            test_name = f"test_{w_name}_q{q}"
            setattr(TestRRDetailed, test_name, _template)

# ---------------------------------------------------------------------------
# Run via   python3 -m unittest -v
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)


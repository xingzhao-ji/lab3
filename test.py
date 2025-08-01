#!/usr/bin/env python3
# ---------------------------------------------------------------------------
#   CS 111 – Lab 3  •  Combined test‑suite for the round‑robin scheduler
# ---------------------------------------------------------------------------

import subprocess
import tempfile
import unittest
import os
import math
import itertools
import textwrap
# pathlib / re are not strictly needed any more, but keep them for parity
import pathlib
import re


# ---------------------------------------------------------------------------
#  Helper: build / clean via `make`
# ---------------------------------------------------------------------------
def _make():
    """Invoke `make`; return (ok: bool, stdout+stderr str)."""
    result = subprocess.run(["make"], capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr


def _make_clean():
    subprocess.run(["make", "clean"], capture_output=True)


# ---------------------------------------------------------------------------
#  ORIGINAL BASIC TESTS  (exactly the logic you provided, just wrapped
#  in a proper import block so `unittest` is defined when the class is read)
# ---------------------------------------------------------------------------
class TestLab2(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.make_ok, cls.make_out = _make()

    def test_averages(self):
        fileName = "processes.txt"
        correctAvgWaitTime = (0, 5.5, 5.0, 7, 4.5, 5.5, 6.25, 4.75)
        correctAvgRespTime = (0, 0.75, 1.5, 2.75, 3.25, 3.25, 4, 4.75)

        self.assertTrue(self.make_ok, msg=f"`make` failed\n{self.make_out}")
        for x in range(1, 7):
            cl_result = subprocess.check_output(("./rr", fileName, str(x))).decode()
            lines = cl_result.split("\n")
            testAvgWaitTime = float(lines[0].split(":")[1])
            testAvgRespTime = float(lines[1].split(":")[1])

            self.assertEqual(
                (testAvgWaitTime, testAvgRespTime),
                (correctAvgWaitTime[x], correctAvgRespTime[x]),
                msg=(
                    f"\nQuantum = {x}\n"
                    f"Expected: wait={correctAvgWaitTime[x]}, resp={correctAvgRespTime[x]}\n"
                    f"Got:      wait={testAvgWaitTime}, resp={testAvgRespTime}\n"
                )
            )

    def test_arrival_and_requeue(self):
        self.assertTrue(self.make_ok, msg=f"`make` failed\n{self.make_out}")

        correctAvgWaitTime = (0, 5, 5.25, 6.5, 4.0, 4.5, 5.75, 4.75)
        correctAvgRespTime = (0, 0.75, 1.5, 2.25, 2.75, 3.25, 3.5, 4.75)

        with tempfile.NamedTemporaryFile() as f:
            f.write(b"4\n")
            f.write(b"1, 0, 7\n")
            f.write(b"2, 3, 4\n")
            f.write(b"3, 4, 1\n")
            f.write(b"4, 6, 4\n")
            f.flush()

            for x in range(1, 7):
                cl_result = subprocess.check_output(("./rr", f.name, str(x))).decode()
                lines = cl_result.split("\n")
                testAvgWaitTime = float(lines[0].split(":")[1])
                testAvgRespTime = float(lines[1].split(":")[1])

                self.assertEqual(
                    (testAvgWaitTime, testAvgRespTime),
                    (correctAvgWaitTime[x], correctAvgRespTime[x]),
                    msg=(
                        f"\nRe‑queue arrival case  •  Quantum = {x}\n"
                        f"Expected: wait={correctAvgWaitTime[x]}, resp={correctAvgRespTime[x]}\n"
                        f"Got:      wait={testAvgWaitTime}, resp={testAvgRespTime}\n"
                    )
                )


# ---------------------------------------------------------------------------
#  EXTENDED EDGE‑CASE SUITE
# ---------------------------------------------------------------------------
def rr_reference(workload, quantum):
    """
    Tiny, deterministic round‑robin scheduler used to compute ground‑truth
    averages.  Workload = [(pid, arrival, burst), …].
    Returns (avg_wait, avg_resp) rounded to 2 decimals.
    """
    n = len(workload)
    remaining = {p: b for p, a, b in workload}
    first_cpu = {}
    responded = set()
    finished  = {}
    ready, arrived, t = [], set(), 0

    while len(finished) < n:
        # Admit arrivals up to and including time t
        for p, a, _ in workload:
            if p not in arrived and a <= t:
                ready.append(p)
                arrived.add(p)

        if not ready:                          # CPU idle → jump to next arrival
            t = min(a for p, a, _ in workload if p not in arrived)
            continue

        p = ready.pop(0)                       # RR: head of queue
        if p not in responded:
            first_cpu[p] = t
            responded.add(p)

        slice_len = min(quantum, remaining[p])
        start     = t
        t        += slice_len
        remaining[p] -= slice_len

        # Admit arrivals during (start, t]
        for q, a, _ in workload:
            if q not in arrived and start < a <= t:
                ready.append(q)
                arrived.add(q)

        if remaining[p] > 0:
            ready.append(p)                    # re‑queue
        else:
            finished[p] = t

    total_wait = sum(finished[p] - a - b for p, a, b in workload)
    total_resp = sum(first_cpu[p] - a       for p, a, b in workload)
    return round(total_wait/n, 2), round(total_resp/n, 2)


def _write_workload(tmpfile, tuples):
    tmpfile.write(f"{len(tuples)}\n".encode())
    for pid, arr, bur in tuples:
        tmpfile.write(f"{pid}, {arr}, {bur}\n".encode())
    tmpfile.flush()


class TestLab2Extended(unittest.TestCase):
    """
    Four extra workloads that cover degenerate and edge behaviours.
    """

    WORKLOADS = {
        "SINGLE":      [(1, 0, 5)],
        "ALL_AT_0":    [(1, 0, 4), (2, 0, 3), (3, 0, 7)],
        "BURSTY_MIX":  [(1, 0,10), (2, 1, 1), (3, 2, 2), (4, 3, 1)],
        "FAST_FINISH": [(1, 0, 1), (2, 1, 1), (3, 1, 1)],
    }

    @classmethod
    def setUpClass(cls):
        cls.make_ok, cls.make_out = _make()
        cls.exe = "./rr"

    def test_extended_workloads(self):
        self.assertTrue(self.make_ok, msg=f"`make` failed\n{self.make_out}")

        for name, tuples in self.WORKLOADS.items():
            with self.subTest(workload=name):
                with tempfile.NamedTemporaryFile() as f:
                    _write_workload(f, tuples)

                    for q in range(1, 7):          # same quantum range
                        out = subprocess.check_output(
                            (self.exe, f.name, str(q)), text=True
                        ).strip().splitlines()

                        got_wait = float(out[0].split(":")[1])
                        got_resp = float(out[1].split(":")[1])

                        exp_wait, exp_resp = rr_reference(tuples, q)

                        self.assertTrue(
                            math.isclose(got_wait, exp_wait, abs_tol=0.01) and
                            math.isclose(got_resp, exp_resp, abs_tol=0.01),
                            msg=(
                                f"\nWork‑load: {name}  quantum={q}"
                                f"\nExpected → wait={exp_wait:.2f} resp={exp_resp:.2f}"
                                f"\nYour code → wait={got_wait:.2f} resp={got_resp:.2f}\n"
                            )
                        )


# ---------------------------------------------------------------------------
#  run via  `python3 -m unittest`  – discovery will pick up both classes
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)


#!/usr/bin/env python3
# ---------------------------------------------------------------------------
#   CS 111 – Lab 3  •  Comprehensive test‑suite for Round‑Robin scheduler
# ---------------------------------------------------------------------------

import subprocess, tempfile, unittest, math, random, itertools, os, textwrap

# ---------------------------------------------------------------------------
#  Build helpers
# ---------------------------------------------------------------------------
def _make():
    res = subprocess.run(["make"], capture_output=True, text=True)
    return res.returncode == 0, res.stdout + res.stderr

def _make_clean():
    subprocess.run(["make", "clean"], capture_output=True)

# ---------------------------------------------------------------------------
#  Reference Round‑Robin implementation (single function, no dependencies)
# ---------------------------------------------------------------------------
def rr_reference(workload, quantum):
    """
    workload : list[(pid, arrival_time, burst_time)]
    quantum  : positive int

    Returns (avg_wait, avg_resp) rounded to 2 decimals.
    """
    n = len(workload)
    remaining = {p: b for p, a, b in workload}
    first_cpu = {}
    responded = set()
    finished  = {}
    ready, arrived, t = [], set(), 0

    while len(finished) < n:
        # Admit all arrivals up to time t
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

        if remaining[p] > 0:                   # still needs CPU
            ready.append(p)
        else:                                  # done
            finished[p] = t

    total_wait = sum(finished[p] - a - b for p, a, b in workload)
    total_resp = sum(first_cpu[p] - a       for p, a, b in workload)
    return round(total_wait/n, 2), round(total_resp/n, 2)

# ---------------------------------------------------------------------------
#  Utility: write workload file in skeleton format
# ---------------------------------------------------------------------------
def _write_workload(tmp, tuples):
    tmp.write(f"{len(tuples)}\n".encode())
    for pid, arr, bur in tuples:
        tmp.write(f"{pid}, {arr}, {bur}\n".encode())
    tmp.flush()

# ---------------------------------------------------------------------------
#  ORIGINAL BASIC TESTS (unchanged except for imports)
# ---------------------------------------------------------------------------
class TestLab2Basic(unittest.TestCase):
    """The two workloads shipped with the skeleton hand‑out."""

    @classmethod
    def setUpClass(cls):
        cls.make_ok, cls.make_out = _make()
        cls.exe = "./rr"

    @classmethod
    def tearDownClass(cls):
        _make_clean()

    # workload 1 – static file processes.txt
    def test_averages(self):
        self.assertTrue(self.make_ok, msg=self.make_out)
        file_name = "processes.txt"
        exp_wait  = (0, 5.5, 5.0, 7.0, 4.5, 5.5, 6.25, 4.75)
        exp_resp  = (0, 0.75, 1.5, 2.75, 3.25, 3.25, 4.0, 4.75)
        for q in range(1, 7):
            out = subprocess.check_output((self.exe, file_name, str(q)), text=True)
            got_wait = float(out.splitlines()[0].split(":")[1])
            got_resp = float(out.splitlines()[1].split(":")[1])
            self.assertEqual(
                (got_wait, got_resp), (exp_wait[q], exp_resp[q]),
                msg=f"\nprocesses.txt  quantum={q}\n"
            )

    # workload 2 – arrival + re‑queue coincidence
    def test_arrival_and_requeue(self):
        self.assertTrue(self.make_ok, msg=self.make_out)
        exp_wait = (0, 5.0, 5.25, 6.5, 4.0, 4.5, 5.75, 4.75)
        exp_resp = (0, 0.75, 1.5, 2.25, 2.75, 3.25, 3.5, 4.75)
        with tempfile.NamedTemporaryFile() as f:
            f.write(
                b"4\n"
                b"1, 0, 7\n"
                b"2, 3, 4\n"
                b"3, 4, 1\n"
                b"4, 6, 4\n"
            )
            f.flush()
            for q in range(1, 7):
                out = subprocess.check_output((self.exe, f.name, str(q)), text=True)
                got_wait = float(out.splitlines()[0].split(":")[1])
                got_resp = float(out.splitlines()[1].split(":")[1])
                self.assertEqual(
                    (got_wait, got_resp), (exp_wait[q], exp_resp[q]),
                    msg=f"\nre‑queue test  quantum={q}\n"
                )

# ---------------------------------------------------------------------------
#  NEW STATIC EDGE‑CASE TESTS
# ---------------------------------------------------------------------------
class TestLab2EdgeCases(unittest.TestCase):
    """
    Seven hand‑crafted workloads that target specific corner cases.
    """

    WORKLOADS = {
        # 1. huge idle gap before first arrival
        "LATE_START":   [(1, 50, 5), (2, 52, 3)],
        # 2. many arrivals at the same timestamp with descending bursts
        "TIE_AT_ZERO":  [(1, 0, 10), (2, 0, 9), (3, 0, 8), (4, 0, 7)],
        # 3. bursts exactly multiples of quantum → no partial slices
        "MULTIPLE_Q":   [(1, 0, 6), (2, 2, 12), (3, 4, 18)],
        # 4. all bursts < quantum → FCFS behaviour
        "SMALL_BURSTS": [(1, 0, 1), (2, 2, 2), (3, 4, 3), (4, 6, 1)],
        # 5. quantum larger than sum(bursts) → behaves like FCFS one‑shot
        "HUGE_QUANT":   [(1, 0, 5), (2, 1, 4), (3, 2, 3)],
        # 6. many identical arrivals late in schedule
        "LATE_BURST":   [(p, 30, 1) for p in range(1, 11)],
        # 7. alternating short/long bursts trickling in
        "ZIGZAG":       [(1, 0, 15), (2, 1, 1), (3, 2, 14), (4, 3, 1),
                         (5, 4, 13), (6, 5, 1)],
    }

    QUANTA = [1, 2, 3, 4, 5, 6, 8, 16]

    @classmethod
    def setUpClass(cls):
        cls.make_ok, cls.make_out = _make()
        cls.exe = "./rr"

    @classmethod
    def tearDownClass(cls):
        _make_clean()

    def test_edge_cases(self):
        self.assertTrue(self.make_ok, msg=self.make_out)
        for name, tuples in self.WORKLOADS.items():
            with self.subTest(workload=name):
                with tempfile.NamedTemporaryFile() as f:
                    _write_workload(f, tuples)
                    for q in self.QUANTA:
                        out = subprocess.check_output(
                            (self.exe, f.name, str(q)), text=True
                        ).splitlines()
                        got_wait = float(out[0].split(":")[1])
                        got_resp = float(out[1].split(":")[1])
                        exp_wait, exp_resp = rr_reference(tuples, q)
                        self.assertTrue(
                            math.isclose(got_wait, exp_wait, abs_tol=0.01) and
                            math.isclose(got_resp, exp_resp, abs_tol=0.01),
                            msg=(
                                f"\nEdge‑case {name}  quantum={q}"
                                f"\nExpected wait={exp_wait:.2f} resp={exp_resp:.2f}"
                                f"\nGot      wait={got_wait:.2f} resp={got_resp:.2f}\n"
                            )
                        )

# ---------------------------------------------------------------------------
#  RANDOM STRESS TESTS
# ---------------------------------------------------------------------------
class TestLab2StressRandom(unittest.TestCase):
    """
    50 deterministic random workloads   (seed = 0xC111).
    Each workload has 2‑15 processes with arrivals ∈ [0,30], bursts ∈ [1,50].
    Checked for quantum 1‑‑10.
    """

    SEED    = 0xC111
    NUM_RUN = 50
    QUANTA  = range(1, 11)

    @classmethod
    def setUpClass(cls):
        cls.make_ok, cls.make_out = _make()
        cls.exe = "./rr"
        random.seed(cls.SEED)

        cls.workloads = []
        for _ in range(cls.NUM_RUN):
            n = random.randint(2, 15)
            tuples = []
            for pid in range(1, n + 1):
                arrival = random.randint(0, 30)
                burst   = random.randint(1, 50)
                tuples.append((pid, arrival, burst))
            # deterministic ordering by pid to avoid duplicate pids
            cls.workloads.append(tuple(tuples))

    @classmethod
    def tearDownClass(cls):
        _make_clean()

    def test_random_workloads(self):
        self.assertTrue(self.make_ok, msg=self.make_out)
        for idx, tuples in enumerate(self.workloads):
            with self.subTest(random_id=idx):
                with tempfile.NamedTemporaryFile() as f:
                    _write_workload(f, tuples)
                    for q in self.QUANTA:
                        out = subprocess.check_output(
                            (self.exe, f.name, str(q)), text=True
                        ).splitlines()
                        got_wait = float(out[0].split(":")[1])
                        got_resp = float(out[1].split(":")[1])
                        exp_wait, exp_resp = rr_reference(tuples, q)
                        self.assertTrue(
                            math.isclose(got_wait, exp_wait, abs_tol=0.01) and
                            math.isclose(got_resp, exp_resp, abs_tol=0.01),
                            msg=(
                                f"\nRandom workload #{idx}  quantum={q}"
                                f"\nExpected wait={exp_wait:.2f} resp={exp_resp:.2f}"
                                f"\nGot      wait={got_wait:.2f} resp={got_resp:.2f}\n"
                            )
                        )

# ---------------------------------------------------------------------------
#  Invalid‑input quick check: quantum = 0 should return non‑zero
# ---------------------------------------------------------------------------
class TestInvalidInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.make_ok, cls.make_out = _make()
        cls.exe = "./rr"

    @classmethod
    def tearDownClass(cls):
        _make_clean()

    def test_zero_quantum(self):
        self.assertTrue(self.make_ok, msg=self.make_out)
        with tempfile.NamedTemporaryFile() as f:
            _write_workload(f, [(1, 0, 1)])
            proc = subprocess.run((self.exe, f.name, "0"))
            self.assertNotEqual(proc.returncode, 0,
                                msg="Program should reject quantum=0")

# ---------------------------------------------------------------------------
#  Run with:   python3 -m unittest -v
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)


# Reproducibility appendix

Independent run of `main` at `4087859874b577adf01ed2fcd3b84eacaf6bdfc9` (merge of PR #4) on 2026-10-23, from
a fresh `git clone` plus `git submodule update --init --recursive`. No tracked file was edited and no code
was changed; every output below is copied from the run.

## Environment

| | |
|---|---|
| OS | Windows 11 Home China, 10.0.26300 (build 26300.9711), x64; Git Bash (GNU bash 5.3.15, MINGW64) |
| git | 2.56.0.windows.2; system config `core.autocrlf=true` (Git for Windows default) |
| Foundry | forge, cast, anvil 1.8.4 (commit `50af4ef`); solc 0.8.30 |
| Python | 3.12.10 (3.12.14 from `requirements-fairness.txt` not available); all pinned packages installed at the exact versions, e.g. matplotlib 3.11.2, numpy 2.5.4 |
| Submodules | `lib/forge-std` v1.16.2, `lib/openzeppelin-contracts` v5.7.0 |

## Commands and output

```text
$ forge build                                   # 11 s
Compiling 67 files with Solc 0.8.30
Compiler run successful with warnings:
$ forge test                                    # wall time 57.6 s
Ran 33 test suites in 56.88s (360.68s CPU time): 111 tests passed, 0 failed, 0 skipped (111 total tests)

$ forge test --match-contract '^FairnessTest$'  # twice, trace copied after each run
Ran 1 test suite in 387.19ms (385.49ms CPU time): 1 tests passed, 0 failed, 0 skipped (1 total tests)
$ diff fairness_trace_run1.csv fairness_trace_run2.csv
(no output)                                     # both sha256 39b85573…, equal to the committed file
$ python analysis/fairness.py
Validated 352 real attempts -> 66 agent rows -> 22 configuration rows
$ git diff --stat
(no output)                                     # git status lists the 3 CSVs as M: line endings only, see below
$ python analysis/fairness.py --plot-only       # fairness.png sha256 89ff55a6… = git show HEAD:results/fairness.png
$ python analysis/check_fairness_repro.py
IDENTICAL fairness_trace.csv / fairness_agents.csv / fairness.csv
ValueError: protected file changed: src/SpendPartition.sol                       # default checkout, exit 1
PASS: 352 attempts; 66 agent rows; 22 configurations; original RhoSweep matches;
protected files and bytecode unchanged                                            # LF checkout, exit 0

$ forge test --match-contract "DemoTraceTest|RhoSweepTest"
Ran 2 test suites in 39.87ms (51.41ms CPU time): 2 tests passed, 0 failed, 0 skipped (2 total tests)
$ diff results/rho_sweep.csv results/container_2026-09-22/rho_sweep.csv
1,34c1,34 …                                     # exit 1; with --strip-trailing-cr: no output
$ ./run_gas_sweep.sh                            # exit 49, see problem 1; rerun: exit 0, 42 s
wrote results\gas_sweep.csv
$ diff /tmp/mine.csv /tmp/ref.csv && echo "gas matches reference"
gas matches reference
$ diff results/rho_sweep.csv results/container_2026-09-30/rho_sweep.csv && echo "rho sweep matches reference"
diff: results/container_2026-09-30/rho_sweep.csv: No such file or directory
```

## Results

| Check | Result |
|---|---|
| Submodule tags v1.16.2 / v5.7.0 | pass |
| `forge build` | pass |
| `forge test`: 111 passed, 0 failed, 0 skipped | pass |
| Fairness trace: two runs byte-identical, and identical to the committed file | pass |
| `fairness.py`: regenerated CSVs byte-identical to the committed ones | pass |
| `fairness.py --plot-only`: `fairness.png` against the committed figure | pass (byte-identical) |
| `check_fairness_repro.py` | fail on the default Windows checkout; pass on an LF checkout |
| `DemoTraceTest`, `RhoSweepTest` | pass |
| `rho_sweep.csv` against `container_2026-09-22` | pass (same bytes as the committed file; plain `diff` differs only by CRLF) |
| `run_gas_sweep.sh` | pass after environment fix 1 |
| README gas check against `container_2026-09-30` | pass |
| README rho sweep check against `container_2026-09-30` | fail: reference file missing |

Nothing was skipped.

## Problems and environment fixes

1. `python3` in Git Bash resolves to the Windows Store alias, which exits with 49, so `run_gas_sweep.sh` stopped
   at `python3 analysis/gas_sweep.py` after the broadcasts had finished. Fix: a `python3` wrapper outside the
   clone, placed first on `PATH`, that calls the venv's `python.exe`. The script then ran unchanged.
2. With `core.autocrlf=true`, text files are checked out with CRLF line endings. `check_fairness_repro.py`
   hashes the raw working files, so all 11 protected files failed, even though every committed file matches
   its expected hash and the bytecode hashes matched. Fix: a second fresh clone of the same commit with
   `git clone -c core.autocrlf=false`, in which the checker passed. The same setting explains the plain-`diff`
   and `git status` noise above.
3. Python 3.12.14 was not available, so 3.12.10 was used. All outputs were still byte-identical.

## Not reproduced, and where it belongs

- **README, "Reference outputs"** (owner liukefan821, commit `3c57ca7`): the check
  `diff results/rho_sweep.csv results/container_2026-09-30/rho_sweep.csv` cannot run, because that file was
  never committed. The README also says this directory holds the invariant and differential coverage, which
  are not there either. The rho sweep itself reproduces against the `container_2026-09-22` copy.
- **`analysis/check_fairness_repro.py`** (owner hehu, commit `5ddce03`): fails on a default Windows checkout
  for line-ending reasons only (problem 2). It also rewrites two tracked files: `results/fairness_audit/environment.json`,
  whose `analysis_python` line now records the running interpreter, and `verification.json`, whose content is
  unchanged but which is rewritten with CRLF. `forge test` likewise rewrites `results/fairness_trace.csv`.

# SpendPartition — implementation skeleton

One parameterised Solidity contract: a principal budget `B_G` per time window shared by `N`
registered delegates. Delegate `i` holds a reservation `r_i`; `S = B_G - R` is a shared surplus;
`rho = rhoNum / rhoDen` sets the split. `rho = 1` is a static partition, `rho = 0` a shared pool,
`0 < rho < 1` a reserved pool.

This tree covers the payment contract, the fixed-scenario and property tests, a rho sweep and a
gas sweep. It is the feasibility spike attached to the BYOP approval request, not the full build;
"Not implemented yet" at the bottom lists what the Layout v1.1 checklist still asks for.

## Source of truth

`docs/frozen/` holds the frozen documents; the code follows them and nothing else:

| File | Role |
|---|---|
| `Spec_v1.1_errata_2026-08-08.md` | semantics (window, apportionment, debit rule, invariants I1–I5) |
| `PropertyTestPlan_v1.1_2026-08-08.md` | test IDs T1–T18, hand-computed traces in Appendix A |
| `StorageLayout_v1.1_2026-08-08.md` | packed slots, hot path, constructor bounds A1–A4, hypotheses H1–H7 |

Changing behaviour means changing those documents first.

## Toolchain

Foundry 1.x (reference run: 1.8.3), solc 0.8.30, EVM version `prague`, optimizer on with 200 runs,
`via_ir` off. Dependencies: `openzeppelin-contracts` v5.7.0, `forge-std` v1.16.2. Python 3 with
`matplotlib` for the figure (the CSV is written without it).

## Setup

```bash
cd ~/Projects/spendpartition
git init -q                      # forge install needs a git repo; skip if one exists
forge install foundry-rs/forge-std@v1.16.2 OpenZeppelin/openzeppelin-contracts@v5.7.0
forge build
```

## Tests

```bash
forge test                       # whole suite
forge test --match-contract ScenariosTest -vv
```

| File | Tests | Covers |
|---|---|---|
| `test/Scenarios.t.sol` | 19 | per-delegation caps exceeding the intended aggregate; a static split rejecting a request the aggregate could serve; shared-pool endpoints; T6, T7, T9, T12 (both cases), T13 (both appendix variants), T5/T11, T16, T17; constructor bounds; slot packing; G1/G2 storage-access counts |
| `test/Fuzz.t.sol` | 3 | T8 apportionment via the characterising inequality (`R * rhoDen <= B_G * rhoNum < (R + 1) * rhoDen`), T18 debit-order transition |
| `test/Invariant.t.sol` | 6 (6 suites) | I1, I3, I4, ghost agreement, the T2 probe (snapshot → real entry point → revert), and handler-side checks for T5, T16, T18, I2 across six configurations |
| `test/RhoSweep.t.sol` | 1 | T14 measurement, writes `results/rho_sweep.csv` |
| `test/ReferenceAnchors.t.sol` | 10 | the Appendix A traces (T6, T7, T12, T13, T5/T11, T9, T17) replayed against `SpendPartitionReference` |
| `test/Differential.t.sol` | 5 (5 suites) | both implementations driven through one call sequence and compared after every call, across five configurations |
| `test/Mutation.t.sol` | 1 | the four mutants in `test/mutants/` run against the named checks, with the resulting kill matrix printed |
| `test/AdversarialToken.t.sol` | 7 | tokens that call back during the transfer, revert, or return false |
| `test/DemoTrace.t.sol` | 1 | replays the six demo acts against the contract and writes `results/demo_trace.csv` |
| `test/WeightedScenarios.t.sol` | 17 | weighted constructor and payment scenarios against `SpendPartitionWeighted`: equal, unequal and zero weights, remainder ties broken by registration index, both rho endpoints, invalid weight arrays, full-precision budgets |
| `test/WeightedFuzz.t.sol` | 6 | allocation properties P1–P6 (conservation, quota floor/ceiling, equal weights matching `SpendPartition`, determinism, zero-weight surplus spending, own-weight monotonicity) |
| `test/WeightedInvariant.t.sol` | 5 (5 suites) | I1–I5 on the weighted contract with a ghost spend ledger, across five weight/rho configurations |
| `test/WeightedReferenceAnchors.t.sol` | 20 | hand-calculated anchors replayed against `SpendPartitionWeightedReference` |
| `test/WeightedDifferential.t.sol` | 5 (5 suites) | weighted optimised and weighted reference driven through one call sequence and compared after every call, across five configurations |
| `test/WeightedStorageAudit.t.sol` | 4 | storage writes on the weighted payment path: one write to the packed agent slot on a reservation-only payment, and no write to the reservation slot in the audited payments |
| `test/Fairness.t.sol` | 1 | the fairness measurement: 352 real payment attempts, writes `results/fairness_trace.csv` |

`forge test` on this tree (Foundry 1.8.4, run 2026-10-23): 111 tests in 33 test suites passed, 0 failed,
0 skipped. That is 53 in the nine base-contract files, 57 in the six `Weighted*` files and 1 in
`Fairness.t.sol`.

Seeds and campaign sizes live in `foundry.toml`: fuzz seed `0x5eed`, fuzz runs 1000 (256 for T8),
invariant runs 64 × depth 128, `fail_on_revert = false` (a rejected payment is a valid outcome).
The invariant configurations are `(N, B_G, rho)` = (3, 100, 1/2), (5, 101, 1/4), (2, 1000, 0),
(10, 2^64−1, 3/4), (3, 100, 1), (50, 1000, 1/3).

`afterInvariant` appends one row per run to `results/invariant_coverage.csv` (accepted, accepted
with spill into surplus, rejected, rollovers) so the campaign's coverage can be checked rather than
assumed. Write the header first:

```bash
printf "n,budget,rho,accepted,accepted_with_spill,rejected,rollovers\n" > results/invariant_coverage.csv
forge test --match-contract "Invariant_"
```

## Differential harness

`src/SpendPartitionReference.sol` is a second implementation of the same spec, organised for
reading rather than for cost: state keyed by window id instead of epoch tags, a linear scan for the
agent index, R and r_i recomputed from their definitions on every call, nothing packed. Structural
choices are deliberately different so that a shared mistake has nowhere to hide.

`SpendPartition` itself is not modified and does not inherit `ISpendPartition`; leaving that file
untouched keeps its bytecode and the gas numbers above unchanged. The harness reaches both
implementations by casting their addresses to the interface.

```bash
printf "n,budget,rho,calls,accepted,rejected,rollovers,stranger_calls,out_of_range_amounts\n" > results/differential_coverage.csv
forge test --match-contract "Differential_"
```

Each handler call issues the same payment from the same caller to both implementations and compares
the success flag; on rejection it also compares the raw return data, which is meaningful because
both declare the same error signatures and therefore the same selectors. One caller in sixteen is an
address that was never registered, and one amount in eight falls outside [1, B_G], so the guard
paths are exercised too. After every call the invariant compares `currentWindowId`, `surplusUsed`,
`reservedTotal`, `surplusCap`, every agent's `spentOf`, `reservationOf` and `indexOf`, and the token
balance each implementation has paid out. Per-run counts land in
`results/differential_coverage.csv`.

To check that the harness can still fail, break the reference on purpose and rerun one
configuration: in `SpendPartitionReference.pay`, replace the `fromReservation` line with
`uint256 fromReservation = 0;` (surplus consumed before the reservation). The run reported
`rejected by both, different revert data` within one campaign. Restore the line afterwards.

## Mutation checks

`test/mutants/` holds three copies of the optimised contract, each generated from
`src/SpendPartition.sol` with one behaviour changed and the change marked by a `MUTATION` comment:

| Mutant | Change |
|---|---|
| `MutantM1DebitOrder` | the shared surplus is consumed before the delegate's own reservation |
| `MutantM2NoWindowTag` | the window tag comparison is dropped on the payment path, so stored values are used as is |
| `MutantM3PartialFill` | a payment that exceeds the remaining surplus is filled partially instead of refused |
| `MutantM4NoGuard` | the reentrancy guard is removed from the payment path |

```bash
forge test --match-contract MutationTest -vv
```

The five checks are the named properties the suite already tests, rewritten to return a boolean so
a failure is recorded rather than aborting the run. The test asserts that every check holds on the
real contract and that no mutant survives all of them, and prints the matrix:

```
check                 SpendPartition  M1  M2  M3  M4   (1 = property held)
T6 apportionment            1        1   1   0   1
T18 debit order             1        0   1   1   1
T5/T9 window reset          1        1   0   1   1
T12 ordering                1        1   1   0   1
T16 atomicity               1        1   1   0   1
R1 one call one payment     1        1   1   1   0
```

Each mutant is caught, and M1, M2 and M4 are each caught by exactly one check: drop the T18, the
T5/T9 or the R1 property and that mutant goes through the other 110 tests untouched. To see how far a
mutant is from the original, `diff src/SpendPartition.sol test/mutants/MutantM2NoWindowTag.sol`.

M4 took two attempts to catch, and the reason is worth recording. A token that calls `pay` on its own
account is refused whatever the guard does, because it was never registered as a delegate; the
attacker has to be a delegate that is itself a contract. Even then, the aggregate bound is not what
breaks: effects are committed before the transfer, so a nested payment reads the already-updated
spend and is accounted like any other, and per-window sum spend <= B_G still holds without the guard.
What the guard buys is narrower and is what R1 states: one call to the entry point performs exactly
one payment. Without it the same call emits two.

## Adversarial tokens

Layout v1.1 Part 5 assumes a standard token. `test/mocks/AdversarialTokens.sol` drops that
assumption with three tokens and one hostile delegate:

```bash
forge test --match-contract AdversarialTokenTest -vv
```

| Case | Behaviour asserted |
|---|---|
| token re-enters `pay` during the transfer | the nested call reverts with `ReentrancyGuardReentrantCall`, whether it is bubbled or swallowed |
| delegate is a contract and re-enters under its own authority | the nested call fails, exactly one `Paid` event is emitted, and the merchant balance equals the recorded spend |
| a view is read during the callback | it returns the already-updated spend, so there is no window where value is moving but the accounting has not landed |
| `transfer` reverts | the payment reverts and both raw storage slots are byte-identical to before |
| `transfer` returns false | SafeERC20 raises `SafeERC20FailedOperation` and no state moves |

## Gas sweep

```bash
./run_gas_sweep.sh               # PORT=8546 ./run_gas_sweep.sh if 8545 is taken
```

Starts a local anvil (60 accounts from the default test mnemonic, `--hardfork prague`), broadcasts
`script/GasSweep.s.sol`, then runs `analysis/gas_sweep.py`. Every deployment and every payment is
its own transaction, so each one pays real EIP-2929 cold-access costs; `gasUsed` is read from the
receipts in `broadcast/GasSweep.s.sol/31337/run-latest.json`.

Four phases, all on the same chain:

1. `N ∈ {2, 5, 10, 20, 50}` × `rho ∈ {0, 1/2, 1}`, `B_G = 1e12` (1,000,000 USDC at 6 decimals),
   window 1 day, payments of 1e6. Per configuration: deploy, prefund, three payments by delegate
   `N-1`, one by delegate `0`.
2. the same shape on `SpendPartitionReference`, which is what the packed layout is measured against.
3. contracts with a one-second window, with the chain clock advanced between payments by the run
   script, so each payment lands in a window of its own and the first write after a rollover is
   measured on real transactions.
4. a payment of exactly `r_i + 1`, which straddles the reservation boundary.

The merchant's token balance is made non-zero before the sweep, so the recipient-side token write is
the same kind in every payment. Payment paths are labelled from each receipt's `Paid` event
(`fromSurplus` and `windowId`), not from the configuration:

| label | meaning |
|---|---|
| `reservation_only` | `fromSurplus == 0` |
| `surplus_first_ever` | the contract's first surplus write |
| `surplus_first_in_window` | first surplus write of a window that already had one before |
| `surplus_same_window` | a later surplus write inside the same window |
| `same_window` / `retag_new_window` | whether the payer's slot already carries the current window id |

Outputs: `results/gas_sweep.csv`, `results/gas_vs_N.png`, `results/gas_regimes.png`, and three
tables on stdout. Measured on the reference run of 2026-09-30:

| path | N=2 | N=10 | N=50 |
|---|---|---|---|
| optimized, reservation only | 47,123 | 47,123 | 47,123 |
| optimized, surplus, first ever | 69,737 | 69,737 | 69,737 |
| optimized, surplus, later in the same window | 52,637 | 52,637 | 52,637 |
| optimized, surplus, first write of a new window | 52,637 | 52,637 | - |
| reference, reservation only | 81,935 | 93,972 | 193,452 |
| reference, surplus, later in the same window | 77,380 | 96,720 | 196,200 |

The three surplus regimes differ only in the first one: a slot that has never been written costs
about 17,100 more than one that has. A first write after a rollover costs the same as any later
write in a window, because both overwrite a non-zero slot. Payment cost on the optimised contract
does not move with N, while the reference grows with it; deployment is the other way round
(735,201 against 800,128 at N=2, 2,168,269 against 1,998,732 at N=50).

## Batching microbenchmark

Phase 5 of the sweep registers a delegate that is a contract and has it issue k payments inside one
transaction, then sends the same k payments as k separate transactions. A warm-up payment runs first
so the contract's only zero-to-non-zero surplus write does not land inside a measured group.
Results go to `results/batching.csv`; measured on 2026-09-30, N = 10:

| rho | k | batched, 1 tx | separate, k tx | per payment, batched | per payment, separate |
|---|---|---|---|---|---|
| 0 | 1 | 56,529 | 52,637 | 56,529 | 52,637 |
| 0 | 4 | 86,499 | 210,548 | 21,625 | 52,637 |
| 0 | 16 | 206,379 | 842,192 | 12,899 | 52,637 |
| 1 | 1 | 51,015 | 47,123 | 51,015 | 47,123 |
| 1 | 4 | 78,843 | 188,492 | 19,711 | 47,123 |
| 1 | 16 | 190,155 | 753,968 | 11,885 | 47,123 |

At k = 1 batching costs more, because of the extra call frame and its calldata. From k = 2 the two
per-transaction costs that do not repeat inside a batch take over: the 21,000 intrinsic cost, and the
cold-access surcharge on every account and slot the payment touches, which is paid once per
transaction rather than once per payment. The marginal cost of one more payment inside a batch is
about 9,990 gas at rho = 0 and 9,276 at rho = 1, against 52,637 and 47,123 standalone.

## Demo trace

The six acts of the demo are produced by calling the contract, not by reimplementing the rules in a
front end:

```bash
forge test --match-contract DemoTraceTest
```

`results/demo_trace.csv` gets one row per request, with the state read back after the call:

| act | what it shows |
|---|---|
| 1 | two caps of 80 against an intended aggregate of 100: both payments pass, 160 leaves |
| 2 | a static 50/50 split: A's request for 80 is refused while half the budget sits idle |
| 3 | a shared pool serves the same 80 |
| 4 | the first mover takes all 100 and B's 20 is refused |
| 5 | rho = 1/2: A is capped at 75 and B's 25 is still served, ending at exactly 100 |
| 6 | the rho sweep in `results/rho_sweep.csv` |

## Dashboard

```bash
forge test --match-contract "DemoTraceTest|RhoSweepTest"   # writes demo_trace.csv and rho_sweep.csv
./run_gas_sweep.sh                                          # writes gas_sweep.csv
python3 analysis/build_dashboard.py                         # writes results/dashboard.html
```

`analysis/build_dashboard.py` inlines the three CSVs into `analysis/dashboard_template.html` and
writes one self-contained file, so the page opens from the file system and can be sent as a single
attachment. It shows the six acts as tabs, a slider over the rho sweep, and the per-payment gas table
with a curve against N. The front end only renders: every number was read back from a contract call
or taken from a transaction receipt, and none of the rules are reimplemented in JavaScript. Rebuild
it whenever the CSVs change.

## Extensions

### Weighted allocations

`src/SpendPartitionWeighted.sol` replaces the equal split of the reserved total `R` with integer
weights fixed at deployment, apportioned by largest remainder (Hamilton) with ties broken by
registration index; equal weights reproduce the baseline reservations. `src/SpendPartitionWeightedReference.sol`
is an independently structured second implementation for the differential harness.
`src/SpendPartition.sol` is unchanged. Spec, design and write-up are in `docs/extensions/`
(`WeightedAllocationSpec.md`, `WeightedImplementationDesign.md`, `WeightedAllocationReportDraft.md`).

Tests: `test/WeightedScenarios.t.sol`, `test/WeightedFuzz.t.sol`, `test/WeightedInvariant.t.sol`,
`test/WeightedReferenceAnchors.t.sol`, `test/WeightedDifferential.t.sol`,
`test/WeightedStorageAudit.t.sol` (57 tests; counts in the table under Tests).

```bash
forge test --match-path "test/Weighted*.t.sol"
./run_weighted_gas_sweep.sh                    # PORT=... if 18545 is taken
python3 analysis/weighted_gas_analysis.py      # offline; rebuilds the memo, its CSV and both figures
```

`run_weighted_gas_sweep.sh` refuses to run unless `forge`, `cast` and `anvil` all report 1.8.4, and
refuses a port that already has a chain. It writes `results/weighted_gas_sweep.csv`,
`results/weighted_gas_summary.csv` and `results/weighted_gas_environment.json`; the baseline
broadcasts and results are not touched. The analysis is in `results/weighted_gas_analysis.md`: fixed
payments on the weighted contract cost 1,742 gas more than the baseline at every N and every weight
profile (48,865 against 47,123 reservation only, 54,379 against 52,637 from surplus), and deployment
grows faster with N (3,885,608–4,066,258 against 1,998,732 at N = 50, depending on the profile).

## Fairness evaluation

`test/Fairness.t.sol` deploys a fresh contract for each rho in {0, 0.1, …, 1} under two fixed request
orderings (22 deployments, 352 real payment attempts, three delegates) and writes every outcome to
`results/fairness_trace.csv`. `analysis/fairness.py` aggregates the trace into
`results/fairness_agents.csv` and `results/fairness.csv` and draws `results/fairness.png` (and
`results/fairness.pdf`). The write-up, metric definitions and limitations are in
`docs/hehu_fairness_section.md`. In the adversarial ordering, all six honest requests are refused at
rho = 0 and 0.1 and none from rho = 0.8 to 1.

```bash
python3.12 -m venv .venv-fairness
source .venv-fairness/bin/activate
python -m pip install -r analysis/requirements-fairness.txt

forge test                                                  # full suite first: the checker needs rho_sweep.csv and build artifacts
forge test --match-contract '^FairnessTest$' -vv            # overwrites results/fairness_trace.csv
python analysis/fairness.py                                 # derived CSVs and both figures
python analysis/fairness.py --plot-only                     # figures only, from fairness.csv
python -m unittest discover -s analysis -p 'test_fairness.py' -v   # 14 metric unit tests
python analysis/check_fairness_repro.py                     # two fresh runs, CSVs compared byte for byte
```

Every `forge test` run rewrites `results/fairness_trace.csv`, which is tracked; the run of 2026-10-23
reproduced the committed file byte for byte apart from line endings.

## Public testnet

`docs/testnet/sepolia_deployment.md` records a replay of demo acts 1–5 on the Sepolia testnet (chain
id 11155111), matching `test/DemoTrace.t.sol` step for step, including the revert arguments of every
refused payment: the token and five act contracts, all source-verified on Etherscan, every scene
transaction with its explorer link, and the commands used. Act 6 is not replayed. Keys are read from
a git-ignored `.env`; `.env.example` lists the variables.

Testnet gas is recorded there but is not used in place of the local gas table: the gas numbers in this
README are local measurements. Deployment on Sepolia used 5,296,856–5,296,880 gas against
800,116–800,128 locally for the same bytecode.

## Reference outputs

`results/container_2026-09-30/` holds a full run (environment in `env.txt`): 52 tests passed,
0 failed; the gas CSV and its three stdout tables, the rho sweep, the invariant and differential
coverage, and both figures. `results/container_2026-09-22/` is kept as the snapshot the proposal
quotes; its gas CSV predates the reference and rollover phases and uses the earlier column set.

The 2026-09-30 reference run predates the extensions: it has none of the `Weighted*` or `Fairness`
suites, the weighted gas sweep, the fairness outputs or the Sepolia replay, so its 52 tests are not
the current total (111, see Tests). The weighted gas sweep uses it as the baseline control: 17
equivalent baseline rows of `results/weighted_gas_sweep.csv` match it exactly.

Reproduction check — payment gas and deployment gas are fixed by the bytecode and the EVM rules,
both pinned here, so a local run should match column for column:

```bash
cut -d, -f1-9,11-13 results/gas_sweep.csv > /tmp/mine.csv
cut -d, -f1-9,11-13 results/container_2026-09-30/gas_sweep.csv > /tmp/ref.csv
diff /tmp/mine.csv /tmp/ref.csv && echo "gas matches reference"
diff results/rho_sweep.csv results/container_2026-09-30/rho_sweep.csv && echo "rho sweep matches reference"
```

`window_id` (column 10) and `tx_hash` (column 14) are excluded: both depend on when the run happened,
not on the contract. If payment
gas matches but deployment gas is off by a few dozen, the likely cause is a different embedded
metadata hash (different dependency revisions); check the `forge install` tags first. Invariant
coverage counts are not part of the check: they depend on the fuzzer's RNG and will differ across
Foundry versions.

## Decisions this tree makes that the frozen documents do not specify

- Delegate identity is `msg.sender`; there is no relayer or signature path. Any diagram with a
  relayer in front of the contract contradicts the Layout v1.1 hot path.
- ABI: `pay(address recipient, uint256 amount)`, views `currentWindowId`, `isAgent`, `indexOf`,
  `reservationOf`, `spentOf`, `surplusUsed`, plus public immutables. Custom errors
  `InvalidConfig`, `ZeroAddress`, `DuplicateAgent`, `InvalidAmount`, `NotAgent`, `SurplusExhausted`.
- A `Paid(agent, recipient, amount, fromSurplus, windowId)` event. `AgentRegistered` is required by
  Layout v1.1 (the optimised contract keeps no agent array); `Paid` is an addition — the dashboard
  and the gas labelling both read it, and adding it after the benchmarks would move every number.
- `ReentrancyGuardTransient` rather than the storage-slot guard, so the reentrancy guard does not
  add a persistent slot to the per-payment storage accounting (H3). It needs `evm_version` at
  cancun or later, which `prague` satisfies.
- The per-delegation-cap baseline is modelled on the same code path as `rho = 1` with
  `B_G = sum of the individual caps`; each delegate then has an independent counter and `S = 0`.

## Not implemented yet

The Layout v1.1 Part 7 checklist is closed: reference implementation and differential harness,
mutation checks, adversarial token mocks, the three surplus write regimes, the hybrid spill case,
optimised against reference, the batching microbenchmark, and the dashboard are all in the tree.
What remains is out of scope by the spec rather than pending: configuration is fixed per deployment,
so there is no mutation path for the delegate set, B_G, rho or the window; one token per deployment;
no borrowing against a future window.

## Failure modes seen so far

- `forge install` fails outside a git repository → run `git init` first.
- Port 8545 already in use → `PORT=8546 ./run_gas_sweep.sh`.
- `matplotlib` missing → the CSV and the stdout table are still written, the figure is skipped.
- `vm.writeFile` permission errors → `fs_permissions` in `foundry.toml` must keep `./results`
  read-write.

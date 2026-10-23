"""Aggregate observed EVM payments (never simulate acceptance) using Spec section 6.

Unit: token smallest units, matching the existing RhoSweep workload.
All numeric metrics use exact Fraction arithmetic, exported to 12 decimal places.
"""

import argparse
import csv
import os
import tempfile
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ("adversarial_first", "seeded_interleaved")
ROLES = {"A": "aggressive", "B": "honest", "C": "honest"}
COUNTS = {"A": 10, "B": 3, "C": 3}
# ABI selector for SurplusExhausted(uint256,uint256), checked with `cast sig`.
# This is an interface constant, not a measured outcome.
BUDGET_ERROR_SELECTOR = "d5490551"
INT_FIELDS = (
    "seed rho_num rho_den budget request_index legitimate amount reservation own_remaining_before "
    "spent_before spent_after total_spent_before total_spent_after surplus_before surplus_after surplus_cap "
    "principal_balance_before principal_balance_after merchant_balance_before merchant_balance_after"
).split()
TRACE_FIELDS = set(INT_FIELDS) | {
    "scenario", "agent", "role", "outcome", "rejection", "revert_data", "state_before", "state_after"
}
AGENT_FIELDS = (
    "scenario seed rho_num rho_den agent role reservation demanded granted requests accepted_requests "
    "budget_rejected_requests service_ratio"
).split()
SUMMARY_FIELDS = (
    "scenario seed rho_num rho_den budget demanded granted requests accepted_requests budget_rejected_requests "
    "jain utilization stranded_capacity budget_rejection_rate honest_requests honest_budget_rejected_requests "
    "honest_budget_rejection_rate starvation_rate"
).split()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_budget_error(data, amount, own_remaining, surplus_available):
    """Audit the recorded error ABI; never use it to generate payment outcomes."""
    require(data.startswith("0x") and len(data) == 138, "budget error payload is not 68 bytes")
    payload = bytes.fromhex(data[2:])
    require(payload[:4].hex() == BUDGET_ERROR_SELECTOR, "unexpected budget error selector")
    from_surplus = int.from_bytes(payload[4:36], "big")
    available = int.from_bytes(payload[36:68], "big")
    require(from_surplus == amount - min(amount, own_remaining) and available == surplus_available,
            "budget error arguments disagree with observed state")


def service_ratio(demanded, granted):
    require(0 <= granted <= demanded, "invalid demand/grant pair")
    return Fraction(granted, demanded) if demanded else None


def jain_index(demanded, granted):
    require(len(demanded) == len(granted), "unmatched agent arrays")
    ratios = [service_ratio(d, g) for d, g in zip(demanded, granted)]
    active = [x for x in ratios if x is not None]
    denominator = len(active) * sum(x * x for x in active)
    return sum(active) ** 2 / denominator if denominator else None


def summarize(agents, budget, adversarial):
    require(budget > 0, "budget must be positive")
    demanded = sum(a["demanded"] for a in agents)
    granted = sum(a["granted"] for a in agents)
    require(0 <= granted <= budget, "aggregate budget exceeded")
    requests = sum(a["requests"] for a in agents)
    rejected = sum(a["budget_rejected_requests"] for a in agents)
    honest = [a for a in agents if a["role"] == "honest"]
    honest_requests = sum(a["requests"] for a in honest)
    honest_rejected = sum(a["budget_rejected_requests"] for a in honest)
    honest_rate = Fraction(honest_rejected, honest_requests) if honest_requests else None
    return {
        "budget": budget, "demanded": demanded, "granted": granted, "requests": requests,
        "accepted_requests": sum(a["accepted_requests"] for a in agents),
        "budget_rejected_requests": rejected,
        "jain": jain_index([a["demanded"] for a in agents], [a["granted"] for a in agents]),
        "utilization": Fraction(granted, budget),
        "stranded_capacity": budget - granted if demanded >= budget else None,
        "budget_rejection_rate": Fraction(rejected, requests) if requests else None,
        "honest_requests": honest_requests, "honest_budget_rejected_requests": honest_rejected,
        "honest_budget_rejection_rate": honest_rate,
        "starvation_rate": honest_rate if adversarial else None,
    }


def load_trace(path):
    """Fail closed on incomplete, duplicate, inconsistent or misclassified observations."""
    with Path(path).open(newline="") as f:
        reader = csv.DictReader(f)
        require(set(reader.fieldnames or []) == TRACE_FIELDS, "unexpected trace columns")
        rows = list(reader)
    require(len(rows) == 352, f"expected 352 real attempts, got {len(rows)}")
    groups = defaultdict(list)
    for raw in rows:
        require(None not in raw and all(v is not None for v in raw.values()), "malformed trace row")
        row = dict(raw)
        for field in INT_FIELDS:
            row[field] = int(raw[field])
            require(row[field] >= 0, f"negative {field}")
        require(row["scenario"] in SCENARIOS, "unknown scenario")
        require(row["agent"] in ROLES and row["role"] == ROLES[row["agent"]], "incorrect agent role")
        require(row["seed"] == 0x5EED and row["rho_den"] == 10, "unexpected seed or denominator")
        require(row["budget"] == 100 and row["amount"] == 10 and row["legitimate"] == 1,
                "workload mismatch: every measured request must be legitimate")
        require(row["outcome"] in ("accepted", "rejected"), "unknown outcome")
        require(row["rejection"] == ("none" if row["outcome"] == "accepted" else "budget"),
                "unexpected rejection classification")
        for field in ("state_before", "state_after"):
            require(row[field].startswith("0x") and len(row[field]) == 66, "invalid state hash")
            int(row[field][2:], 16)
        groups[(row["scenario"], row["rho_num"])].append(row)
    require(set(groups) == {(s, k) for s in SCENARIOS for k in range(11)}, "incomplete configuration grid")
    for scenario in SCENARIOS:
        reference_order = None
        for k in range(11):
            group = groups[(scenario, k)]
            require([r["request_index"] for r in group] == list(range(16)), "missing/duplicate/reordered attempt")
            order = [r["agent"] for r in group]
            require(Counter(order) == COUNTS, "incorrect request multiset")
            if reference_order is None:
                reference_order = order
            require(order == reference_order, "request order changed with rho")
            if scenario == "adversarial_first":
                require(order == ["A"] * 10 + ["B"] * 3 + ["C"] * 3, "incorrect adversarial ordering")
            spent = dict.fromkeys(ROLES, 0)
            reservations = {}
            previous = None
            for r in group:
                who = r["agent"]
                require(r["spent_before"] == spent[who] and r["total_spent_before"] == sum(spent.values()),
                        "observed spending is discontinuous")
                reservations.setdefault(who, r["reservation"])
                require(r["reservation"] == reservations[who], "reservation changed")
                require(r["own_remaining_before"] == max(0, r["reservation"] - r["spent_before"]),
                        "incorrect remaining reservation observation")
                if previous:
                    for name in ("total_spent", "surplus", "principal_balance", "merchant_balance", "state"):
                        require(r[name + "_before"] == previous[name + "_after"], f"discontinuous {name}")
                else:
                    require(r["total_spent_before"] == r["surplus_before"] == 0, "deployment is not fresh")
                    require(r["principal_balance_before"] == 6400, "unexpected prefunding")
                ok = r["outcome"] == "accepted"
                if ok:
                    require(r["revert_data"] == "0x", "accepted call has revert data")
                    spent[who] += r["amount"]
                    require(r["principal_balance_before"] - r["principal_balance_after"] == r["amount"],
                            "principal transfer disagrees with outcome")
                    require(r["merchant_balance_after"] - r["merchant_balance_before"] == r["amount"],
                            "merchant transfer disagrees with outcome")
                else:
                    validate_budget_error(r["revert_data"], r["amount"], r["own_remaining_before"],
                                          r["surplus_cap"] - r["surplus_before"])
                    for name in ("spent", "total_spent", "surplus", "principal_balance", "merchant_balance", "state"):
                        require(r[name + "_before"] == r[name + "_after"], f"revert changed {name}")
                    require(r["amount"] > r["own_remaining_before"], "I2-protected request was rejected")
                require(r["spent_after"] == spent[who] and r["total_spent_after"] == sum(spent.values()),
                        "observed outcome disagrees with actual spending")
                require(r["total_spent_after"] <= r["budget"], "I1 violated")
                require(r["surplus_before"] <= r["surplus_after"] <= r["surplus_cap"], "I3 violated")
                previous = r
            require(sum(reservations.values()) + group[-1]["surplus_cap"] == 100, "allocation does not conserve budget")
    return groups


def aggregate(groups):
    agent_rows, summaries = [], []
    for scenario in SCENARIOS:
        for k in range(11):
            group = groups[(scenario, k)]
            common = dict(scenario=scenario, seed=group[0]["seed"], rho_num=k, rho_den=10)
            agents = []
            for who in ROLES:
                attempts = [r for r in group if r["agent"] == who]
                accepted = [r for r in attempts if r["outcome"] == "accepted"]
                a = dict(common, agent=who, role=ROLES[who], reservation=attempts[0]["reservation"],
                         demanded=sum(r["amount"] for r in attempts), granted=sum(r["amount"] for r in accepted),
                         requests=len(attempts), accepted_requests=len(accepted),
                         budget_rejected_requests=len(attempts) - len(accepted))
                a["service_ratio"] = service_ratio(a["demanded"], a["granted"])
                agents.append(a)
            summary = dict(common, **summarize(agents, group[0]["budget"], scenario == "adversarial_first"))
            require(summary["granted"] == group[-1]["total_spent_after"], "final spending does not reconcile")
            agent_rows.extend(agents)
            summaries.append(summary)
    require(len(agent_rows) == 66 and len(summaries) == 22, "incorrect output row counts")
    return agent_rows, summaries


def cell(value):
    if value is None:
        return "N/A"
    if isinstance(value, Fraction):
        return f"{float(value):.12f}"
    return value


def write_csv(path, rows, fields):
    with Path(path).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: cell(row[key]) for key in fields} for row in rows)


def plot(summary_path, output_dir):
    """Rebuild solely from the measured summary CSV. No payment logic here."""
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "sc6109-matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    with Path(summary_path).open(newline="") as f:
        rows = list(csv.DictReader(f))
    require(len(rows) == 22 and {(r["scenario"], int(r["rho_num"])) for r in rows}
            == {(s, k) for s in SCENARIOS for k in range(11)}, "invalid summary grid")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.7), layout="constrained")
    styles = [("#0072B2", "o", "-", "Adversarial first"), ("#D55E00", "s", "--", "Seeded interleaved")]
    for scenario, (color, marker, line, label) in zip(SCENARIOS, styles):
        data = sorted((r for r in rows if r["scenario"] == scenario), key=lambda r: int(r["rho_num"]))
        xs = [int(r["rho_num"]) / int(r["rho_den"]) for r in data]
        for ax, metric in zip(axes, ("jain", "utilization", "honest_budget_rejection_rate")):
            ys = [float(r[metric]) if r[metric] != "N/A" else float("nan") for r in data]
            ax.plot(xs, ys, color=color, marker=marker, linestyle=line, linewidth=1.6, markersize=4, label=label)
    for ax, title, ylabel in zip(axes, ("(a) Service-ratio fairness", "(b) Budget utilization", "(c) Honest request rejection"),
                                 ("Jain index", "Actual spent / budget", "Budget-rejected honest requests / 6")):
        ax.set(title=title, xlabel=r"Reservation ratio $\rho$", ylabel=ylabel, xlim=(-0.025, 1.025), ylim=(-0.025, 1.04))
        ax.set_xticks([i / 5 for i in range(6)])
        ax.grid(alpha=0.22, linewidth=0.6)
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[2].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].legend(frameon=False, loc="lower right", fontsize=9)
    fig.get_layout_engine().set(w_pad=0.06, h_pad=0.06, wspace=0.07)
    fig.savefig(Path(output_dir) / "fairness.png", dpi=300, facecolor="white", metadata={"Software": "SC6109 fairness evaluation"})
    fig.savefig(Path(output_dir) / "fairness.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, default=ROOT / "results/fairness_trace.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--plot-only", action="store_true", help="rebuild figures from fairness.csv without regenerating metrics")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not args.plot_only:
        agents, summaries = aggregate(load_trace(args.trace))
        write_csv(args.output_dir / "fairness_agents.csv", agents, AGENT_FIELDS)
        write_csv(args.output_dir / "fairness.csv", summaries, SUMMARY_FIELDS)
        print("Validated 352 real attempts -> 66 agent rows -> 22 configuration rows")
    plot(args.output_dir / "fairness.csv", args.output_dir)
    print(f"Wrote publication figures to {args.output_dir}")


if __name__ == "__main__":
    main()

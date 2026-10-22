// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {SPBase} from "./Base.t.sol";
import {SpendPartition} from "../src/SpendPartition.sol";
import {MockUSDC} from "./mocks/MockUSDC.sol";

/// Spec section 6 / T14 measurement: no monotonicity assertion.
/// A is aggressive (10 requests); B/C are honest (3 each). All requests are legitimate.
/// Fresh deployment per (ordering, rho); standard funded token, one window, no forks.
contract FairnessTest is SPBase {
    string internal constant OUT = "results/fairness_trace.csv";
    uint256 internal constant SEED = 0x5eed;
    uint256 internal constant BUDGET = 100;
    uint256 internal constant AMOUNT = 10;

    struct Observation {
        uint256[3] spent;
        uint256 used;
        uint256 principalBalance;
        uint256 merchantBalance;
        bytes32 stateHash;
    }

    struct Attempt {
        Observation before_;
        Observation after_;
        uint256 reservation;
        uint256 remaining;
        bool ok;
        bytes data;
    }

    function setUp() public {
        usdc = new MockUSDC();
    }

    function test_ExportFairnessTrace() public {
        vm.createDir("results", true);
        vm.writeFile(
            OUT,
            "scenario,seed,rho_num,rho_den,budget,request_index,agent,role,legitimate,amount,outcome,rejection,revert_data,reservation,own_remaining_before,spent_before,spent_after,total_spent_before,total_spent_after,surplus_before,surplus_after,surplus_cap,principal_balance_before,principal_balance_after,merchant_balance_before,merchant_balance_after,state_before,state_after\n"
        );
        for (uint256 scenario = 0; scenario < 2; ++scenario) {
            // Build once per scenario and reuse the identical ordering at all rho values.
            uint256[16] memory order = _order(scenario);
            for (uint256 k = 0; k <= 10; ++k) {
                address[] memory agents = _agents(3);
                SpendPartition sp = _deploy(agents, BUDGET, k, 10);
                for (uint256 j = 0; j < order.length; ++j) {
                    _attempt(sp, agents, scenario, j, order[j]);
                }
            }
        }
    }

    function _order(uint256 scenario) internal pure returns (uint256[16] memory order) {
        for (uint256 i = 0; i < 16; ++i) {
            order[i] = i < 10 ? 0 : (i < 13 ? 1 : 2);
        }
        if (scenario == 1) {
            // Fisher-Yates, descending i=16..2. Portable 32-bit LCG, initial state 0x5eed.
            // The seed controls ordering only, independently of Foundry's fuzz RNG.
            uint256 state = SEED;
            for (uint256 i = 16; i > 1; --i) {
                state = (1664525 * state + 1013904223) % (2 ** 32);
                uint256 j = state % i;
                (order[i - 1], order[j]) = (order[j], order[i - 1]);
            }
        }
    }

    function _observe(SpendPartition sp, address[] memory agents) internal view returns (Observation memory o) {
        bytes32[3] memory raw;
        uint256[3] memory balances;
        for (uint256 i = 0; i < 3; ++i) {
            o.spent[i] = sp.spentOf(agents[i]);
            raw[i] = vm.load(address(sp), _agentKey(agents[i]));
            balances[i] = usdc.balanceOf(agents[i]);
        }
        o.used = sp.surplusUsed();
        o.principalBalance = usdc.balanceOf(address(sp));
        o.merchantBalance = usdc.balanceOf(MERCHANT);
        o.stateHash = keccak256(
            abi.encode(
                raw,
                vm.load(address(sp), SURPLUS_SLOT),
                o.spent,
                o.used,
                o.principalBalance,
                o.merchantBalance,
                balances,
                usdc.totalSupply(),
                sp.currentWindowId()
            )
        );
    }

    function _total(Observation memory o) internal pure returns (uint256) {
        return o.spent[0] + o.spent[1] + o.spent[2];
    }

    function _attempt(SpendPartition sp, address[] memory agents, uint256 scenario, uint256 index, uint256 who)
        internal
    {
        Attempt memory a;
        a.before_ = _observe(sp, agents);
        a.reservation = sp.reservationOf(agents[who]);
        a.remaining = a.reservation > a.before_.spent[who] ? a.reservation - a.before_.spent[who] : 0;
        // SPBase._pay discards revert bytes, so use the real entry point directly here.
        vm.prank(agents[who]);
        (a.ok, a.data) = address(sp).call(abi.encodeCall(SpendPartition.pay, (MERCHANT, AMOUNT)));
        a.after_ = _observe(sp, agents);
        _check(sp, who, a);
        _write(sp, scenario, index, who, a);
    }

    function _check(SpendPartition sp, uint256 who, Attempt memory a) internal view {
        if (!a.ok) {
            bytes memory data = a.data;
            assertEq(data.length, 68, "unexpected revert payload length");
            bytes4 selector;
            assembly { selector := mload(add(data, 32)) }
            assertEq(selector, SpendPartition.SurplusExhausted.selector, "unexpected revert selector");
            // Check both actual error arguments, not just the selector.
            assertEq(
                data,
                abi.encodeWithSelector(
                    SpendPartition.SurplusExhausted.selector,
                    AMOUNT - (AMOUNT < a.remaining ? AMOUNT : a.remaining),
                    sp.surplusCap() - a.before_.used
                ),
                "unexpected budget error arguments"
            );
            assertEq(a.before_.stateHash, a.after_.stateHash, "budget revert changed state or balances");
            assertGt(AMOUNT, a.remaining, "I2: rejected protected request");
        } else {
            assertEq(a.data.length, 0, "unexpected return data");
            assertEq(a.after_.spent[who], a.before_.spent[who] + AMOUNT, "accepted amount");
            assertEq(a.after_.principalBalance + AMOUNT, a.before_.principalBalance, "principal transfer");
            assertEq(a.after_.merchantBalance, a.before_.merchantBalance + AMOUNT, "merchant transfer");
            for (uint256 i = 0; i < 3; ++i) {
                if (i != who) assertEq(a.after_.spent[i], a.before_.spent[i], "another delegate changed");
            }
        }
        // I2 scope: registered caller, positive valid amount, adequate liquidity, standard token.
        if (AMOUNT <= a.remaining) assertTrue(a.ok, "I2: reservation-protected request failed");
        assertEq(sp.currentWindowId(), 0, "workload crossed window");
        assertLe(_total(a.after_), BUDGET, "I1");
        assertLe(a.after_.used, sp.surplusCap(), "I3");
    }

    function _write(SpendPartition sp, uint256 scenario, uint256 index, uint256 who, Attempt memory a) internal {
        string memory row = string.concat(
            scenario == 0 ? "adversarial_first" : "seeded_interleaved",
            ",",
            vm.toString(SEED),
            ",",
            vm.toString(sp.rhoNum()),
            ",10,100,",
            vm.toString(index),
            ",",
            who == 0 ? "A,aggressive" : (who == 1 ? "B,honest" : "C,honest"),
            ",1,10,",
            a.ok ? "accepted,none," : "rejected,budget,",
            vm.toString(a.data)
        );
        Observation memory before_ = a.before_;
        Observation memory after_ = a.after_;
        row = string.concat(
            row,
            ",",
            vm.toString(a.reservation),
            ",",
            vm.toString(a.remaining),
            ",",
            vm.toString(before_.spent[who]),
            ",",
            vm.toString(after_.spent[who]),
            ",",
            vm.toString(_total(before_)),
            ",",
            vm.toString(_total(after_))
        );
        row = string.concat(
            row,
            ",",
            vm.toString(before_.used),
            ",",
            vm.toString(after_.used),
            ",",
            vm.toString(sp.surplusCap()),
            ",",
            vm.toString(before_.principalBalance),
            ",",
            vm.toString(after_.principalBalance),
            ",",
            vm.toString(before_.merchantBalance),
            ",",
            vm.toString(after_.merchantBalance),
            ",",
            vm.toString(before_.stateHash),
            ",",
            vm.toString(after_.stateHash)
        );
        vm.writeLine(OUT, row);
    }
}

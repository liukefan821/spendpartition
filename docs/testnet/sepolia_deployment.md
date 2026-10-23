# Sepolia testnet replay

Status: **complete.** Acts 1–5 match `test/DemoTrace.t.sol` step for step, including the exact revert
arguments of every refused payment. Acts 2 and 5 were replayed a second time because the first attempts
ran in the wrong order (see "Runs to replace").

Every value below was read from Sepolia Etherscan on 2026-10-22 and 2026-10-23, not copied from notes.

## Network and build

| | |
|---|---|
| Network | Sepolia, chain id 11155111 |
| Explorer | https://sepolia.etherscan.io |
| RPC used | https://ethereum-sepolia-rpc.publicnode.com |
| Compiler settings | taken unchanged from `foundry.toml`: solc 0.8.30, optimizer on, 200 runs, EVM `prague`, `via_ir` off |
| Source verification | every contract below shows "Source Code Verified (Exact Match)" on Etherscan |
| Deployer | `0x8511AF6B6B36B49B233FEa034E465923a8615316` (testnet-only wallet) |
| Delegate A | `0x0d9616252f84eEcF2792e191Cf2A4DE70450928E` |
| Delegate B | `0x65B88c115b80ea07bc19Bfb74fA362EB95c1365E` |

These are throwaway testnet wallets. Their keys must not be used for anything else.

## Token

| Contract | Address | Deploy tx | Gas used |
|---|---|---|---|
| MockUSDC (`test/mocks/MockUSDC.sol`) | [0xD289391B25C4A4e4416EFf5623F200F4D4f1f518](https://sepolia.etherscan.io/address/0xD289391B25C4A4e4416EFf5623F200F4D4f1f518) | [0xc1a0a9e9…addf16](https://sepolia.etherscan.io/tx/0xc1a0a9e929cdd1ac6ad48a22ec7ab02e34975fa04dd816828a4a06d7d2addf16) | 3,315,394 |

## Deployments

All constructor arguments were decoded from the deployment transaction input. N = 2 in every act.

| Act | Contract | Deploy tx | B_G | rho | window (s) | Gas used |
|---|---|---|---|---|---|---|
| 1 | [0xBBa95bB7…38896](https://sepolia.etherscan.io/address/0xBBa95bB7761a096283B9E6ee143a6e6DF6a38896) | [0x12d34e9b…a0f736](https://sepolia.etherscan.io/tx/0x12d34e9b20519f47bafac5f0270903fcece3ac3e73aef2f962cc9226cba0f736) | 160 | 1/1 | 3600 | 5,296,868 |
| 2 | [0x85149699…4E20C](https://sepolia.etherscan.io/address/0x851496990aC307585e75F78182f6F0B31ea4E20C) | [0xda7a0aba…947c69](https://sepolia.etherscan.io/tx/0xda7a0aba698664203bed57c7df017e5a4042916b29255b02ec670fe73a947c69) | 100 | 1/1 | 604800 | 5,296,880 |
| 3 | [0xB36C95B7…0baA2](https://sepolia.etherscan.io/address/0xB36C95B7317015F7a7dA2BD5C42D7FCa3D20baA2) | [0xbf723b95…afeb82](https://sepolia.etherscan.io/tx/0xbf723b95a620a21b995be0c0862165dc0e2da09ed53562fd448819df4cafeb82) | 100 | 0/1 | 3600 | 5,296,856 |
| 4 | [0x6147Fa55…c0354](https://sepolia.etherscan.io/address/0x6147Fa551C3922E47bCe16fD4EfdfE38BA1c0354) | [0xf1e67c8f…d83e4e](https://sepolia.etherscan.io/tx/0xf1e67c8f42cf334a347da909781beff5b371e9476054c88a1ee400d693d83e4e) | 100 | 0/1 | 3600 | 5,296,856 |
| 5 | [0xA6c7ed5b…0C6C8](https://sepolia.etherscan.io/address/0xA6c7ed5bed64DD6a40380E6B9517891116C0C6C8) | [0x00bf57ef…a7c780](https://sepolia.etherscan.io/tx/0x00bf57efd40d028de303e8510bf04d7444c96dc2bb8e974f1baf5edea8a7c780) | 100 | 1/2 | 604800 | 5,296,880 |

## Scene transactions

Order is the order of `test/DemoTrace.t.sol`. Each transaction was sent only after the previous one was
confirmed. Refused payments were sent with a manual `--gas-limit` so that they land on-chain as failed
transactions.

| Act | Step | Tx | Who | Request | Expected (DemoTrace) | On-chain result | fromSurplus / error | Gas used | Link |
|---|---|---|---|---|---|---|---|---|---|
| 1 | – | mint 160 to contract | deployer | – | – | success | – | 238,395 | [0x3dd94b11…0bf23f](https://sepolia.etherscan.io/tx/0x3dd94b11e31b571d567c587530e5e6eb2e81ffe4d83fb3ac2b056470650bf23f) |
| 1 | 0 | pay | A | 80 | accepted | **success** | fromSurplus 0 | 161,017 | [0xed01c7c1…021996](https://sepolia.etherscan.io/tx/0xed01c7c134335bbe53fead28235d980135b298a6613145fe8313e2a0e9021996) |
| 1 | 1 | pay | B | 80 | accepted | **success** | fromSurplus 0 | 149,401 | [0x3405432a…ef7a2](https://sepolia.etherscan.io/tx/0x3405432ac4f0d6a66921d05a84359c60f44bd7ce8514a65afa649d4dd97ef7a2) |
| 2 | – | mint 100 to contract | deployer | – | – | success | – | 140,475 | [0xb822feec…cd84a6](https://sepolia.etherscan.io/tx/0xb822feec021495e0b9b8d83ac0315abcdead994a27b15fa02872488134cd84a6) |
| 2 | 0 | pay | A | 80 | refused | **reverted** | `SurplusExhausted(30, 0)` | 21,835 | [0x8e158cbb…c9b997](https://sepolia.etherscan.io/tx/0x8e158cbb2aba47e0452db54504fa1d68b3418eea14095d4e458c3b4582c9b997) |
| 2 | 1 | pay | A | 50 | accepted | **success** | fromSurplus 0 | 63,097 | [0x96a54add…1e94e3](https://sepolia.etherscan.io/tx/0x96a54add638473716f9d6f9f212a22eecd43a268304a347a3bdfd2bb431e94e3) |
| 3 | – | mint 100 to contract | deployer | – | – | success | – | – | [0xd53aaf4b…c149a](https://sepolia.etherscan.io/tx/0xd53aaf4b1d9ab8725c332ec220b379ace070d14fcc63d138624333c4e5ac149a) |
| 3 | 0 | pay | A | 80 | accepted | **success** | fromSurplus 80 | 173,721 | [0xb01b1f82…677e4d](https://sepolia.etherscan.io/tx/0xb01b1f82058c9c834c17d13e3e8a1fc187f11f4d17a421cd26d1381cc0677e4d) |
| 4 | – | mint 100 to contract | deployer | – | – | success | – | – | [0x26e009f0…793d8](https://sepolia.etherscan.io/tx/0x26e009f092bf6d15418306d658cb336fb9ba6f57bf88b373d6d725e7bf1793d8) |
| 4 | 0 | pay | A | 100 | accepted | **success** | fromSurplus 100 | 162,105 | [0x11c61164…e49a4](https://sepolia.etherscan.io/tx/0x11c61164e57d1801debadaacb3eea54a215ec28594cbcc21a56656b95a2e49a4) |
| 4 | 1 | pay | B | 20 | refused | **reverted** | `SurplusExhausted(20, 0)` | 21,773 | [0x2340afdb…2b9f](https://sepolia.etherscan.io/tx/0x2340afdbacce32a2008c08f201b5fa266ed5fc6cd518be2829b7bf20a7f62b9f) |
| 5 | – | mint 100 to contract | deployer | – | – | success | – | 140,475 | [0xe877b9fd…b8dca7](https://sepolia.etherscan.io/tx/0xe877b9fd25c694c3c9d5954915849821b8535f2ad3fff50b8d3311c666b8dca7) |
| 5 | 0 | pay | A | 76 | refused | **reverted** | `SurplusExhausted(51, 50)` | 21,835 | [0xe56b7bc5…bc43dd](https://sepolia.etherscan.io/tx/0xe56b7bc59848fe5f082f11e13531de554fbf7e7a1e33b3a65fe3558856bc43dd) |
| 5 | 1 | pay | A | 75 | accepted | **success** | fromSurplus 50 | 173,783 | [0x6db4fdf4…b3cb17](https://sepolia.etherscan.io/tx/0x6db4fdf4cec301a45a21d77f90dfb1e6500946125b40508cd210512b4ab3cb17) |
| 5 | 2 | pay | B | 25 | accepted | **success** | fromSurplus 0 | 51,481 | [0xe0098dd2…30fca1](https://sepolia.etherscan.io/tx/0xe0098dd234abafcab8e0306e2d53c4e90a9d567a8f631450f217af07e030fca1) |

Act 6 (the rho sweep, `results/rho_sweep.csv`) is shown from the local run only; it is not replayed on
testnet.

Every payment is in window 0 of its contract (the `Paid` events report `windowId` 0). For acts 1, 3 and 4
the last payment lands within 16 minutes of deployment, inside the 3600-second window; acts 2 and 5 use the
local 7-day window and finish within 4 minutes of deployment.

## Differences from the local demo

| | Local (`test/Base.t.sol`, `test/DemoTrace.t.sol`) | Sepolia |
|---|---|---|
| Window length | 7 days (604800 s) | 3600 s for acts 1, 3, 4; 604800 s for the replayed acts 2 and 5 |
| Contract prefund | `budget * 64` | exactly `budget` |
| Payment recipient | `0xBEEF` | `0x…0001` for A's payments, `0x…0002` for B's |
| Transaction order | exact, inside one test | one transaction at a time, each sent after the previous was confirmed |

None of these changes an outcome: no act crosses a window boundary, and no act spends more than its
budget, so the prefund never binds.

## Gas: testnet against local

Deployment gas is directly comparable (same bytecode, same constructor arguments apart from the window):

| | Local, `results/container_2026-09-30/gas_sweep_tables.txt`, N = 2 | Sepolia, N = 2 | Difference |
|---|---|---|---|
| Deploy, rho = 1 and 1/2 | 800,128 | 5,296,868 (acts 1 and 5: 5,296,880) | +4,496,740 |
| Deploy, rho = 0 | 800,116 | 5,296,856 | +4,496,740 |

The local sweep deploys with a 1-day window; acts 1, 3, 4 use 3600 s and acts 2, 5 use 604800 s. The
window only changes one constructor-argument word, which is why the 604800-second deployments cost 12 gas
more. The difference against local is otherwise identical for every rho value, and Etherscan reports an exact bytecode match, so the
gap is on the chain side (how Sepolia's current fork prices contract creation), not in the contract. The
exact cause was not investigated. This is recorded, not corrected: the gas tables in the README stay as
measured locally.

Payment gas on Sepolia (51,481 to 173,783 for accepted payments) is also far above local
(47,123 to 69,823), but the workloads are not identical: locally the recipient already holds tokens, here
each recipient's first transfer writes a new balance slot. These numbers are reported as observed and are
not used in place of the local gas table.

Refused payments used 21,773 gas (acts 1–4 contracts) or 21,835 gas (replayed acts 2 and 5).

## Runs to replace

These transactions exist on-chain but are not part of the replay. They are listed so that nobody cites them.

| Act | Contract | What happened | Why it is replaced |
|---|---|---|---|
| 2 | [0xe9aBd18F…CfdaB](https://sepolia.etherscan.io/address/0xe9aBd18FEdC080Bd6ac32DDb7a46CF5C30fCFdaB) | A paid 50 (success, 08:58:12 UTC), then A paid 80 (reverted `SurplusExhausted(80, 0)`, 09:05:24 UTC) | order reversed; DemoTrace refuses the 80 first, with A's reservation untouched |
| 5 | [0x77C55821…9998C](https://sepolia.etherscan.io/address/0x77C558218e4ac761E4342E3f5171BfdbC0a9998C) | A paid 75 (success), A paid 75 again (reverted `SurplusExhausted(75, 0)`), B paid 25 (success) | DemoTrace sends 76 first; the refused 76 is what shows A's ceiling of 75 |
| 5 | `0xEaa7CEFA470b8E3EbD2A5B4CE24B3CbC702A1B77` | received a mint of 100 at 09:51:12 UTC | earlier attempt, not used |
| 5 | – | an act 5 mint hash `0x0df601e1…0d14d0` was recorded in an earlier note | it does not exist on Sepolia; the mint for the superseded act 5 contract is `0x4111f621…6962dd` |

## Commands

Private keys live only in `.env`, which is git-ignored. Variables: `PRIVATE_KEY` (deployer), `A_KEY`,
`B_KEY`, `RPC_URL`, `ETHERSCAN_API_KEY`, and the addresses `TOKEN`, `A`, `B`, `SP`.

```bash
source .env

# token, once
forge create test/mocks/MockUSDC.sol:MockUSDC \
  --rpc-url $RPC_URL --private-key $PRIVATE_KEY --verify --broadcast

# gas money for each delegate
cast send $A --value 0.01ether --rpc-url $RPC_URL --private-key $PRIVATE_KEY
cast send $B --value 0.01ether --rpc-url $RPC_URL --private-key $PRIVATE_KEY

# one deployment per act: token, agents, budget, rhoNum, rhoDen, window (act 5 shown)
forge create src/SpendPartition.sol:SpendPartition \
  --rpc-url $RPC_URL --private-key $PRIVATE_KEY --verify --broadcast \
  --constructor-args $TOKEN "[$A,$B]" 100 1 2 604800

# prefund
cast send $TOKEN "mint(address,uint256)" $SP 100 --rpc-url $RPC_URL --private-key $PRIVATE_KEY

# act 5, in order; the refused payment needs a manual gas limit to skip estimation
cast send $SP "pay(address,uint256)" 0x0000000000000000000000000000000000000001 76 \
  --gas-limit 300000 --rpc-url $RPC_URL --private-key $A_KEY
cast send $SP "pay(address,uint256)" 0x0000000000000000000000000000000000000001 75 \
  --rpc-url $RPC_URL --private-key $A_KEY
cast send $SP "pay(address,uint256)" 0x0000000000000000000000000000000000000002 25 \
  --rpc-url $RPC_URL --private-key $B_KEY
```

These are the commands that were run for acts 2 and 5, with the literal keys and addresses replaced by
variables.

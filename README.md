# evm_contract_exporter

A convenient common interface for exporting contract data and related metrics in various formats.

## Spec mode
See `SPEC.md` for the format and constraints. Agent usage: `docs/AGENT_QUICKSTART.md`.

Examples:
```bash
evm_contract_exporter --spec spec.yaml --plan
evm_contract_exporter --spec spec.yaml --plan --plan-format json
evm_contract_exporter --spec spec.yaml
```

Notes:
- Spec mode reads the network from the spec file.
- YAML specs require `PyYAML`; JSON works without extra dependencies.
- Plan mode hits RPC today. `plan_spec` pulls ABI from chain via Brownie, so you need a working network + RPC even to validate/plan.

## Agent Constraints
- Plan hits RPC via Brownie (requires configured network + working RPC).
- ABI is pulled from chain (no offline ABI support today).
- No args or dynamic array outputs.
- Explicit mode rejects overloaded methods.
- `field` is required for tuple/struct outputs.
- `key` is not allowed when `field` is set.
- Unknown keys are rejected (strict validation).
- Spec mode uses `spec.network` (CLI `--network` ignored).
- Plan does not start Docker containers.

## Debug logging
Some exporters rely on ypricemagic for price lookups. If you need to spot long-running price calls, enable the `y.stuck?` logger at DEBUG. Details: [y.stuck? logger](CONTRIBUTING.md#y-stuck-logger).

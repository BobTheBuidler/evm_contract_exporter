# Agent Quickstart

This repo supports a strict, spec-driven workflow for exporting contract metrics. Use a spec to plan and run exports without writing Python.

## Write a spec
Start with one of the examples in `examples/spec/` and adjust:

Generic mode (auto-discover exportable view methods):
```yaml
version: "0.1"
network: "mainnet"
contract: "0x0000000000000000000000000000000000000000"
mode: "generic"
interval: "1d"
concurrency: 100
```

Explicit mode (declare exact metrics):
```yaml
version: "0.1"
network: "mainnet"
contract: "0x0000000000000000000000000000000000000000"
mode: "explicit"
interval: "15m"
metrics:
  - method: "slot0"
    field: "sqrtPriceX96"
```

Full rules live in `SPEC.md`.

## Validate / plan
Plan prints what would be exported and why things are skipped.
```bash
evm_contract_exporter --spec spec.yaml --plan
evm_contract_exporter --spec spec.yaml --plan --plan-format json
```

RPC requirement: plan hits the chain to fetch ABI via Brownie, so you need a configured network and working RPC even for planning.

## Run
```bash
evm_contract_exporter --spec spec.yaml
```

## JSON plan shape
Plan output has this structure:
```json
{
  "mode": "explicit",
  "contract": "0x0000000000000000000000000000000000000000",
  "counts": {"exportable": 1, "skipped": 1},
  "exportable": [
    {"method": "totalSupply", "field": null, "key": "total_supply", "scale": true, "status": "ok", "reason": null}
  ],
  "skipped": [
    {"method": "foo", "field": null, "key": null, "scale": null, "status": "skip", "reason": "has inputs"}
  ]
}
```

## Constraints
- Unknown keys are rejected (strict validation).
- Explicit mode requires `metrics`; generic mode forbids `metrics` and `scale`.
- `field` is required for tuple/struct outputs.
- `key` overrides are not supported when `field` is set.
- No args, no dynamic arrays, no overloaded methods in explicit mode.
- Spec mode uses `spec.network` (CLI `--network` is ignored).
- Plan does not start Docker containers.

## Skip reason glossary
These map to `reason` values in plan output.
- `skip list`: method name is in the hard-coded skip list.
- `not view`: method is not a view.
- `has inputs`: method requires args.
- `no outputs`: method returns nothing.
- `dynamic array output`: output type ends with `[]`.
- `unexportable output`: output type is not exportable.
- `field required`: tuple/struct output without `field` in explicit mode.
- `overloaded method`: explicit mode rejects overloaded methods.
- `method not found`: ABI has no such method.
- `field index out of range`: tuple index too large.
- `field name not found`: struct field not found.
- `key override not supported for derived metrics`: `key` + `field` used together.
- `invalid field`: field type not supported.

## Troubleshooting
- RPC errors: check Brownie network config + RPC availability.
- YAML parsing: install `PyYAML` or use JSON.
- Skips: compare against the glossary above.

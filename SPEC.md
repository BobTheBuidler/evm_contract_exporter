# EVM Contract Exporter Spec (Draft v0.1)

Status: Draft. This document reflects current behavior in this repo and does not add new features.
Agent usage guide: `docs/AGENT_QUICKSTART.md`.

## 1) Purpose
Define a minimal, declarative format so agents can describe what to export without writing Python code.

## 2) Non-goals (v0.1)
- Mutating contract calls (transactions).
- Methods with arguments.
- Dynamic array outputs (any ABI type ending in "[]").
- Multi-contract export in a single spec (not implemented in code).
- Custom datastore selection (code defaults to the DB-backed key/value store).
- Buffering (setting buffer raises NotImplementedError in current code).

## 3) Document format
YAML or JSON. Top-level object only.

### 3.1 Top-level fields
- version (string, required): must be "0.1".
- network (string, required): Brownie network identifier (for CLI usage). Example: "mainnet".
- contract (string, required): contract address (hex, checksum ok).
- mode (string, required): "generic" or "explicit".
- interval (string, required): duration string in the form "<int><unit>" repeated. Units: d, h, m, s.
  - Examples: "1d", "12h", "1d6h30m".
- concurrency (int, optional): exporter concurrency/semaphore value.
- scale (bool or int, optional): default scaling rule for explicit metrics. Must be omitted in generic mode.
  - In explicit mode, default is false.
- metrics (list, required if mode=explicit; must be omitted for generic): list of metric entries.

### 3.2 Metric entries (explicit mode)
Each entry maps to a ContractCallMetric or a derived metric.

Fields:
- method (string, required): view method name with no args.
- field (int or string, optional): required if the method returns a tuple or struct.
  - int selects a tuple index.
  - string selects a named struct field.
- scale (bool or int, optional): overrides top-level scale for this metric.
- key (string, optional): overrides the default metric key. Must be non-empty. Only supported when `field` is omitted.

## 4) Exportable types (current code)
Exportable ABI output types:
- bool
- int8..int256
- uint8..uint256

Unexportable types:
- string, bytes, bytes1, bytes4, bytes32, address
- any array type (type ends with "[]")

Tuple/struct outputs are allowed, but only fields of exportable types are emitted. Others are skipped with warnings.

## 5) Behavior mapping to current code
- Generic mode uses `safe_views()` + `unpack()` and exports all eligible view methods.
- Explicit mode uses `ViewMethodExporter` and only exports the listed metrics.
- Start timestamp is derived from contract creation block, rounded down to the interval, then + interval.
- All metrics within one exporter must share the same contract address.

Generic mode also applies a hard-coded skip list (not overridable in v0.1):
- decimals
- eip712Domain
- metadata
- MAX_UINT
- UINT_MAX_VALUE
- getReserves
- reserve0
- reserve1
- price0CumulativeLast
- price1CumulativeLast
- kLast
- currentCumulativePrices
- reserve0CumulativeLast
- reserve1CumulativeLast
- lastObservation
- DELEGATE_PROTOCOL_SWAP_FEES_SENTINEL

## 6) Validation rules (must)
- contract must be a valid address (Brownie `convert.to_address` compatible).
- method must be a view method with no args.
- If output is a tuple or struct, `field` is required to avoid exporting a non-scalar value.
- `key` overrides are not supported for derived metrics (when `field` is set).
- When mode=generic, `metrics` and `scale` must be omitted.
- scale rules:
  - bool: allowed. scale=true only auto-scales for int256/uint256 outputs.
  - int: allowed only for numeric outputs, must be > 0, and must end with "00" (per current validation).
- buffer is not supported and must be omitted.

## 7) Default key naming
- For method metrics, default key is the snake_case version of the method name.
- Tuple-derived metrics append "[index]".
- Struct-derived metrics append ".field_name" (snake_case).

## 8) Examples

### 8.1 Generic export (auto-discovery)
```yaml
version: "0.1"
network: "mainnet"
contract: "0x0000000000000000000000000000000000000000"
mode: "generic"
interval: "1d"
concurrency: 100
```

### 8.2 Explicit export (single metric)
```yaml
version: "0.1"
network: "mainnet"
contract: "0x0000000000000000000000000000000000000000"
mode: "explicit"
interval: "1h"
metrics:
  - method: "totalSupply"
    scale: true
```

### 8.3 Explicit export (tuple/struct field)
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

## 9) Reserved fields (not implemented)
- start
- end
- buffer
- datastore

These are intentionally omitted from v0.1 to match current behavior.

## 10) Environment requirements (current behavior)
- Plan mode pulls ABI from the chain via Brownie, so a configured network + working RPC is required even for planning.

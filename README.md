# evm_contract_exporter

A convenient common interface for exporting contract data and related metrics in various formats.

## Debug logging
Some exporters rely on ypricemagic for price lookups. If you need to spot long-running price calls, enable the `y.stuck?` logger at DEBUG. Details: [y.stuck? logger](CONTRIBUTING.md#y-stuck-logger).

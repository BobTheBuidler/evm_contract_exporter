import json
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union


_INTERVAL_RE = re.compile(r"(\d+)([dhms])")
_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

_ALLOWED_TOP_LEVEL_KEYS = {
    "version",
    "network",
    "contract",
    "mode",
    "interval",
    "concurrency",
    "scale",
    "metrics",
}

_ALLOWED_METRIC_KEYS = {
    "method",
    "field",
    "scale",
    "key",
}


class SpecValidationError(ValueError):
    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("Spec validation failed:\n- " + "\n- ".join(self.errors))


@dataclass(frozen=True)
class MetricSpec:
    method: str
    field: Optional[Union[int, str]]
    scale: Optional[Union[bool, int]]
    key: Optional[str]


@dataclass(frozen=True)
class ExportSpec:
    version: str
    network: str
    contract: str
    mode: str
    interval: timedelta
    interval_str: str
    concurrency: Optional[int]
    scale: Optional[Union[bool, int]]
    metrics: Tuple[MetricSpec, ...]


def load_spec(path: str) -> Mapping[str, Any]:
    if not isinstance(path, str) or not path:
        raise ValueError("path must be a non-empty string")
    if path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    if path.endswith(".yaml") or path.endswith(".yml"):
        try:
            import yaml
        except ImportError as e:
            raise ImportError("YAML support requires PyYAML") from e
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    raise ValueError("spec file must be .json, .yaml, or .yml")


def build_spec(raw: Mapping[str, Any]) -> ExportSpec:
    validated = _validate_and_normalize(raw)
    return validated


def validate_spec(raw: Mapping[str, Any]) -> None:
    _validate_and_normalize(raw)


def _validate_and_normalize(raw: Mapping[str, Any]) -> ExportSpec:
    errors: List[str] = []

    if not isinstance(raw, Mapping):
        raise SpecValidationError(["spec must be a mapping/dict"])

    _check_unknown_keys(raw, _ALLOWED_TOP_LEVEL_KEYS, "top-level", errors)

    version = _require_str(raw, "version", errors)
    if version and version != "0.1":
        errors.append("version must be '0.1'")

    network = _require_str(raw, "network", errors)
    if network is not None and not network.strip():
        errors.append("network must be a non-empty string")

    contract = _require_str(raw, "contract", errors)
    if contract is not None and not _ADDRESS_RE.match(contract):
        errors.append("contract must be a 0x-prefixed 40-hex address")

    mode = _require_str(raw, "mode", errors)
    if mode and mode not in {"generic", "explicit"}:
        errors.append("mode must be 'generic' or 'explicit'")

    interval_str = _require_str(raw, "interval", errors)
    interval = None
    if interval_str:
        try:
            interval = _parse_interval(interval_str)
        except ValueError as e:
            errors.append(str(e))

    concurrency = raw.get("concurrency")
    if concurrency is not None:
        if isinstance(concurrency, bool) or not isinstance(concurrency, int):
            errors.append("concurrency must be an int")
        elif concurrency <= 0:
            errors.append("concurrency must be > 0")

    scale = raw.get("scale")
    if scale is not None:
        _validate_scale(scale, "scale", errors)

    metrics_raw = raw.get("metrics")
    metrics: List[MetricSpec] = []

    if mode == "explicit":
        if metrics_raw is None:
            errors.append("metrics is required when mode=explicit")
        elif not isinstance(metrics_raw, list):
            errors.append("metrics must be a list")
        elif len(metrics_raw) == 0:
            errors.append("metrics must not be empty")
        if scale is None:
            scale = False
    elif mode == "generic":
        if metrics_raw is not None:
            errors.append("metrics must be omitted when mode=generic")
        if scale is not None:
            errors.append("scale must be omitted when mode=generic")

    if isinstance(metrics_raw, list):
        for idx, metric in enumerate(metrics_raw):
            if not isinstance(metric, Mapping):
                errors.append(f"metrics[{idx}] must be a mapping")
                continue
            _check_unknown_keys(metric, _ALLOWED_METRIC_KEYS, f"metrics[{idx}]", errors)
            method = _require_str(metric, "method", errors, prefix=f"metrics[{idx}].")
            if method is not None and not method.strip():
                errors.append(f"metrics[{idx}].method must be a non-empty string")

            field = metric.get("field")
            if field is not None:
                if isinstance(field, bool):
                    errors.append(f"metrics[{idx}].field must be int or str")
                elif isinstance(field, int):
                    if field < 0:
                        errors.append(f"metrics[{idx}].field must be >= 0")
                elif isinstance(field, str):
                    if not field:
                        errors.append(f"metrics[{idx}].field must be non-empty")
                else:
                    errors.append(f"metrics[{idx}].field must be int or str")

            metric_scale = metric.get("scale")
            if metric_scale is not None:
                _validate_scale(metric_scale, f"metrics[{idx}].scale", errors)

            key = metric.get("key")
            if key is not None:
                if not isinstance(key, str):
                    errors.append(f"metrics[{idx}].key must be a string")
                elif not key.strip():
                    errors.append(f"metrics[{idx}].key must be non-empty")

            if metric.get("field") is not None and metric.get("key") is not None:
                errors.append(
                    f"metrics[{idx}].key is not supported when field is set"
                )

            if errors:
                continue

            metrics.append(
                MetricSpec(
                    method=method,
                    field=field,
                    scale=metric_scale,
                    key=key,
                )
            )

    if errors:
        raise SpecValidationError(errors)

    assert interval is not None
    return ExportSpec(
        version=version,
        network=network,
        contract=contract,
        mode=mode,
        interval=interval,
        interval_str=interval_str,
        concurrency=concurrency,
        scale=scale,
        metrics=tuple(metrics),
    )


def _require_str(raw: Mapping[str, Any], key: str, errors: List[str], prefix: str = "") -> Optional[str]:
    value = raw.get(key)
    if value is None:
        errors.append(f"{prefix}{key} is required")
        return None
    if not isinstance(value, str):
        errors.append(f"{prefix}{key} must be a string")
        return None
    return value


def _validate_scale(value: Any, label: str, errors: List[str]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        if value <= 0:
            errors.append(f"{label} must be > 0")
        elif str(value).endswith("00") is False:
            errors.append(f"{label} must end with 00")
        return
    errors.append(f"{label} must be bool or int")


def _check_unknown_keys(raw: Mapping[str, Any], allowed: Iterable[str], label: str, errors: List[str]) -> None:
    for key in raw:
        if key not in allowed:
            errors.append(f"{label} has unknown key '{key}'")


def _parse_interval(value: str) -> timedelta:
    if not isinstance(value, str) or not value:
        raise ValueError("interval must be a non-empty string")
    matches = _INTERVAL_RE.findall(value)
    if not matches:
        raise ValueError("interval must look like 1d or 10m")
    if "".join(amount + unit for amount, unit in matches) != value:
        raise ValueError("interval must only contain d/h/m/s units")

    days = hours = minutes = seconds = 0
    for amount, unit in matches:
        amount = int(amount)
        if unit == "d":
            days += amount
        elif unit == "h":
            hours += amount
        elif unit == "m":
            minutes += amount
        elif unit == "s":
            seconds += amount
        else:
            raise ValueError("interval must use units d/h/m/s")
    result = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    if result.total_seconds() <= 0:
        raise ValueError("interval must be > 0")
    return result

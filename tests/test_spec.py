import importlib.util
from pathlib import Path

import pytest

_SPEC_PATH = Path(__file__).resolve().parents[1] / "evm_contract_exporter" / "spec.py"
_SPEC_MODULE = importlib.util.module_from_spec(
    importlib.util.spec_from_file_location("evm_contract_exporter.spec", _SPEC_PATH)
)
assert _SPEC_MODULE.__spec__ and _SPEC_MODULE.__spec__.loader
_SPEC_MODULE.__spec__.loader.exec_module(_SPEC_MODULE)

ExportSpec = _SPEC_MODULE.ExportSpec
SpecValidationError = _SPEC_MODULE.SpecValidationError
build_spec = _SPEC_MODULE.build_spec


def _base_spec():
    return {
        "version": "0.1",
        "network": "mainnet",
        "contract": "0x0000000000000000000000000000000000000000",
        "interval": "1d",
    }


def test_build_spec_generic():
    raw = _base_spec()
    raw.update({"mode": "generic"})
    spec = build_spec(raw)
    assert isinstance(spec, ExportSpec)
    assert spec.mode == "generic"
    assert spec.metrics == ()
    assert spec.interval.total_seconds() == 86400


def test_build_spec_explicit_defaults_scale():
    raw = _base_spec()
    raw.update(
        {
            "mode": "explicit",
            "scale": 100,
            "metrics": [
                {"method": "totalSupply"},
                {"method": "balanceOf", "field": 0, "scale": True},
            ],
        }
    )
    spec = build_spec(raw)
    assert len(spec.metrics) == 2
    assert spec.metrics[0].scale == 100
    assert spec.metrics[1].scale is True


def test_explicit_defaults_scale_false():
    raw = _base_spec()
    raw.update(
        {
            "mode": "explicit",
            "metrics": [
                {"method": "totalSupply"},
            ],
        }
    )
    spec = build_spec(raw)
    assert spec.scale is False
    assert spec.metrics[0].scale is False


def test_unknown_key_fails():
    raw = _base_spec()
    raw.update({"mode": "generic", "wat": 1})
    with pytest.raises(SpecValidationError):
        build_spec(raw)


def test_invalid_interval_fails():
    raw = _base_spec()
    raw.update({"mode": "generic", "interval": "1x"})
    with pytest.raises(SpecValidationError):
        build_spec(raw)


def test_generic_with_metrics_fails():
    raw = _base_spec()
    raw.update({"mode": "generic", "metrics": [{"method": "totalSupply"}]})
    with pytest.raises(SpecValidationError):
        build_spec(raw)


def test_explicit_requires_metrics():
    raw = _base_spec()
    raw.update({"mode": "explicit"})
    with pytest.raises(SpecValidationError):
        build_spec(raw)


def test_invalid_address_fails():
    raw = _base_spec()
    raw.update({"mode": "generic", "contract": "0x123"})
    with pytest.raises(SpecValidationError):
        build_spec(raw)


def test_scale_int_requires_suffix():
    raw = _base_spec()
    raw.update(
        {
            "mode": "explicit",
            "metrics": [{"method": "totalSupply", "scale": 18}],
        }
    )
    with pytest.raises(SpecValidationError):
        build_spec(raw)


def test_key_not_allowed_with_field():
    raw = _base_spec()
    raw.update(
        {
            "mode": "explicit",
            "metrics": [{"method": "slot0", "field": 0, "key": "custom"}],
        }
    )
    with pytest.raises(SpecValidationError):
        build_spec(raw)

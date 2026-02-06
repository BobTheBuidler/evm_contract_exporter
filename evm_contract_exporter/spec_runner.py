import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

import inflection
from brownie.network.contract import OverloadedMethod
from y import Contract

from evm_contract_exporter import types
from evm_contract_exporter.generic._methods import _skip
from evm_contract_exporter.metric import ContractCallMetric
from evm_contract_exporter.spec import ExportSpec, MetricSpec
from evm_contract_exporter.exporters.method import ViewMethodExporter
from evm_contract_exporter.generic.exporter import GenericContractExporter


@dataclass(frozen=True)
class PlanItem:
    method: str
    field: Optional[Union[int, str]]
    key: Optional[str]
    scale: Optional[Union[bool, int]]
    status: str
    reason: Optional[str]


def _method_key(method_name: str) -> str:
    return inflection.underscore(method_name)


def _field_key(base_key: str, field: Union[int, str]) -> str:
    if isinstance(field, int):
        return f"{base_key}[{field}]"
    return f"{base_key}.{inflection.underscore(field)}"


def _group_functions(abi: Sequence[Mapping[str, Any]]) -> Dict[str, List[Mapping[str, Any]]]:
    grouped: Dict[str, List[Mapping[str, Any]]] = {}
    for item in abi:
        if item.get("type") != "function":
            continue
        name = item.get("name")
        if not name:
            continue
        grouped.setdefault(name, []).append(item)
    return grouped


def _is_view(abi: Mapping[str, Any]) -> bool:
    return abi.get("stateMutability") == "view"


def _has_no_args(abi: Mapping[str, Any]) -> bool:
    return not abi.get("inputs")


def _is_struct_output(outputs: Sequence[Mapping[str, Any]]) -> bool:
    if len(outputs) == 1:
        output = outputs[0]
        if output.get("internalType", "").startswith("struct "):
            components = output.get("components", [])
            return components and all(c.get("name") for c in components)
        return False
    return all(o.get("name") for o in outputs)


def _tuple_outputs(outputs: Sequence[Mapping[str, Any]]) -> bool:
    return len(outputs) > 1


def _is_exportable_type(abi_type: str) -> bool:
    if abi_type.endswith("[]"):
        return False
    if abi_type in types.EXPORTABLE_TYPES:
        return True
    if abi_type in types.UNEXPORTABLE_TYPES:
        return False
    return False


def _normalize_outputs(outputs: Sequence[Mapping[str, Any]]) -> Tuple[List[Mapping[str, Any]], bool]:
    if len(outputs) == 1 and outputs[0].get("components"):
        components = outputs[0].get("components", [])
        return list(components), True
    return list(outputs), False


def _plan_for_abi_method(method_name: str, abi: Mapping[str, Any]) -> Tuple[List[PlanItem], List[PlanItem]]:
    export: List[PlanItem] = []
    skipped: List[PlanItem] = []

    if method_name in _skip.SKIP_METHODS:
        skipped.append(PlanItem(method_name, None, None, None, "skip", "skip list"))
        return export, skipped

    if not _is_view(abi):
        skipped.append(PlanItem(method_name, None, None, None, "skip", "not view"))
        return export, skipped

    if not _has_no_args(abi):
        skipped.append(PlanItem(method_name, None, None, None, "skip", "has inputs"))
        return export, skipped

    outputs = abi.get("outputs", [])
    if not outputs:
        skipped.append(PlanItem(method_name, None, None, None, "skip", "no outputs"))
        return export, skipped

    base_key = _method_key(method_name)

    if len(outputs) == 1 and outputs[0].get("type", "").endswith("[]"):
        skipped.append(PlanItem(method_name, None, None, None, "skip", "dynamic array output"))
        return export, skipped

    if _is_struct_output(outputs):
        components, single_struct = _normalize_outputs(outputs)
        for comp in components:
            comp_name = comp.get("name")
            if not comp_name:
                continue
            comp_type = comp.get("type", "")
            if comp_type.endswith("[]"):
                skipped.append(
                    PlanItem(method_name, comp_name, None, None, "skip", "dynamic array output")
                )
                continue
            if _is_exportable_type(comp_type):
                key = _field_key(base_key, comp_name)
                export.append(PlanItem(method_name, comp_name, key, None, "ok", None))
            else:
                skipped.append(
                    PlanItem(method_name, comp_name, None, None, "skip", "unexportable output")
                )
        if export or skipped:
            return export, skipped

    if _tuple_outputs(outputs):
        for idx, output in enumerate(outputs):
            abi_type = output.get("type", "")
            if abi_type.endswith("[]"):
                skipped.append(
                    PlanItem(method_name, idx, None, None, "skip", "dynamic array output")
                )
                continue
            if _is_exportable_type(abi_type):
                key = _field_key(base_key, idx)
                export.append(PlanItem(method_name, idx, key, None, "ok", None))
            else:
                skipped.append(
                    PlanItem(method_name, idx, None, None, "skip", "unexportable output")
                )
        if export or skipped:
            return export, skipped

    output_type = outputs[0].get("type", "")
    if output_type.endswith("[]"):
        skipped.append(PlanItem(method_name, None, None, None, "skip", "dynamic array output"))
        return export, skipped
    if _is_exportable_type(output_type):
        export.append(PlanItem(method_name, None, base_key, None, "ok", None))
        return export, skipped

    skipped.append(PlanItem(method_name, None, None, None, "skip", "unexportable output"))
    return export, skipped


def _plan_explicit(spec: ExportSpec, abi: Sequence[Mapping[str, Any]]) -> Tuple[List[PlanItem], List[PlanItem]]:
    export: List[PlanItem] = []
    skipped: List[PlanItem] = []
    grouped = _group_functions(abi)

    for metric in spec.metrics:
        method_name = metric.method
        items = grouped.get(method_name)
        if not items:
            skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "method not found"))
            continue
        if len(items) > 1:
            skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "overloaded method"))
            continue
        method_abi = items[0]
        if not _is_view(method_abi):
            skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "not view"))
            continue
        if not _has_no_args(method_abi):
            skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "has inputs"))
            continue
        outputs = method_abi.get("outputs", [])
        if not outputs:
            skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "no outputs"))
            continue

        if metric.field is None:
            if len(outputs) == 1 and outputs[0].get("type", "").endswith("[]"):
                skipped.append(PlanItem(method_name, None, None, metric.scale, "skip", "dynamic array output"))
                continue
            if _is_struct_output(outputs) or _tuple_outputs(outputs):
                skipped.append(PlanItem(method_name, None, None, metric.scale, "skip", "field required"))
                continue
            output_type = outputs[0].get("type", "")
            if not _is_exportable_type(output_type):
                skipped.append(PlanItem(method_name, None, None, metric.scale, "skip", "unexportable output"))
                continue
            key = metric.key or _method_key(method_name)
            export.append(PlanItem(method_name, None, key, metric.scale, "ok", None))
            continue

        if metric.key is not None and metric.field is not None:
            skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "key override not supported for derived metrics"))
            continue

        if isinstance(metric.field, int):
            if len(outputs) <= metric.field:
                skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "field index out of range"))
                continue
            output = outputs[metric.field]
            output_type = output.get("type", "")
            if output_type.endswith("[]"):
                skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "dynamic array output"))
                continue
            if not _is_exportable_type(output_type):
                skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "unexportable output"))
                continue
            key = _field_key(_method_key(method_name), metric.field)
            export.append(PlanItem(method_name, metric.field, key, metric.scale, "ok", None))
            continue

        if isinstance(metric.field, str):
            components, _single_struct = _normalize_outputs(outputs)
            comp = next((c for c in components if c.get("name") == metric.field), None)
            if comp is None:
                skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "field name not found"))
                continue
            output_type = comp.get("type", "")
            if output_type.endswith("[]"):
                skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "dynamic array output"))
                continue
            if not _is_exportable_type(output_type):
                skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "unexportable output"))
                continue
            key = _field_key(_method_key(method_name), metric.field)
            export.append(PlanItem(method_name, metric.field, key, metric.scale, "ok", None))
            continue

        skipped.append(PlanItem(method_name, metric.field, None, metric.scale, "skip", "invalid field"))

    return export, skipped


def _plan_item_field_suffix(field: Optional[Union[int, str]]) -> str:
    if isinstance(field, int):
        return f"[{field}]"
    if isinstance(field, str):
        return f".{field}"
    return ""


def _plan_item_to_dict(item: PlanItem) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "method": item.method,
        "field": item.field,
        "key": item.key,
        "scale": item.scale,
        "status": item.status,
        "reason": item.reason,
    }
    return data


def _build_plan_data(mode: str, contract: str, export: Sequence[PlanItem], skipped: Sequence[PlanItem]) -> Dict[str, Any]:
    return {
        "mode": mode,
        "contract": contract,
        "exportable": [_plan_item_to_dict(item) for item in export],
        "skipped": [_plan_item_to_dict(item) for item in skipped],
        "counts": {"exportable": len(export), "skipped": len(skipped)},
    }


def _print_plan_text(plan: Mapping[str, Any]) -> None:
    mode = plan.get("mode", "")
    title = f"{mode} plan" if mode else "plan"
    export = plan.get("exportable", [])
    skipped = plan.get("skipped", [])
    print(title)
    print(f"exportable: {len(export)}")
    print(f"skipped: {len(skipped)}")
    if export:
        print("export:")
        for item in export:
            field = _plan_item_field_suffix(item.get("field"))
            scale = f" scale={item.get('scale')}" if item.get("scale") is not None else ""
            key = f" key={item.get('key')}" if item.get("key") else ""
            print(f"  ok: {item.get('method')}{field}{key}{scale}")
    if skipped:
        print("skipped:")
        for item in skipped:
            field = _plan_item_field_suffix(item.get("field"))
            reason = f" reason={item.get('reason')}" if item.get("reason") else ""
            print(f"  skip: {item.get('method')}{field}{reason}")


def _print_plan_json(plan: Mapping[str, Any]) -> None:
    print(json.dumps(plan, indent=2, sort_keys=True))


def _build_explicit_metrics(spec: ExportSpec, contract) -> List[Any]:
    grouped = _group_functions(contract.abi)
    metrics: List[Any] = []

    for metric in spec.metrics:
        items = grouped.get(metric.method)
        if not items:
            raise ValueError(f"method not found: {metric.method}")
        if len(items) > 1:
            raise ValueError(f"overloaded method not supported: {metric.method}")
        method = getattr(contract, metric.method, None)
        if method is None:
            raise ValueError(f"method not found: {metric.method}")
        if isinstance(method, OverloadedMethod):
            raise ValueError(f"overloaded method not supported: {metric.method}")
        scale = metric.scale if metric.scale is not None else False
        call_metric = ContractCallMetric(method, scale=scale, key=metric.key or "")
        if metric.field is None:
            metrics.append(call_metric)
        else:
            metrics.append(call_metric[metric.field])
    return metrics


async def plan_spec_async(spec: ExportSpec) -> Dict[str, Any]:
    contract = await Contract.coroutine(spec.contract)
    if spec.mode == "generic":
        export, skipped = [], []
        grouped = _group_functions(contract.abi)
        for method_name, items in grouped.items():
            for item in items:
                exp, sk = _plan_for_abi_method(method_name, item)
                export.extend(exp)
                skipped.extend(sk)
        return _build_plan_data(spec.mode, spec.contract, export, skipped)
    export, skipped = _plan_explicit(spec, contract.abi)
    return _build_plan_data(spec.mode, spec.contract, export, skipped)


async def export_from_spec_async(spec: ExportSpec) -> None:
    if spec.mode == "generic":
        exporter = GenericContractExporter(
            spec.contract,
            interval=spec.interval,
            concurrency=spec.concurrency,
        )
        await exporter
        return

    contract = await Contract.coroutine(spec.contract)
    metrics = _build_explicit_metrics(spec, contract)
    exporter = ViewMethodExporter(
        *metrics,
        interval=spec.interval,
        concurrency=spec.concurrency,
    )
    await exporter


def plan_spec(spec: ExportSpec, *, format: str = "text") -> None:
    plan = asyncio.get_event_loop().run_until_complete(plan_spec_async(spec))
    if format == "json":
        _print_plan_json(plan)
    else:
        _print_plan_text(plan)


def export_from_spec(spec: ExportSpec) -> None:
    asyncio.get_event_loop().run_until_complete(export_from_spec_async(spec))

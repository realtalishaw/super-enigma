#!/usr/bin/env python3
import asyncio
import json
import time
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is on sys.path when running as a script
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.dsl_generator.generator import DSLGeneratorService
from services.dsl_generator.models import GenerationRequest
from services.dsl_generator.response_parser import ResponseParser
from core.validator import validate, lint, Stage, LintContext

API_URL = "http://localhost:8001"


async def get_http_lint_context_with_session(session) -> LintContext:
    class HTTPCatalogAdapter:
        def __init__(self, api_url: str, session):
            self.api_url = api_url
            self.session = session

        async def get_provider_by_slug(self, slug: str):
            try:
                async with self.session.get(f"{self.api_url}/catalog/providers/{slug}", timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("tools"):
                            return {
                                "metadata": {"slug": slug},
                                "actions": data["tools"].get("actions", []),
                                "triggers": data["tools"].get("triggers", []),
                            }
            except Exception:
                return None
            return None

        async def get_tool_by_slug(self, action_name: str, toolkit_slug: str):
            provider = await self.get_provider_by_slug(toolkit_slug)
            if not provider:
                return None
            for a in provider.get("actions", []):
                if a.get("slug") == action_name:
                    return a
            for t in provider.get("triggers", []):
                if t.get("slug") == action_name:
                    return t
            return None

        async def get_catalog(self):
            return {"providers": {}}

    # Health check
    async with session.get(f"{API_URL}/health", timeout=5) as resp:
        if resp.status != 200:
            raise RuntimeError("API health check failed")

    # Cache status sanity
    async with session.get(f"{API_URL}/cache/status", timeout=10) as resp:
        if resp.status != 200:
            raise RuntimeError("Cache status failed")
        cache = await resp.json()
        if not cache.get("cache", {}).get("has_cached_data"):
            raise RuntimeError("Cache has no data")

    return LintContext(catalog=HTTPCatalogAdapter(API_URL, session), connections=None)


def infer_stage_from_doc(doc: Dict[str, Any]) -> Stage:
    st = (doc or {}).get("schema_type", "template").lower()
    if st == "executable":
        return Stage.EXECUTABLE
    if st == "dag":
        return Stage.DAG
    return Stage.TEMPLATE


async def run_case(
    gen: DSLGeneratorService, context_for_lint: Optional[LintContext], case: Dict[str, Any]
) -> Dict[str, Any]:
    req = GenerationRequest(
        user_prompt=case["prompt"],
        workflow_type=case.get("workflow_type", "template"),
        complexity=case.get("complexity", "medium"),
        selected_apps=case.get("selected_apps"),
    )

    t0 = time.time()
    resp = await gen.generate_workflow(req)
    latency_ms = int((time.time() - t0) * 1000)

    out: Dict[str, Any] = {
        "success": bool(resp.success),
        "latency_ms": latency_ms,
        "schema_valid": False,
        "catalog_compliant": False,
        "lint_errors": 0,
        "lint_warnings": 0,
        "confidence": float(resp.confidence or 0.0),
        "raw_response_preview": (resp.raw_response[:240] + "…") if getattr(resp, "raw_response", None) and len(resp.raw_response) > 240 else getattr(resp, "raw_response", None),
        "input": {
            "workflow_type": req.workflow_type,
            "complexity": req.complexity,
            "selected_apps": req.selected_apps or [],
            "prompt_summary": (req.user_prompt[:120] + ("…" if len(req.user_prompt) > 120 else "")),
        },
    }

    if not resp.success or not resp.dsl_template:
        out["error_message"] = resp.error_message or "generation failed"
        return out

    doc = resp.dsl_template
    stage = infer_stage_from_doc(doc)
    out["stage"] = stage.value
    out["dsl"] = doc

    v = await validate(stage, doc)
    out["schema_valid"] = bool(v.ok)
    out["validation_errors"] = [
        {
            "code": e.code,
            "path": e.path,
            "message": e.message,
            "stage": getattr(e.stage, "value", str(e.stage)),
        }
        for e in v.errors
    ]

    # Linting with real HTTP catalog when possible; fallback to empty context
    if context_for_lint is None:
        ctx = LintContext(catalog=None, connections=None)
    else:
        ctx = context_for_lint
    l = await lint(stage, doc, ctx)
    out["lint_errors"] = len(l.errors)
    out["lint_warnings"] = len(l.warnings)
    out["lint_error_details"] = [
        {"code": f.code, "severity": f.severity, "path": f.path, "message": f.message}
        for f in l.errors
    ]
    out["lint_warning_details"] = [
        {"code": f.code, "severity": f.severity, "path": f.path, "message": f.message}
        for f in l.warnings
    ]

    # Catalog compliance using the generator's cached catalog (real data)
    parser = ResponseParser()
    catalog_dict = getattr(gen.catalog_manager, "_catalog_cache", {}) or {}
    comp = parser.verify_catalog_compliance(doc, catalog_dict)
    out["catalog_compliant"] = bool(comp.get("is_compliant", False))
    out["catalog_errors"] = comp.get("errors", [])

    return out


def percentile(values: List[int], p: float) -> int:
    if not values:
        return 0
    values_sorted = sorted(values)
    k = max(0, min(len(values_sorted) - 1, int(round((p / 100.0) * (len(values_sorted) - 1)))))
    return int(values_sorted[k])


def _summarize_failures(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.get("success"))
    failed = total - passed
    parse_fail = sum(1 for r in results if (not r.get("success") and r.get("error_message", "").lower().startswith("failed to parse")))
    schema_fail = sum(1 for r in results if (not r.get("schema_valid") and r.get("success") is not True))
    catalog_fail = sum(1 for r in results if (not r.get("catalog_compliant")))
    lint_fail = sum(1 for r in results if (r.get("lint_errors", 0) > 0))

    # Top lint error codes
    code_counts: Dict[str, int] = {}
    for r in results:
        for e in r.get("lint_error_details", []):
            code_counts[e.get("code", "")] = code_counts.get(e.get("code", ""), 0) + 1
    top_lint_codes = sorted(code_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "parse_failures": parse_fail,
        "schema_failures": schema_fail,
        "catalog_failures": catalog_fail,
        "lint_failure_cases": lint_fail,
        "top_lint_error_codes": top_lint_codes,
    }


def _save_artifacts(save_dir: Path, idx: int, result: Dict[str, Any], dsl: Optional[Dict[str, Any]]):
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / f"case_{idx:03d}_report.json").write_text(json.dumps(result, indent=2))
        if dsl is not None:
            (save_dir / f"case_{idx:03d}_output.json").write_text(json.dumps(dsl, indent=2))
        raw = result.get("raw_response_preview")
        if raw:
            # Save full raw if present in result's extended field (preview might be truncated)
            # We prefer to store the preview; if you want full, add it to result later.
            (save_dir / f"case_{idx:03d}_raw.txt").write_text(str(raw))
    except Exception:
        pass


async def main(dataset_path: str, out_path: Optional[str] = None, save_dir: Optional[str] = None):
    cases = json.loads(Path(dataset_path).read_text())

    gen = DSLGeneratorService()
    await gen.initialize()
    # Try to ensure catalog cache is warm
    try:
        await gen.preload_catalog_cache()
    except Exception:
        pass

    # Prefer real HTTP catalog for lint context
    results: List[Dict[str, Any]] = []
    context_for_lint: Optional[LintContext] = None

    # Create default save directory if not provided
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    default_dir = Path(ROOT) / "services" / "dsl_generator" / "evals" / f"run-{run_id}"
    save_path = Path(save_dir) if save_dir else default_dir
    try:
        save_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            context_for_lint = await get_http_lint_context_with_session(session)
            for i, c in enumerate(cases, 1):
                res = await run_case(gen, context_for_lint, c)
                results.append(res)
                _save_artifacts(save_path, i, res, res.get("dsl"))
    except Exception:
        for i, c in enumerate(cases, 1):
            res = await run_case(gen, None, c)
            results.append(res)
            _save_artifacts(save_path, i, res, res.get("dsl"))

    n = max(1, len(results))
    latencies = [r["latency_ms"] for r in results]
    agg = {
        "count": len(results),
        "pass_at_1": sum(1 for r in results if r["success"]) / n,
        "schema_valid_rate": sum(1 for r in results if r["schema_valid"]) / n,
        "catalog_compliance_rate": sum(1 for r in results if r["catalog_compliant"]) / n,
        "avg_lint_errors": sum(r["lint_errors"] for r in results) / n,
        "avg_lint_warnings": sum(r["lint_warnings"] for r in results) / n,
        "p50_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
        "pass_count": sum(1 for r in results if r["success"]),
        "fail_count": sum(1 for r in results if not r["success"]),
        "failure_summary": _summarize_failures(results),
    }

    out = {"aggregate": agg, "results": results, "run": {"id": run_id, "save_dir": str(save_path)}}
    text = json.dumps(out, indent=2)
    print(text)
    # Default summary path inside the run dir if not provided
    summary_path = Path(out_path) if out_path else (save_path / "summary.json")
    try:
        summary_path.write_text(text)
    except Exception:
        pass


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python services/dsl_generator/eval.py DATASET_JSON [OUT_JSON] [SAVE_DIR]"
        )
        raise SystemExit(2)
    dataset = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    save_dir = sys.argv[3] if len(sys.argv) > 3 else None
    asyncio.run(main(dataset, out, save_dir))



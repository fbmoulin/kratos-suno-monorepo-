"""Prompt Lab — CLI para A/B testing de system prompts.

Uso:
    # Compara duas versões de prompt em múltiplos casos de teste
    python -m prompt_lab.run \\
        --prompts v1_baseline v2_stricter \\
        --test-cases test_cases/artists.json \\
        --output results/

    # Uma versão só, interativo
    python -m prompt_lab.run --prompts v1_baseline --interactive

Resultado: JSON + CSV com dados para avaliação humana.

Padrão inspirado em pseuno-ai (ericdjm/pseuno-ai, MIT).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

# Adiciona backend ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.dna_text_extractor import DNAExtractionError, TextDNAExtractor
from app.services.prompt_compressor import (
    ComplianceError,
    compress_all,
)


# ---------------------------------------------------------------------------
# Test case loading
# ---------------------------------------------------------------------------

def load_test_cases(paths: list[Path]) -> list[dict]:
    """Carrega casos de teste de um ou mais arquivos JSON.

    Formato esperado:
        [
            {
                "name": "Coldplay",
                "subject": "Coldplay",
                "expected_genre_contains": ["alternative", "rock"],
                "expected_bpm_range": [70, 140],
                "forbidden_in_output": ["coldplay", "chris martin"]
            }
        ]
    """
    cases = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            cases.extend(json.load(f))
    return cases


# ---------------------------------------------------------------------------
# Assertion runner
# ---------------------------------------------------------------------------

def check_assertions(case: dict, result: dict) -> dict:
    """Verifica asserções estruturais automáticas sobre um resultado."""
    dna = result["sonic_dna"]
    variants = result["variants"]

    checks = {}

    # 1. Gênero esperado aparece
    if expected := case.get("expected_genre_contains"):
        genre_str = (
            f"{dna['genre_primary']} {dna.get('genre_secondary') or ''}"
        ).lower()
        checks["genre_matches"] = all(e.lower() in genre_str for e in expected)

    # 2. BPM no range esperado
    if bpm_range := case.get("expected_bpm_range"):
        bpm = dna["bpm_typical"]
        checks["bpm_in_range"] = bpm_range[0] <= bpm <= bpm_range[1]

    # 3. Compliance: termos proibidos não vazaram
    forbidden = case.get("forbidden_in_output") or dna.get("forbidden_terms", [])
    if forbidden:
        leaked = []
        for v in variants:
            for term in forbidden:
                if term.lower() in v["prompt"].lower():
                    leaked.append((v["label"], term))
        checks["no_forbidden_leak"] = len(leaked) == 0
        if leaked:
            checks["_leaked_terms"] = leaked

    # 4. Char limits
    checks["all_variants_under_200"] = all(v["char_count"] <= 200 for v in variants)

    # 5. Variantes diferentes
    prompts = {v["prompt"] for v in variants}
    checks["variants_are_unique"] = len(prompts) == len(variants)

    return checks


# ---------------------------------------------------------------------------
# Runner principal
# ---------------------------------------------------------------------------

async def run_test_case(
    case: dict,
    prompt_version: str,
) -> dict:
    """Roda um caso de teste com uma versão de prompt."""
    extractor = TextDNAExtractor(prompt_version=prompt_version)

    result = {
        "case_name": case["name"],
        "subject": case["subject"],
        "prompt_version": prompt_version,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "unknown",
        "error": None,
        "sonic_dna": None,
        "variants": None,
        "checks": None,
    }

    try:
        dna = await extractor.extract(case["subject"])
        variants = compress_all(dna)

        result["status"] = "ok"
        result["sonic_dna"] = dna.model_dump()
        result["variants"] = [v.model_dump() for v in variants]
        result["checks"] = check_assertions(case, {
            "sonic_dna": result["sonic_dna"],
            "variants": result["variants"],
        })

    except DNAExtractionError as exc:
        result["status"] = "extraction_error"
        result["error"] = str(exc)
    except ComplianceError as exc:
        result["status"] = "compliance_failure"
        result["error"] = str(exc)
    except Exception as exc:
        result["status"] = "unknown_error"
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


async def run_matrix(
    cases: list[dict],
    prompt_versions: list[str],
) -> list[dict]:
    """Roda matriz cases × versions em paralelo."""
    tasks = [
        run_test_case(case, version)
        for case in cases
        for version in prompt_versions
    ]
    return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_results(results: list[dict], output_dir: Path) -> None:
    """Salva JSON completo + CSV para avaliação humana."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # JSON completo
    json_path = output_dir / f"results_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # CSV simplificado para eval humano
    csv_path = output_dir / f"results_{timestamp}.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "case_name",
            "prompt_version",
            "status",
            "genre_primary",
            "bpm",
            "conservative_prompt",
            "faithful_prompt",
            "creative_prompt",
            "all_checks_pass",
            "human_rating_1_5",
            "human_notes",
        ])
        for r in results:
            if r["status"] == "ok":
                dna = r["sonic_dna"]
                variants = {v["label"]: v["prompt"] for v in r["variants"]}
                checks = r["checks"] or {}
                all_pass = all(v for k, v in checks.items() if not k.startswith("_"))
                writer.writerow([
                    r["case_name"],
                    r["prompt_version"],
                    r["status"],
                    dna["genre_primary"],
                    dna["bpm_typical"],
                    variants.get("conservative", ""),
                    variants.get("faithful", ""),
                    variants.get("creative", ""),
                    all_pass,
                    "",  # preencher humano
                    "",
                ])
            else:
                writer.writerow([
                    r["case_name"],
                    r["prompt_version"],
                    r["status"],
                    "", "", "", "", "",
                    False,
                    "",
                    r["error"] or "",
                ])

    print(f"\n📁 Resultados salvos em:")
    print(f"   JSON: {json_path}")
    print(f"   CSV:  {csv_path}")


def print_summary(results: list[dict]) -> None:
    """Imprime tabela resumo no terminal."""
    print("\n" + "=" * 80)
    print(f"{'CASE':<30} {'VERSION':<20} {'STATUS':<20} {'CHECKS PASS':<10}")
    print("=" * 80)
    for r in results:
        if r["status"] == "ok":
            checks = r["checks"] or {}
            public_checks = {k: v for k, v in checks.items() if not k.startswith("_")}
            passed = sum(1 for v in public_checks.values() if v)
            total = len(public_checks)
            check_str = f"{passed}/{total}"
        else:
            check_str = "—"
        print(f"{r['case_name']:<30} {r['prompt_version']:<20} {r['status']:<20} {check_str:<10}")
    print("=" * 80)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Prompt Lab — A/B test de prompts")
    parser.add_argument(
        "--prompts",
        nargs="+",
        default=["v1_baseline"],
        help="Versões de prompt para testar (arquivos em app/prompts/versions/)",
    )
    parser.add_argument(
        "--test-cases",
        nargs="+",
        type=Path,
        default=[Path(__file__).parent / "test_cases" / "artists.json"],
        help="Arquivo(s) JSON com casos de teste",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("prompt_lab/results"),
        help="Diretório para salvar resultados",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Modo interativo: lê subjects do stdin",
    )

    args = parser.parse_args()

    if args.interactive:
        print("Modo interativo. Digite subjects (Ctrl+D para terminar):")
        cases = []
        for line in sys.stdin:
            subject = line.strip()
            if subject:
                cases.append({"name": subject, "subject": subject})
    else:
        cases = load_test_cases(args.test_cases)

    print(f"\n🧪 Rodando {len(cases)} caso(s) × {len(args.prompts)} versão(ões) = "
          f"{len(cases) * len(args.prompts)} testes...\n")

    results = asyncio.run(run_matrix(cases, args.prompts))

    print_summary(results)
    save_results(results, args.output)


if __name__ == "__main__":
    main()

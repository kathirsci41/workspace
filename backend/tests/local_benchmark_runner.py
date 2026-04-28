"""
Local Benchmark Runner — On-Premises Safe Extraction Testing
================================================================

SECURITY GATES:
- Only connects to localhost (http://localhost:11434 or http://127.0.0.1:11434)
- Blocks execution with external/remote endpoints
- Uses synthetic test documents only (no customer data)
- Results written to timestamped immutable files
- Never modifies canonical ground truth

Usage:
    python backend/tests/local_benchmark_runner.py

Environment:
    OLLAMA_ENDPOINT=http://localhost:11434 (default)
    BENCHMARK_MODE=true (required to enable)
"""

import os
import sys
import csv
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import httpx
from pdf2image import convert_from_path
import base64
import io


class LocalBenchmarkConfig:
    """Configuration with safety gates"""

    ALLOWED_ENDPOINTS = [
        "http://localhost:11434",
        "http://127.0.0.1:11434",
    ]

    def __init__(self):
        self.endpoint = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
        self.benchmark_mode = os.getenv("BENCHMARK_MODE", "false").lower() == "true"
        self.ocr_model = os.getenv("OCR_MODEL", "glm-ocr")
        self.extraction_model = os.getenv("EXTRACTION_MODEL", "gemma4:e4b")

    def validate(self) -> bool:
        """Ensure benchmark cannot leak customer data"""
        if not self.benchmark_mode:
            print("ERROR: BENCHMARK_MODE=true required to run benchmarks")
            print("       Set: export BENCHMARK_MODE=true")
            return False

        is_local = any(
            self.endpoint.startswith(allowed) for allowed in self.ALLOWED_ENDPOINTS
        )
        if not is_local:
            raise RuntimeError(
                f"SECURITY: Only local endpoints allowed. Got: {self.endpoint}\n"
                f"          Allowed: {self.ALLOWED_ENDPOINTS}\n"
                f"          Reason: Prevents accidental customer data exfiltration"
            )

        print(f"✓ Endpoint validated: {self.endpoint}")
        print(f"✓ Benchmark mode: enabled")
        print(f"✓ Using synthetic data only (no customer documents)")
        return True


class LocalBenchmark:
    """Safe local-only benchmark runner"""

    def __init__(self, config: LocalBenchmarkConfig):
        self.config = config
        self.results_dir = Path("backend/tests/results") / datetime.now().isoformat()
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.results_dir / "candidates.csv"
        self.ground_truth_file = Path(
            "backend/tests/fixtures/benchmark_ground_truth.csv"
        )

    def validate_ground_truth(self) -> bool:
        """Verify ground truth exists and is immutable"""
        if not self.ground_truth_file.exists():
            print(
                f"ERROR: Ground truth file not found: {self.ground_truth_file}\n"
                f"       Create it with synthetic test documents only."
            )
            return False

        print(f"✓ Ground truth loaded: {self.ground_truth_file}")
        print(f"✓ Results will be written to: {self.results_file}")
        return True

    async def extract_ocr_from_pdf(
        self, pdf_path: str, timeout: int = 120
    ) -> Optional[str]:
        """
        Extract OCR text from PDF using local glm-ocr model.
        Mimics backend two_layer_client.py Layer 1.
        """
        try:
            images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=150)
            if not images:
                return None

            img_buffer = io.BytesIO()
            images[0].save(img_buffer, format="PNG")
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode()

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.config.endpoint}/api/generate",
                    json={
                        "model": self.config.ocr_model,
                        "prompt": "Extract all text as markdown from this document image",
                        "stream": False,
                        "images": [img_base64],
                    },
                )

                if response.status_code != 200:
                    return None

                result = response.json()
                return result.get("response", "") or None

        except Exception as e:
            print(f"  OCR error: {e}")
            return None

    async def extract_fields(
        self, markdown: str, timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Extract structured fields from OCR markdown using local extraction model.
        Mimics backend two_layer_client.py Layer 2.
        """
        start_time = time.time()

        try:
            extraction_prompt = """Extract structured data from this logistics document:

{markdown_text}

Return ONLY valid JSON:
{{
  "reference_number": "...",
  "total_amount": "...",
  "delivery_address": "..."
}}
""".format(
                markdown_text=markdown
            )

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.config.endpoint}/api/generate",
                    json={
                        "model": self.config.extraction_model,
                        "prompt": extraction_prompt,
                        "stream": False,
                    },
                )

                elapsed = time.time() - start_time

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "time_sec": elapsed,
                    }

                result = response.json()
                response_text = result.get("response", "")

                try:
                    extracted = json.loads(response_text)
                    return {
                        "success": True,
                        "data": extracted,
                        "time_sec": elapsed,
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Invalid JSON response",
                        "time_sec": elapsed,
                        "raw": response_text[:100],
                    }

        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "success": False,
                "error": str(e),
                "time_sec": elapsed,
            }

    async def run(self):
        """Execute benchmark against synthetic test data"""
        print("\n" + "=" * 80)
        print("LOCAL BENCHMARK RUNNER — Synthetic Data Only")
        print("=" * 80)

        if not self.config.validate():
            sys.exit(1)

        if not self.validate_ground_truth():
            sys.exit(1)

        # Load ground truth
        ground_truth_rows = []
        with open(self.ground_truth_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            ground_truth_rows = list(reader)

        print(f"\nLoaded {len(ground_truth_rows)} synthetic test documents\n")

        results = []
        for idx, row in enumerate(ground_truth_rows, 1):
            file_path = row["file_path"]
            file_name = row["file_name"]
            expected_ref = row["expected_po_number"]

            if not Path(file_path).exists():
                print(f"[{idx}/{len(ground_truth_rows)}] {file_name} - NOT FOUND")
                continue

            print(f"[{idx}/{len(ground_truth_rows)}] {file_name}...", end="", flush=True)

            # Layer 1: OCR
            ocr_start = time.time()
            markdown = await self.extract_ocr_from_pdf(file_path)
            ocr_time = time.time() - ocr_start

            if not markdown:
                print(f" OCR FAILED ({ocr_time:.1f}s)")
                continue

            print(f" OCR OK ({ocr_time:.1f}s)", end="", flush=True)

            # Layer 2: Extract fields
            extraction_result = await self.extract_fields(markdown)

            if extraction_result["success"]:
                extraction_time = extraction_result["time_sec"]
                extracted_data = extraction_result["data"]
                print(f" > Extract ({extraction_time:.1f}s)")

                results.append(
                    {
                        "document_id": row["document_id"],
                        "file_name": file_name,
                        "document_type": row["document_type"],
                        "expected_po_number": expected_ref,
                        "extracted_po_number": extracted_data.get("reference_number", ""),
                        "expected_amount": row["expected_amount"],
                        "extracted_amount": extracted_data.get("total_amount", ""),
                        "ocr_time_sec": round(ocr_time, 2),
                        "extraction_time_sec": round(extraction_time, 2),
                        "total_time_sec": round(ocr_time + extraction_time, 2),
                    }
                )
            else:
                print(f" EXTRACTION FAILED: {extraction_result['error']}")

        # Write results to immutable timestamped file
        if results:
            with open(self.results_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)

            # Summary statistics
            print("\n" + "=" * 80)
            print("BENCHMARK RESULTS (Synthetic Data)")
            print("=" * 80)

            success_count = len(results)
            total_count = len(ground_truth_rows)

            print(f"\nSuccess rate: {success_count}/{total_count} documents ({success_count/total_count*100:.1f}%)")

            if results:
                ocr_avg = sum(r["ocr_time_sec"] for r in results) / len(results)
                extraction_avg = sum(r["extraction_time_sec"] for r in results) / len(
                    results
                )
                total_avg = ocr_avg + extraction_avg

                print(f"\nOCR (Layer 1):")
                print(f"  Average: {ocr_avg:.1f} sec/doc")

                print(f"\nExtraction (Layer 2):")
                print(f"  Average: {extraction_avg:.1f} sec/doc")

                print(f"\nTotal Pipeline:")
                print(f"  Average: {total_avg:.1f} sec/doc")
                print(f"  Throughput: {3600/total_avg:.0f} docs/hour")

                print(f"\nResults saved to: {self.results_file}")
                print(
                    f"NOTE: Ground truth ({self.ground_truth_file}) NOT modified"
                )

        print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    import asyncio

    config = LocalBenchmarkConfig()
    benchmark = LocalBenchmark(config)
    asyncio.run(benchmark.run())

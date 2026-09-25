"""
CLI Tool for PII Redaction.
Runs end-to-end PII detection, pseudonymization, and reconstruction on DOCX documents.
"""

import argparse
import sys
import os
import time

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.pipeline import PiiRedactionPipeline


def main():
    parser = argparse.ArgumentParser(description="Production PII Redaction CLI")
    parser.add_argument("--input", "-i", type=str, default="Red Herring Prospectus.docx", help="Input DOCX path")
    parser.add_argument("--output", "-o", type=str, default="artifacts/output_docs/Redacted_Red_Herring_Prospectus.docx", help="Output DOCX path")
    parser.add_argument("--model-path", type=str, default="models/gliner_multi_pii", help="Local GLiNER model path")
    parser.add_argument("--no-images", action="store_true", help="Disable image redaction path")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.")
        sys.exit(1)

    print("==================================================")
    print("PII REDACTION PIPELINE: STARTING RUN")
    print(f"Input Document : {args.input}")
    print(f"Target Output  : {args.output}")
    print(f"Neural Model   : {args.model_path}")
    print("==================================================")

    start_time = time.time()
    pipeline = PiiRedactionPipeline(
        enable_neural=True,
        enable_context=True,
        enable_registry=True,
        enable_images=not args.no_images,
        model_path=args.model_path
    )

    summary = pipeline.process_document(args.input, args.output)
    elapsed = time.time() - start_time

    print("\n==================================================")
    print("PII REDACTION COMPLETE")
    print(f"Time Taken            : {elapsed:.2f} seconds")
    print(f"Blocks Processed      : {summary['total_blocks_processed']}")
    print(f"Total PII Detected    : {summary['total_pii_detected']}")
    print("PII Breakdown by Type :")
    for p_type, count in sorted(summary["pii_by_type"].items()):
        print(f"  - {p_type:<15}: {count}")
    print(f"Redacted File Saved To: {summary['output_file']}")
    print("==================================================")


if __name__ == "__main__":
    main()

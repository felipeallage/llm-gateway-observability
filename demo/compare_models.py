"""Run the same prompt across multiple models and log cost/latency/tokens.

Cost-gating by design: this script ALWAYS prints an estimate of max USD
exposure before making any call, and refuses to call the gateway unless
--yes is passed. This mirrors the AIsa quickstart's own rule: a paid call
must never be made just to "check" something without explicit approval.

Usage:
    python demo/compare_models.py --prompt "Explain CAP theorem in 2 lines" \
        --models gpt-5-nano deepseek-v4-flash gemini-3.5-flash --max-tokens 200

    (add --yes only after reviewing the printed cost estimate)
"""
import argparse
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

import aisa_client  # noqa: E402


def estimate_max_cost(model: str, prompt_tokens_guess: int, max_tokens: int) -> tuple[float | None, str]:
    return aisa_client.estimate_cost_usd(model, prompt_tokens_guess, max_tokens)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prompt", required=True, help="Prompt to send to every model")
    parser.add_argument("--models", nargs="+", required=True, help="Model IDs to compare (see /v1/models)")
    parser.add_argument("--max-tokens", type=int, default=300, help="max_tokens per call (used for the cost ceiling estimate)")
    parser.add_argument("--run-tag", default="comparison", help="Label to group these calls in the dashboard")
    parser.add_argument("--yes", action="store_true", help="Actually execute the calls (omit to only print the cost estimate)")
    args = parser.parse_args()

    # Rough prompt-token guess for the pre-flight estimate: ~4 chars/token, +20% safety margin.
    prompt_tokens_guess = int(len(args.prompt) / 4 * 1.2) + 1

    print(f"Prompt: {args.prompt!r}")
    print(f"Models: {args.models}")
    print(f"Estimated prompt tokens: ~{prompt_tokens_guess}, max_tokens ceiling: {args.max_tokens}\n")

    print(f"{'model':40s} {'max_cost_usd':>14s}  status")
    total_known = 0.0
    any_unknown = False
    for model in args.models:
        cost, status = estimate_max_cost(model, prompt_tokens_guess, args.max_tokens)
        if status == "known":
            total_known += cost
            print(f"{model:40s} {cost:>14.6f}  known (worst case, assumes full max_tokens used)")
        else:
            any_unknown = True
            print(f"{model:40s} {'?':>14s}  UNKNOWN PRICE - not in pricing.json or unverified")

    print(f"\nTotal estimated max exposure (known-price models only): ${total_known:.6f} USD")
    if any_unknown:
        print("WARNING: one or more models have unknown/unverified pricing. Actual cost for those calls")
        print("will be logged as cost_status='unknown_price' — check aisa.one's live dashboard for real pricing")
        print("before running at scale.")

    if not args.yes:
        print("\nDry run only (no calls made). Re-run with --yes to execute after reviewing the estimate above.")
        return

    print("\nExecuting...\n")
    for model in args.models:
        try:
            resp = aisa_client.chat_completion(
                model=model,
                messages=[{"role": "user", "content": args.prompt}],
                max_tokens=args.max_tokens,
                run_tag=args.run_tag,
            )
            usage = resp.get("usage", {})
            content = resp["choices"][0]["message"]["content"]
            print(f"[{model}] tokens={usage} \n{content}\n{'-'*60}")
        except Exception as e:
            print(f"[{model}] ERROR: {e}\n{'-'*60}")

    print("Done. Run `streamlit run dashboard/app.py` to see the results.")


if __name__ == "__main__":
    main()

"""Look up Azure OpenAI / Foundry token prices via the public Azure Retail Prices API.

    uv run python scripts/llm_prices.py                      # gpt-5-mini, Global Standard
    uv run python scripts/llm_prices.py --model gpt-5-nano
    uv run python scripts/llm_prices.py --all                # every meter, all regions

No login needed: https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices
Prints every matching meter and proposes LLM_PRICE_INPUT_PER_MTOK / LLM_PRICE_OUTPUT_PER_MTOK.
The proposal picks the pay-as-you-go *global* input and output meters (not cached, not batch,
not data zone / regional). Check the printed table before you paste anything.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

API = "https://prices.azure.com/api/retail/prices"


def fetch(model: str) -> list[dict]:
    flt = f"serviceName eq 'Azure OpenAI' and contains(meterName, '{model}')"
    url = f"{API}?{urllib.parse.urlencode({'api-version': '2023-01-01-preview', '$filter': flt})}"
    items: list[dict] = []
    while url:
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 - fixed https host
            data = json.load(resp)
        items += data.get("Items", [])
        url = data.get("NextPageLink")
    return items


def per_mtok(item: dict) -> float | None:
    """Normalize the retail price to USD per 1 million tokens."""
    unit = item["unitOfMeasure"].replace(" ", "").upper()
    price = float(item["retailPrice"])
    if unit.startswith("1M"):
        return price
    if unit.startswith("1K"):
        return price * 1000
    if unit.startswith("1000"):
        return price * 1000
    return None


def classify(name: str) -> str:
    n = name.lower()
    if "cached" in n or "cache" in n:
        return "cached-input"
    if "batch" in n:
        return "batch"
    if "inp" in n or "input" in n:
        return "input"
    if "outp" in n or "output" in n:
        return "output"
    return "other"


def scope(name: str) -> str:
    n = name.lower()
    if "glbl" in n or "global" in n:
        return "global"
    if "data zone" in n or "dz" in n.split():
        return "data-zone"
    return "regional/other"


def main() -> int:
    parser = argparse.ArgumentParser(description="Azure OpenAI token prices from the Retail Prices API")
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--region", default="eastus", help="ARM region to show (prices for global meters are the same everywhere)")
    parser.add_argument("--all", action="store_true", help="show every region and meter type")
    args = parser.parse_args()

    try:
        items = fetch(args.model)
    except Exception as error:  # noqa: BLE001
        print(f"Could not reach {API}: {error}", file=sys.stderr)
        return 1
    if not items:
        print(f"No meters found containing '{args.model}'. Try a different spelling (e.g. 'gpt 5 mini').")
        return 1

    rows = []
    for it in items:
        if it.get("type") not in (None, "Consumption"):
            continue
        if not args.all and it["armRegionName"] != args.region:
            continue
        rows.append(it)
    if not rows:  # region filter too strict: fall back to everything
        rows = items

    print(f"{'meter':60s} {'unit':12s} {'price':>10s} {'per 1M':>10s} {'kind':13s} {'scope':14s} region")
    seen = set()
    for it in sorted(rows, key=lambda i: (i["meterName"], i["armRegionName"])):
        key = (it["meterName"], it["armRegionName"], it["retailPrice"])
        if key in seen:
            continue
        seen.add(key)
        pm = per_mtok(it)
        print(f"{it['meterName']:60s} {it['unitOfMeasure']:12s} {it['retailPrice']:>10} "
              f"{'-' if pm is None else f'{pm:.4f}':>10s} {classify(it['meterName']):13s} {scope(it['meterName']):14s} {it['armRegionName']}")

    def pick(kind: str) -> float | None:
        cands = [per_mtok(i) for i in rows if classify(i["meterName"]) == kind and scope(i["meterName"]) == "global"]
        cands = [c for c in cands if c is not None]
        return min(cands) if cands else None

    inp, outp = pick("input"), pick("output")
    print()
    if inp is None or outp is None:
        print("Could not identify global input/output meters automatically; pick them from the table above.")
        return 0
    print("Proposed for .env (Global Standard, pay-as-you-go, USD per 1M tokens):")
    print(f"LLM_PRICE_INPUT_PER_MTOK={inp:g}")
    print(f"LLM_PRICE_OUTPUT_PER_MTOK={outp:g}")
    print("Check the 'kind' and 'scope' columns: use the data-zone meters instead if your deployment is Data Zone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

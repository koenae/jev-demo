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

# The API's `contains` is case-sensitive and the service/product naming for Foundry has moved
# around, so we pull a few broad slices and match the model name locally, case-insensitively.
FILTERS = [
    "contains(productName, 'OpenAI')",
    "contains(productName, 'Foundry')",
    "contains(productName, 'Azure AI')",
    "serviceName eq 'Azure OpenAI'",
    "serviceName eq 'Cognitive Services'",
]


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "jev-demo/llm_prices"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed https host
        return json.load(resp)


def fetch_filter(flt: str, quiet: bool = False) -> list[dict]:
    url = f"{API}?{urllib.parse.urlencode({'api-version': '2023-01-01-preview', '$filter': flt})}"
    items: list[dict] = []
    page = 0
    while url:
        data = _get(url)
        items += data.get("Items", [])
        url = data.get("NextPageLink")
        page += 1
        if not quiet:
            print(f"  {flt}: page {page}, {len(items)} items so far", end="\r", file=sys.stderr)
    if not quiet:
        print(file=sys.stderr)
    return items


def norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def matches(item: dict, model: str) -> bool:
    m = norm(model)
    return any(m in norm(item.get(k, "")) for k in ("meterName", "skuName", "productName"))


def fetch(model: str, dump: str | None = None) -> list[dict]:
    seen: set[str] = set()
    items: list[dict] = []
    for flt in FILTERS:
        try:
            for it in fetch_filter(flt):
                key = it.get("meterId", "") + it.get("armRegionName", "") + str(it.get("retailPrice"))
                if key not in seen:
                    seen.add(key)
                    items.append(it)
        except Exception as error:  # noqa: BLE001
            print(f"  filter {flt!r} failed: {error}", file=sys.stderr)
        if any(matches(it, model) for it in items):
            break  # found the model in this slice; no need to pull the rest
    if dump:
        with open(dump, "w", encoding="utf-8") as fh:
            json.dump(items, fh, indent=1)
        print(f"raw items written to {dump} ({len(items)})", file=sys.stderr)
    return [it for it in items if matches(it, model)]


def discover() -> None:
    """Print the distinct service/product names that mention OpenAI or Foundry (first slices only)."""
    names: dict[tuple[str, str], int] = {}
    for flt in FILTERS[:3]:
        try:
            for it in fetch_filter(flt):
                names[(it.get("serviceName", ""), it.get("productName", ""))] = names.get((it.get("serviceName", ""), it.get("productName", "")), 0) + 1
        except Exception as error:  # noqa: BLE001
            print(f"  filter {flt!r} failed: {error}", file=sys.stderr)
    for (svc, prod), n in sorted(names.items()):
        print(f"{n:6d}  serviceName={svc!r:40s} productName={prod!r}")


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
    """Meter names look like 'GPT 5 Mini cchd Inpt Glbl 1M Tokens' or 'GPT 5 Mini Batch outpt DZone 1M Tokens'."""
    n = name.lower()
    if "batch" in n:
        return "batch"
    if "cchd" in n or "cached" in n or "cache" in n:
        return "cached-input"
    if "inp" in n or "input" in n:
        return "input"
    if "outp" in n or "output" in n:
        return "output"
    return "other"


def scope(name: str) -> str:
    n = name.lower()
    if "glbl" in n or "global" in n:
        return "global"
    if "dzone" in n or "data zone" in n or "dz" in n.split():
        return "data-zone"
    return "regional/other"


def main() -> int:
    parser = argparse.ArgumentParser(description="Azure OpenAI token prices from the Retail Prices API")
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--region", default="eastus", help="ARM region to show (prices for global meters are the same everywhere)")
    parser.add_argument("--all", action="store_true", help="show every region and meter type")
    parser.add_argument("--discover", action="store_true", help="list service/product names that mention OpenAI or Foundry")
    parser.add_argument("--dump", metavar="FILE", help="write all fetched raw items to a JSON file")
    args = parser.parse_args()

    if args.discover:
        discover()
        return 0
    try:
        items = fetch(args.model, dump=args.dump)
    except Exception as error:  # noqa: BLE001
        print(f"Could not reach {API}: {error}", file=sys.stderr)
        return 1
    if not items:
        print(f"No meters matched '{args.model}'. Run with --discover to see the service/product names, "
              "or --dump prices_raw.json and search that file.")
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
        cands = {per_mtok(i) for i in rows if classify(i["meterName"]) == kind and scope(i["meterName"]) == "global"}
        cands.discard(None)
        if len(cands) > 1:
            print(f"warning: several global {kind} meters ({sorted(cands)}); taking the highest, check the table", file=sys.stderr)
        return max(cands) if cands else None  # type: ignore[type-var]

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

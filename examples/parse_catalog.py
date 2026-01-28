#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from textwrap import shorten


def load_catalog(path: str) -> dict:
    raw = Path(path).read_text(encoding="utf-8")
    return json.loads(raw)


def dataset_summary(dataset: dict, max_description: int) -> tuple:
    title = dataset.get("title", "Untitled")
    identifier = dataset.get("identifier", "")
    description = dataset.get("description", "")
    if description and max_description > 0:
        description = shorten(description, width=max_description, placeholder="...")

    distributions = dataset.get("distribution", [])
    urls = []
    for dist in distributions:
        url = dist.get("accessURL") or dist.get("downloadURL")
        if url:
            urls.append(url)

    return title, identifier, description, urls


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize datasets in a Project Open Data catalog."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="data/usaspending_catalog.json",
        help="Path to catalog JSON (default: data/usaspending_catalog.json)",
    )
    parser.add_argument(
        "--max-description",
        type=int,
        default=140,
        help="Max description length (default: 140)",
    )
    args = parser.parse_args()

    catalog = load_catalog(args.path)
    datasets = catalog.get("dataset", [])
    print(f"Datasets: {len(datasets)}")

    for dataset in datasets:
        title, identifier, description, urls = dataset_summary(
            dataset, args.max_description
        )
        print(f"\n{title}")
        if identifier:
            print(f"  Identifier: {identifier}")
        if description:
            print(f"  Description: {description}")
        if urls:
            print("  Access URLs:")
            for url in urls:
                print(f"    - {url}")


if __name__ == "__main__":
    main()

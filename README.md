# Green-Subsidies-Research

## Using the USAspending catalog JSON

The JSON you shared is a Project Open Data (DCAT-US) catalog. It is metadata
that describes datasets and their download or API access URLs. Your project can
use it to discover dataset titles, descriptions, and the `accessURL` or
`downloadURL` values needed to fetch data.

### Quick start

1. Save the JSON to `data/usaspending_catalog.json`.
2. Run the helper script to list datasets and access URLs:

```
python3 examples/parse_catalog.py data/usaspending_catalog.json
```

3. Use the printed URLs to download data or call the API. Example:

```
curl -s https://api.usaspending.gov/api/v2/awards/last_updated/
```

### What to look for in the catalog

- `dataset`: an array of dataset objects.
- `title` and `description`: human-readable metadata.
- `distribution`: one or more access points for the data.
- `distribution[].accessURL` or `distribution[].downloadURL`: endpoints to call.

### Programmatic use (Python)

If you want to integrate it directly:

```python
import json
from pathlib import Path

catalog = json.loads(Path("data/usaspending_catalog.json").read_text())
for dataset in catalog.get("dataset", []):
    print(dataset.get("title"), dataset.get("identifier"))
```
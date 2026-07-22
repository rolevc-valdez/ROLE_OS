# ROLE OS

ROLE OS turns a ChatGPT conversations export into a structured, searchable
personal knowledge base, and serves it through a small read-only API.

## Repository layout

```
ROLE_OS/
  builder/      # CLI tool: builds the ROLE Knowledge OS + SQLite DB from a ChatGPT export
  dashboard/    # FastAPI app: read-only API over the generated SQLite database
  docs/         # Project documentation
  tests/        # Repo-level / integration tests
  scripts/      # Utility and automation scripts
  samples/      # Sample ChatGPT export + generated output for local testing
```

## Quick start

1. **Build the knowledge base** from a ChatGPT export:

   ```bash
   cd builder
   python builder.py "<chatgpt_export.zip>" "<output_dir>" --clean
   ```

   See [`builder/README.md`](builder/README.md) for details.

2. **Serve it** with the dashboard API:

   ```bash
   cd dashboard
   pip install -r requirements.txt
   export ROLE_OS_DB_PATH="<output_dir>/00_SYSTEM/role_os.db"
   uvicorn app.main:app --reload
   ```

   See [`dashboard/README.md`](dashboard/README.md) for endpoint details.

## Status

This repository currently implements data extraction (`builder`) and a plain
data-access API (`dashboard`). No AI/LLM features are implemented yet — the
dashboard only reads and serves data that the builder already extracted with
rule-based classification.

## Development

Run the full test suite from the repo root:

```bash
pip install -r dashboard/requirements.txt pytest
python -m pytest
```

See [`CHANGELOG.md`](CHANGELOG.md) for release history.

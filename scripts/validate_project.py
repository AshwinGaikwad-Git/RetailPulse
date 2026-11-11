"""Re-run the original pipeline, execute the preserved notebook, and verify extensions."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "pip", "check"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "src/data_cleaning.py"], cwd=ROOT, check=True)
    print("Original pipeline passed; executing notebook…", flush=True)
    path = ROOT / "notebooks" / "online_retail_analysis.ipynb"
    notebook = nbformat.read(path, as_version=4)
    def progress(cell, cell_index, **kwargs):
        if cell.cell_type == "code":
            print(f"Notebook code cell {cell_index} complete", flush=True)
    NotebookClient(notebook, timeout=600, kernel_name="python3",
                   resources={"metadata": {"path": str(ROOT)}}, on_cell_executed=progress).execute()
    nbformat.validate(notebook)
    nbformat.write(notebook, path)
    print("Notebook passed; exporting extended reports…", flush=True)
    from src.reporting import export_reports, load_analysis
    result = export_reports(load_analysis())
    print(json.dumps(result, indent=2), flush=True)
    subprocess.run([sys.executable, "scripts/verify_results.py"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()

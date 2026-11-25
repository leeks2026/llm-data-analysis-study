"""Execute only the second-stage notebook and persist its actual outputs."""
from pathlib import Path
import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "notebooks" / "02_중간분석.ipynb"
notebook = nbformat.read(path, as_version=4)
NotebookClient(notebook, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}).execute()
nbformat.write(notebook, path)
print("Executed", path.name)

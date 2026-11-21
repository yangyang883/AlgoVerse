"""Run after owner approval and `gh auth login`; creates labels and five role issues."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
labels = ["P0", "P1", "frontend", "backend", "ai-nlp", "algorithm", "evaluation", "bug", "integration"]
issue_labels = {
    "01-ai-nlp.md": "P0,ai-nlp",
    "02-algorithm.md": "P0,algorithm",
    "03-backend.md": "P0,backend,integration",
    "04-frontend.md": "P0,frontend",
    "05-evaluation.md": "P0,evaluation",
}

for label in labels:
    subprocess.run(["gh", "label", "create", label, "--force"], cwd=root, check=True)
for filename, assigned_labels in issue_labels.items():
    path = root / ".github" / "issues" / filename
    title = path.read_text(encoding="utf-8").splitlines()[0].removeprefix("# ")
    subprocess.run(["gh", "issue", "create", "--title", title, "--body-file", str(path),
                    "--label", assigned_labels], cwd=root, check=True)

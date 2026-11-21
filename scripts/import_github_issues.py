"""Import role issues and labels with the current Git credential; safe to rerun."""
import json
import re
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
remote = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=root, text=True).strip()
match = re.fullmatch(r"https://github\.com/([^/]+)/([^/]+)\.git", remote)
if not match:
    raise SystemExit("Expected a GitHub HTTPS origin ending in .git")
owner, repo = match.groups()
credential = subprocess.check_output(
    ["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
    cwd=root, text=True,
)
token = next((line[9:] for line in credential.splitlines() if line.startswith("password=")), None)
if not token:
    raise SystemExit("No GitHub credential available")
base = f"https://api.github.com/repos/{owner}/{repo}"


def api(method, path, payload=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = Request(base + path, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "AlgoVerse-issue-import",
    })
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        raise SystemExit(f"GitHub API {method} {path} failed: HTTP {error.code}") from None


labels = ["P0", "P1", "frontend", "backend", "ai-nlp", "algorithm", "evaluation", "bug", "integration"]
issue_labels = {
    "01-ai-nlp.md": ["P0", "ai-nlp"],
    "02-algorithm.md": ["P0", "algorithm"],
    "03-backend.md": ["P0", "backend", "integration"],
    "04-frontend.md": ["P0", "frontend"],
    "05-evaluation.md": ["P0", "evaluation"],
}

existing_labels = {item["name"] for item in api("GET", "/labels?per_page=100")}
for name in labels:
    if name not in existing_labels:
        api("POST", "/labels", {"name": name})
        print("Created label:", name)

existing_titles = {item["title"] for item in api("GET", "/issues?state=all&per_page=100")
                   if "pull_request" not in item}
for filename, assigned_labels in issue_labels.items():
    body = (root / ".github" / "issues" / filename).read_text(encoding="utf-8")
    title = body.splitlines()[0].removeprefix("# ")
    if title not in existing_titles:
        created = api("POST", "/issues", {"title": title, "body": body, "labels": assigned_labels})
        print("Created issue:", created["number"], title)

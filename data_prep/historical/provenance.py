"""provenance.json for a processed folder: which raw files (with checksums and source URLs), which code and
which settings produced the processed tables, and the checksums of the tables themselves."""
import datetime
import json
import subprocess
from pathlib import Path

from data_prep.historical import config, http_get


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=config.REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()


def settings() -> dict:
    """All upper-case constants of config.py, paths as strings."""
    out = {}
    for name in sorted(n for n in dir(config) if n.isupper()):
        value = getattr(config, name)
        out[name] = str(value) if isinstance(value, Path) else value
    return json.loads(json.dumps(out, default=str))


def raw_files(manifest: dict) -> dict:
    """Every file under the raw folder with its checksum; source metadata from the download manifest.
    Files not in the manifest (e.g. hand-copied ENTSO-E web tables) are marked as such."""
    out = {}
    for path in sorted(p for p in config.RAW_DIR.rglob("*") if p.is_file() and not p.name.endswith(".part")):
        key = path.relative_to(config.RAW_DIR).as_posix()
        entry = manifest.get(key)
        digest = http_get.sha256(path)
        if entry is not None and entry["sha256"] != digest:
            raise RuntimeError(f"raw/{key} differs from its manifest checksum; re-download it before processing")
        out[key] = {"sha256": digest, "bytes": path.stat().st_size,
                    **({k: entry.get(k) for k in ("url", "retrieved_at_utc", "last_modified")} if entry
                       else {"source": "not downloaded by download.py (not in raw_manifest.json)"})}
    return out


def write(out_dir: Path, period: dict) -> Path:
    code_dir = Path(__file__).resolve().parent
    record = {
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "period": period,
        "code": {"git_commit": git("rev-parse", "HEAD"),
                 "uncommitted_changes_in_data_prep_historical": bool(git("status", "--porcelain", "--", str(code_dir))),
                 "files_sha256": {p.name: http_get.sha256(p) for p in sorted(code_dir.glob("*.py"))}},
        "settings": settings(),
        "raw_files": raw_files(http_get.load_manifest()),
        "outputs_sha256": {p.name: http_get.sha256(p) for p in sorted(out_dir.glob("*.csv"))},
    }
    target = out_dir / "provenance.json"
    target.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    return target

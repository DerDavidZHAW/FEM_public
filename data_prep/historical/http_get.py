"""Polite HTTP GET for the downloaders (stdlib only, no `requests` dependency), with a download manifest.

Every file saved by `download` is recorded in `input/historical/raw_manifest.json` (outside the gitignored
raw folder, so it can be committed): source URL (credentials removed), retrieval time, HTTP Last-Modified,
ETag and content type, size and SHA-256. A file already on disk is reused only if it still matches its
manifest entry and was fetched from the same URL; otherwise the run stops and asks for --force.
"""
import datetime
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from data_prep.historical.config import RAW_DIR, REPO_ROOT, USER_AGENT

MAX_ATTEMPTS = 5
MANIFEST = RAW_DIR.parent / "raw_manifest.json"
SECRET_PARAMS = {"securityToken"}  # ENTSO-E API token
_last_request_at: dict[str, float] = {}


def redact(url: str) -> str:
    """URL with the values of credential parameters replaced, safe to store; other URLs unchanged."""
    parts = urllib.parse.urlsplit(url)
    if not SECRET_PARAMS & {k for k, _ in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)}:
        return url
    query = [(k, "REDACTED" if k in SECRET_PARAMS else v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query, safe=":/,")))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_key(dest: Path) -> str:
    return dest.resolve().relative_to(RAW_DIR.resolve()).as_posix()


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}


def save_manifest(manifest: dict) -> None:
    """Write atomically. On Windows the replace fails while another process (virus scanner, editor) holds
    the target open; retry briefly, then raise."""
    tmp = MANIFEST.with_suffix(".json.part")
    tmp.write_text(json.dumps(dict(sorted(manifest.items())), indent=1, ensure_ascii=False), encoding="utf-8")
    for attempt in range(1, 11):
        try:
            tmp.replace(MANIFEST)
            return
        except PermissionError:
            if attempt == 10:
                raise
            time.sleep(0.2 * attempt)


def get_bytes(url: str, headers: dict | None = None, min_interval_s: float = 0.0, host_key: str = "") -> tuple[bytes, dict]:
    """GET url; return the body and HTTP metadata. Waits min_interval_s since the last call with the same
    host_key. HTTP 429 and 5xx are retried (honouring Retry-After) up to MAX_ATTEMPTS, then raised.
    Any other HTTP error is raised at once."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    attempt = 0
    while True:
        attempt += 1
        wait = _last_request_at.get(host_key, 0.0) + min_interval_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request_at[host_key] = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                meta = {"http_status": response.status, "content_type": response.headers.get("Content-Type"),
                        "last_modified": response.headers.get("Last-Modified"), "etag": response.headers.get("ETag")}
                return response.read(), meta
        except urllib.error.HTTPError as err:
            if not (err.code == 429 or err.code >= 500) or attempt == MAX_ATTEMPTS:
                body = err.read()[:500].decode("utf-8", "replace")
                raise RuntimeError(f"GET {redact(url)} failed with HTTP {err.code}: {body}") from err
            retry_after = err.headers.get("Retry-After")
            pause = float(retry_after) if retry_after and retry_after.isdigit() else 60.0
            print(f"  HTTP {err.code}, retrying in {pause:.0f} s (attempt {attempt}/{MAX_ATTEMPTS})")
            time.sleep(pause)


def download(url: str, dest: Path, force: bool, **kwargs) -> Path:
    """Save url to dest and record it in the manifest. An existing dest is kept unless force is set.

    Raises if a kept file no longer matches its manifest checksum, or was fetched from another URL.
    A file that predates the manifest is entered with an unknown retrieval time (its mtime is noted).
    """
    shown = dest.relative_to(REPO_ROOT) if dest.is_relative_to(REPO_ROOT) else dest
    key, clean_url = manifest_key(dest), redact(url)
    manifest = load_manifest()
    if dest.exists() and not force:
        entry = manifest.get(key)
        digest = sha256(dest)
        if entry is None:
            mtime = datetime.datetime.fromtimestamp(dest.stat().st_mtime, datetime.timezone.utc)
            manifest[key] = {"url": clean_url, "retrieved_at_utc": None, "bytes": dest.stat().st_size, "sha256": digest,
                             "note": f"downloaded before the manifest existed; retrieval time unknown, "
                                     f"file modified {mtime.isoformat(timespec='seconds')}"}
            save_manifest(manifest)
        elif entry["sha256"] != digest:
            raise RuntimeError(f"{shown} changed since it was downloaded (SHA-256 differs from {MANIFEST.name}); "
                               "re-download with --force")
        elif entry["url"] != clean_url:
            raise RuntimeError(f"{shown} was downloaded from {entry['url']}, the code now asks for {clean_url}; "
                               "re-download with --force")
        print(f"  exists, skipped: {shown}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    body, meta = get_bytes(url, **kwargs)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(dest)
    manifest = load_manifest()  # re-read: another download may have written meanwhile
    manifest[key] = {"url": clean_url,
                     "retrieved_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                     "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), **meta}
    save_manifest(manifest)
    print(f"  downloaded {len(body) / 1e6:.2f} MB -> {shown}")
    return dest

from __future__ import annotations

import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote

from i18n import t


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = _app_dir()
FOLLOWING_FILENAME = "following.json"

_IG_HREF = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:_u/)?([A-Za-z0-9._]+)",
    re.IGNORECASE,
)
_USERNAME = re.compile(r"^[A-Za-z0-9._]{1,30}$")
_SKIP_PATHS = {
    "about",
    "accounts",
    "direct",
    "emails",
    "explore",
    "legal",
    "p",
    "reel",
    "reels",
    "stories",
}


class CompareError(Exception):
    pass


@dataclass
class ParsedList:
    names: dict[str, str] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    skipped: int = 0


@dataclass
class CompareResult:
    following: dict[str, str]
    followers: dict[str, str]
    not_following_back: list[str]
    you_dont_follow: list[str]
    mutual_count: int
    follower_files: list[str]
    following_file: str
    skipped_followers: int
    skipped_following: int


def classify_name(name: str) -> str | None:
    base = Path(name).name.lower()
    if base.endswith(".zip"):
        return "zip"
    if base.startswith("followers"):
        return "followers"
    if base.startswith("following"):
        return "following"
    return None


def _username_from_entry(entry: object) -> str | None:
    if not isinstance(entry, dict):
        return None

    title = entry.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()

    data = entry.get("string_list_data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            value = first.get("value")
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def _entries_from_payload(payload: object) -> list[object] | None:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None

    for key in ("relationships_following", "relationships_followers"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    for value in payload.values():
        if (
            isinstance(value, list)
            and value
            and isinstance(value[0], dict)
        ):
            return value

    return None


def parse_usernames(payload: object) -> tuple[dict[str, str], int]:
    entries = _entries_from_payload(payload)
    if entries is None:
        raise CompareError(t("err_bad_json_format"))

    names: dict[str, str] = {}
    skipped = 0
    for entry in entries:
        username = _username_from_entry(entry)
        if not username:
            skipped += 1
            continue
        names.setdefault(username.casefold(), username)
    return names, skipped


def parse_html(text: str) -> tuple[dict[str, str], int]:
    names: dict[str, str] = {}
    for match in _IG_HREF.finditer(text):
        username = unquote(match.group(1)).strip()
        if username.casefold() in _SKIP_PATHS or not _USERNAME.fullmatch(username):
            continue
        names.setdefault(username.casefold(), username)
    return names, 0


def _decode(data: bytes) -> str:
    return data.decode("utf-8-sig")


def parse_bytes(filename: str, data: bytes) -> tuple[dict[str, str], int]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        try:
            payload = json.loads(_decode(data))
        except json.JSONDecodeError as exc:
            raise CompareError(t("err_invalid_json", name=filename, detail=exc.msg)) from exc
        return parse_usernames(payload)
    if suffix in {".html", ".htm"}:
        return parse_html(_decode(data))
    raise CompareError(t("err_unsupported", name=filename))


def load_username_file(path: Path) -> tuple[dict[str, str], int]:
    try:
        data = path.read_bytes()
    except FileNotFoundError as exc:
        raise CompareError(t("err_not_found", name=path.name)) from exc
    except OSError as exc:
        raise CompareError(t("err_cannot_read", name=path.name, detail=exc)) from exc
    return parse_bytes(path.name, data)


def _add(target: ParsedList, names: dict[str, str], skipped: int, label: str) -> None:
    target.names.update(names)
    target.skipped += skipped
    target.files.append(f"{label} ({len(names)})")


def zip_has_export(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return any(
                classify_name(member) in {"followers", "following"}
                for member in archive.namelist()
            )
    except (OSError, zipfile.BadZipFile):
        return False


def ingest_zip(path: Path, followers: ParsedList, following: ParsedList) -> None:
    try:
        archive = zipfile.ZipFile(path)
    except FileNotFoundError as exc:
        raise CompareError(t("err_not_found", name=path.name)) from exc
    except zipfile.BadZipFile as exc:
        raise CompareError(t("err_bad_zip", name=path.name)) from exc
    except OSError as exc:
        raise CompareError(t("err_cannot_read", name=path.name, detail=exc)) from exc

    found = False
    with archive:
        for member in archive.namelist():
            role = classify_name(member)
            if role not in {"followers", "following"}:
                continue
            found = True
            names, skipped = parse_bytes(Path(member).name, archive.read(member))
            label = f"{path.name}/{Path(member).name}"
            _add(followers if role == "followers" else following, names, skipped, label)

    if not found:
        raise CompareError(t("err_zip_empty", name=path.name))


def ingest_path(path: Path, followers: ParsedList, following: ParsedList) -> None:
    path = Path(path)
    role = classify_name(path.name)
    if role == "zip":
        ingest_zip(path, followers, following)
        return
    if role not in {"followers", "following"}:
        raise CompareError(t("err_unrecognized_file", name=path.name))
    names, skipped = load_username_file(path)
    _add(followers if role == "followers" else following, names, skipped, path.name)


def discover_sources(base: Path | None = None) -> list[Path]:
    folder = base or APP_DIR
    found: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen or not path.is_file():
            return
        seen.add(resolved)
        found.append(path)

    for zip_path in sorted(folder.glob("*.zip")):
        if zip_has_export(zip_path):
            add(zip_path)
    for path in sorted(folder.glob("followers*.json")) + sorted(folder.glob("followers*.html")):
        add(path)
    for name in ("following.json", "following.html"):
        add(folder / name)
    return found


def _sorted_display(keys: Iterable[str], source: dict[str, str]) -> list[str]:
    return [source[key] for key in sorted(keys, key=str.casefold)]


def compare_lists(followers: ParsedList, following: ParsedList) -> CompareResult:
    follower_keys = set(followers.names)
    following_keys = set(following.names)
    return CompareResult(
        following=following.names,
        followers=followers.names,
        not_following_back=_sorted_display(
            following_keys - follower_keys, following.names
        ),
        you_dont_follow=_sorted_display(
            follower_keys - following_keys, followers.names
        ),
        mutual_count=len(follower_keys & following_keys),
        follower_files=followers.files,
        following_file=", ".join(following.files) if following.files else FOLLOWING_FILENAME,
        skipped_followers=followers.skipped,
        skipped_following=following.skipped,
    )


def analyze(paths: Iterable[Path] | None = None) -> CompareResult:
    sources = [Path(path) for path in paths] if paths is not None else discover_sources()
    if not sources:
        raise CompareError(t("err_no_export"))

    followers = ParsedList()
    following = ParsedList()
    for path in sources:
        ingest_path(path, followers, following)

    if not followers.names:
        raise CompareError(t("err_no_followers"))
    if not following.names:
        raise CompareError(t("err_no_following"))
    return compare_lists(followers, following)


def export_usernames(path: Path, title: str, usernames: list[str]) -> None:
    lines = [
        t("export_header", title=title, count=len(usernames)),
        "=" * 55,
        "",
    ]
    lines.extend(f"{index:>4}. @{username}" for index, username in enumerate(usernames, 1))
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        raise CompareError(t("err_cannot_save", name=path.name, detail=exc)) from exc

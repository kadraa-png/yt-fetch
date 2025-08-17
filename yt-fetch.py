#!/usr/bin/env python3
import argparse
import sys
import re
from pathlib import Path
from typing import List, Optional, Any, Dict

import yt_dlp

__version__ = "1.5"

# ============== Optional Rich UI ==============
USE_RICH = False
try:
    from rich.progress import Progress, BarColumn, TimeElapsedColumn, TimeRemainingColumn, TextColumn
    from rich.table import Table
    from rich.console import Console
    USE_RICH = True
    _console = Console()
except Exception:
    _console = None
# =============================================


# ---------------- Helpers ----------------

def pick_formats(mode: str, container: str) -> str:
    """Choose formats per mode to avoid unnecessary downloads."""
    if mode == "mp3":
        # Only audio, avoids downloading video first.
        return "bestaudio/best"
    # Video path:
    if container.lower() == "mp4":
        return ("bv*[ext=mp4][vcodec~='^(av1|vp9|h264)']+ba[ext=m4a]/"
                "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bestvideo*+bestaudio/best")
    return "bestvideo*+bestaudio/best"


def build_postprocessors(mode: str, container: str, embed_metadata: bool, embed_thumbnail: bool):
    """Postprocessors depend on mode and metadata toggle."""
    pps = []
    if embed_metadata:
        pps.append({"key": "FFmpegMetadata", "add_chapters": True})
        if embed_thumbnail:
            if mode == "mp3":
                pps.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
            pps.append({"key": "EmbedThumbnail"})
    if mode == "mp3":
        pps.append({"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"})
    else:
        if container.lower() == "mp4":
            pps.append({"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"})
    return pps


def make_outtmpl(flat: bool) -> str:
    """Return a RELATIVE template. paths:{home: OUT_DIR} will place it."""
    return "%(title)s [%(id)s].%(ext)s" if flat else "%(uploader)s/%(title)s [%(id)s].%(ext)s"


def is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def to_search_expr(query: str, limit: int) -> str:
    return f"ytsearch{limit}:{query}"


def prepare_inputs(target: Optional[str], search: Optional[str], search_limit: int) -> List[str]:
    inputs = []
    if target:
        inputs.append(target if is_url(target) else to_search_expr(target, search_limit))
    if search:
        inputs.append(to_search_expr(search, search_limit))
    return inputs


def parse_bulk_file(path: Path, search_limit: int) -> List[str]:
    results = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            results.append(line if is_url(line) else to_search_expr(line, search_limit))
    return results


# -------------- State / Logger / Hooks --------------

class HookState:
    def __init__(self):
        self.total_items = 0
        self.completed_items = 0
        self.seen_403 = False
        self.ffmpeg_issue = False
        self.task_id = None
        self.progress: Optional[Progress] = None


class YDLLogger:
    def __init__(self, state: HookState, verbose: bool):
        self.state = state
        self.verbose = verbose
        self._re_403 = re.compile(r"\bHTTP(?:\s+Error)?\s*403\b", re.I)

    def debug(self, msg):
        if self.verbose:
            print(msg)

    def info(self, msg):
        if self.verbose:
            print(msg)

    def warning(self, msg):
        s = str(msg)
        if self._re_403.search(s):
            self.state.seen_403 = True
        if "ffmpeg" in s.lower() or "postprocess" in s.lower():
            self.state.ffmpeg_issue = True
        if self.verbose:
            print(msg, file=sys.stderr)

    def error(self, msg):
        s = str(msg)
        if self._re_403.search(s):
            self.state.seen_403 = True
        if "ffmpeg" in s.lower() or "postprocess" in s.lower():
            self.state.ffmpeg_issue = True
        print(msg, file=sys.stderr)


def progress_hook_factory(state: HookState):
    def hook(d: Dict[str, Any]):
        # Called frequently; count file-level completion on "finished"
        if d.get("status") == "finished":
            state.completed_items += 1
            if state.progress and state.task_id is not None:
                try:
                    state.progress.update(state.task_id, completed=state.completed_items)
                except Exception:
                    pass
    return hook


# -------------- Build yt-dlp options --------------

def get_common_opts(
    output_dir: Path,
    outtmpl: str,
    download_archive: Optional[Path],
    use_aria2c: bool,
    verbose: bool,
    write_subs: bool,
    retries: int,
    fragment_retries: int,
    sleep: float,
    sleep_max: Optional[float],
    force_ipv4: bool,
    cookies_file: Optional[str],
    cookies_from_browser: Optional[str],
    embed_metadata: bool,
    keep_video: bool,
    redownload: bool,
    state: HookState,
) -> dict:
    logger = YDLLogger(state, verbose)
    common = {
        "logger": logger,
        "progress_hooks": [progress_hook_factory(state)],
        "paths": {"home": str(output_dir)},
        "outtmpl": outtmpl,
        "ignoreerrors": True,
        # side files only if metadata is on
        "writethumbnail": bool(embed_metadata),
        "writedescription": bool(embed_metadata),
        "writeinfojson": bool(embed_metadata),
        "writesubtitles": write_subs,
        "subtitleslangs": ["all"],
        "merge_output_format": "mkv",
        "noplaylist": False,
        "embedchapters": bool(embed_metadata),
        "embedmetadata": bool(embed_metadata),
        "prefer_ffmpeg": True,
        # stability
        "retries": retries,
        "fragment_retries": fragment_retries,
        "sleep_interval": sleep,
        "max_sleep_interval": (sleep_max if sleep_max and sleep_max >= sleep else None),
        "concurrent_fragment_downloads": 2,
        "quiet": not verbose,
        "no_warnings": not verbose,
        "forceipv4": force_ipv4,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
        # overwrite behavior
        "overwrites": bool(redownload),
        "keepvideo": bool(keep_video),
    }
    if not redownload and download_archive:
        common["download_archive"] = str(download_archive)
    if use_aria2c:
        common["external_downloader"] = "aria2c"
        common["external_downloader_args"] = ["-x8", "-s8", "-k1M", "--summary-interval=0"]
    if cookies_file:
        common["cookiefile"] = cookies_file
    if cookies_from_browser:
        common["cookiesfrombrowser"] = (cookies_from_browser, None, True)
    return common


def build_opts(
    mode: str,
    container: str,
    output_dir: Path,
    outtmpl: str,
    download_archive: Optional[Path],
    use_aria2c: bool,
    verbose: bool,
    write_subs: bool,
    retries: int,
    fragment_retries: int,
    sleep: float,
    sleep_max: Optional[float],
    force_ipv4: bool,
    cookies_file: Optional[str],
    cookies_from_browser: Optional[str],
    embed_metadata: bool,
    embed_thumbnail: bool,
    keep_video: bool,
    redownload: bool,
    state: HookState,
) -> dict:
    fmt = pick_formats(mode, container)
    opts = get_common_opts(
        output_dir, outtmpl, download_archive, use_aria2c, verbose, write_subs,
        retries, fragment_retries, sleep, sleep_max, force_ipv4,
        cookies_file, cookies_from_browser, embed_metadata, keep_video, redownload, state
    )
    opts.update({
        "format": fmt,
        "postprocessors": build_postprocessors(mode, container, embed_metadata, embed_thumbnail and embed_metadata),
        # Sometimes helps with YouTube throttling
        "extractor_args": {"youtube": {"player_client": ["android"]}},
    })
    return opts


def run_ydl(inputs: List[str], ydl_opts: dict, state: HookState):
    # Optional progress UI (bulk)
    if USE_RICH and len(inputs) > 1:
        with Progress(
            TextColumn("[bold]yt-fetch[/bold]"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=False,
            disable=False
        ) as prog:
            state.progress = prog
            state.task_id = prog.add_task("bulk", total=len(inputs))
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.download(inputs)
    else:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.download(inputs)


# ----------------- Dry-run -----------------

def dry_run_list(items: List[str]):
    """
    dry-run:
    - Uses extract_flat to avoid format probing & extra requests.
    - Shows a progress bar with rich (if present).
    - Lists (title, id, uploader/channel, duration if available, URL).
    """
    results = []

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "simulate": True,
        "extract_flat": True,      # key speed-up
        "lazy_playlist": True,
        "socket_timeout": 10,
        "retries": 2,
        "fragment_retries": 1,
        "cachedir": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
    }

    total = len(items)
    processed = 0

    def _collect(info_obj):
        if not info_obj:
            return
        if "entries" in info_obj and info_obj["entries"]:
            for e in info_obj["entries"]:
                if not e:
                    continue
                results.append({
                    "title": e.get("title"),
                    "id": e.get("id"),
                    "uploader": e.get("uploader") or e.get("channel"),
                    "duration": e.get("duration"),
                    "webpage_url": e.get("webpage_url"),
                })
        else:
            results.append({
                "title": info_obj.get("title"),
                "id": info_obj.get("id"),
                "uploader": info_obj.get("uploader") or info_obj.get("channel"),
                "duration": info_obj.get("duration"),
                "webpage_url": info_obj.get("webpage_url"),
            })

    if USE_RICH:
        with Progress(
            TextColumn("[bold]yt-fetch dry-run[/bold]"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            transient=False,
        ) as prog:
            task = prog.add_task("scan", total=total)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for it in items:
                    try:
                        info = ydl.extract_info(it, download=False)
                        _collect(info)
                    except Exception:
                        results.append({
                            "title": f"[error resolving] {it}",
                            "id": "",
                            "uploader": "",
                            "duration": None,
                            "webpage_url": "",
                        })
                    processed += 1
                    prog.update(task, completed=processed)
    else:
        print(f"yt-fetch dry-run: resolving {total} item(s)...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for it in items:
                try:
                    info = ydl.extract_info(it, download=False)
                    _collect(info)
                except Exception:
                    results.append({
                        "title": f"[error resolving] {it}",
                        "id": "",
                        "uploader": "",
                        "duration": None,
                        "webpage_url": "",
                    })
                processed += 1
                print(f"  [{processed}/{total}] {it}")

    # ---- Display results ----
    if USE_RICH:
        table = Table(title="yt-fetch dry-run (no downloads)")
        table.add_column("Title")
        table.add_column("ID", style="cyan")
        table.add_column("Uploader", style="magenta")
        table.add_column("Duration (s)", style="green")
        table.add_column("URL", style="blue")
        for r in results:
            table.add_row(r["title"] or "",
                          r["id"] or "",
                          r["uploader"] or "",
                          str(r["duration"] or ""),
                          r["webpage_url"] or "")
        _console.print(table)
    else:
        print("\nyt-fetch dry-run (no downloads):")
        for r in results:
            print(f"- {r['title']} [{r['id']}] | {r['uploader']} | {r['duration']}s | {r['webpage_url']}")

    return 0


# ----------------- CLI -----------------

def main():
    p = argparse.ArgumentParser(
        prog="yt-fetch",
        description=("yt-fetch: High-quality YouTube downloader. "
                     "MP4/MP3, metadata toggle, flat folders, bulk status bar, fast dry-run (yt-dlp + ffmpeg).")
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    m = p.add_mutually_exclusive_group(required=True)
    m.add_argument("--single", "-s", help="Single URL or search query to download.")
    m.add_argument("--bulk-file", "-b", type=Path, help="Path to a txt file with URLs or search queries (one per line).")

    # search controls
    p.add_argument("--search", help="Extra search query to include (in addition to --single).")
    p.add_argument("--search-limit", type=int, default=1, help="Top N results to download for each search query (default: 1).")
    p.add_argument("--top", type=int, help="Alias for --search-limit. If both set, --top wins.")

    # modes
    p.add_argument("--mode", choices=["mp4", "mp3"], default="mp4", help="Download as MP4 video or MP3 audio (default: mp4).")
    p.add_argument("--container", choices=["mp4", "mkv"], default="mp4", help="Preferred container for video mode (default: mp4).")

    # output
    p.add_argument("--out", type=Path, default=Path("./downloads"), help="Output directory (default: ./downloads).")
    p.add_argument("--archive", type=Path, default=Path("./downloaded.txt"), help="Download archive file to avoid duplicates.")
    p.add_argument("--no-archive", action="store_true", help="Disable the download archive.")
    p.add_argument("--flat", action="store_true", help="Put all outputs directly into the output folder (no per-uploader subfolders).")

    # metadata
    p.add_argument("--no-metadata", action="store_true", help="Disable writing/embedding metadata, thumbnails, info JSON, and description.")

    # stability & extras
    p.add_argument("--aria2c", action="store_true", help="Use aria2c external downloader for speed.")
    p.add_argument("--no-aria2c", action="store_true", help="Force-disable aria2c (overrides --aria2c).")
    p.add_argument("--subs", action="store_true", help="Download and embed available subtitles.")
    p.add_argument("--verbose", action="store_true", help="Verbose output.")
    p.add_argument("--force-ipv4", action="store_true", help="Use IPv4 only (can avoid 403s on some networks).")
    p.add_argument("--cookies-file", help="Path to a cookies.txt file.")
    p.add_argument("--cookies-from-browser",
                   choices=["firefox", "chrome", "chromium", "brave", "edge", "vivaldi", "opera"],
                   help="Load cookies from the given browser profile.")
    p.add_argument("--retries", type=int, default=10, help="Number of retries on HTTP errors (default: 10).")
    p.add_argument("--fragment-retries", type=int, default=10, help="Retries per video fragment (default: 10).")
    p.add_argument("--sleep", type=float, default=1.0, help="Seconds to sleep between downloads (default: 1.0).")
    p.add_argument("--sleep-max", type=float, help="Max sleep (randomized between --sleep and --sleep-max).")
    p.add_argument("--keep-video", "-k", action="store_true", help="Keep the original video file when extracting MP3.")
    p.add_argument("--redownload", action="store_true", help="Ignore the archive and overwrite existing files; always re-download.")

    # dry-run
    p.add_argument("--dry-run", action="store_true",
                   help="Resolve inputs and list what would be downloaded (no files saved). Best with --bulk-file.")

    args = p.parse_args()

    # Resolve top/search-limit
    search_limit = args.top if args.top is not None else args.search_limit

    output_dir: Path = args.out
    output_dir.mkdir(parents=True, exist_ok=True)

    download_archive = None if (args.no_archive or args.redownload) else args.archive
    use_aria2c = args.aria2c and not args.no_aria2c

    outtmpl = make_outtmpl(flat=args.flat)
    embed_metadata = not args.no_metadata
    embed_thumbnail = True

    # Build inputs
    targets: List[str] = []
    if args.single:
        targets.extend(prepare_inputs(args.single, args.search, search_limit))
    elif args.bulk_file:
        if not args.bulk_file.exists():
            print(f"Bulk file not found: {args.bulk_file}", file=sys.stderr)
            sys.exit(2)
        targets.extend(parse_bulk_file(args.bulk_file, search_limit))

    if not targets:
        print("No valid inputs after parsing arguments.", file=sys.stderr)
        sys.exit(2)

    # Dry-run: list and exit
    if args.dry_run:
        sys.exit(dry_run_list(targets))

    # Progress/state
    state = HookState()
    state.total_items = len(targets)

    # Build options
    ydl_opts = build_opts(
        mode=args.mode,
        container=args.container,
        output_dir=output_dir,
        outtmpl=outtmpl,
        download_archive=download_archive,
        use_aria2c=use_aria2c,
        verbose=args.verbose,
        write_subs=args.subs,
        retries=args.retries,
        fragment_retries=args.fragment_retries,
        sleep=args.sleep,
        sleep_max=args.sleep_max,
        force_ipv4=args.force_ipv4,
        cookies_file=args.cookies_file,
        cookies_from_browser=args.cookies_from_browser,
        embed_metadata=embed_metadata,
        embed_thumbnail=embed_thumbnail,
        keep_video=args.keep_video,
        redownload=args.redownload,
        state=state,
    )

    code = 1  # default to failure unless set by run
    try:
        code = run_ydl(targets, ydl_opts, state)
    except Exception as e:
        msg = str(e)
        if re.search(r"(ffmpeg|postprocess|post-processing|Postprocessing)", msg, re.I):
            print("\n[yt-fetch] ffmpeg/postprocessing error detected. "
                  "Try again with --redownload (and optionally -k/--keep-video).", file=sys.stderr)
        raise
    finally:
        # notices
        if state.seen_403 and isinstance(code, int) and code > 0:
            print(
                "\n[yt-fetch] Detected HTTP 403 Forbidden on failed items.\n"
                "Tips:\n"
                "  • Disable external downloader: --no-aria2c\n"
                "  • Force IPv4: --force-ipv4\n"
                "  • Use cookies (age/region): --cookies-from-browser firefox  (or your browser)\n"
                "  • Update yt-dlp: python -m pip install -U yt-dlp\n",
                file=sys.stderr
            )
        if state.ffmpeg_issue and isinstance(code, int) and code > 0:
            print(
                "[yt-fetch] ffmpeg hinted a problem. If outputs look corrupted or missing, "
                "re-run with --redownload (and optionally -k to keep intermediates).",
                file=sys.stderr
            )

    sys.exit(code)


if __name__ == "__main__":
    main()

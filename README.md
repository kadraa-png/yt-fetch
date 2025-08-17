# yt-fetch

`yt-fetch` is a **Linux-first YouTube downloader** written in Python.  
It downloads videos or audio in the **highest quality**, supports bulk mode, flat output folders, metadata embedding (or disabling), and comes with a dry-run feature and progress bars (via [rich](https://github.com/Textualize/rich)).  
**ONLY TESTED ON ARCH LINUX, IF YOU NOTICE ANY BUGS FEEL FREE TO REPORT THEM.**

---

Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) + [ffmpeg](https://ffmpeg.org).

---

## ✨ Features

-   Download **MP4 (video)** or **MP3 (audio-only)** at the highest quality
-   Bulk downloading from URLs and search queries
-   Search queries with `--top N` to grab multiple results
-   **Dry-run mode** (`--dry-run`) to list what would be downloaded
-   **Flat output option** (`--flat`) to save everything into one folder
-   Optional **metadata embedding** (title, uploader, chapters, thumbnail)  
    or disable with `--no-metadata`
-   Archive tracking (`downloaded.txt`) to skip duplicates
-   Force re-download with `--redownload`
-   **Subtitles** download and embedding (`--subs`)
-   Nice **progress bars** with [rich] for bulk runs and dry-run
-   Compatible with Linux, macOS, and Windows

---

## 📦 Installation

### Arch Linux

```bash
sudo pacman -S python ffmpeg
pip install -U yt-dlp
# optional (for pretty progress bars)
sudo pacman -S python-rich
```

### Ubuntu / Debian

```bash
sudo apt install python3 python3-pip ffmpeg
pip install -U yt-dlp rich
```

### macOS

```bash
brew install ffmpeg yt-dlp
pip install rich
```

### Windows (PowerShell)

```powershell
pip install -U yt-dlp rich
```

---

## 🚀 Usage

### Single video by URL

```bash
python ./yt-fetch.py --single "https://www.youtube.com/watch?v=xxxxxxxxxxx"
```

### Search query (top 3 results as MP3)

```bash
python ./yt-fetch.py --single "lofi hip hop" --mode mp3 --top 3
```

### Bulk mode

`bulk.txt`:

```
https://www.youtube.com/watch?v=xxxxxxxxxxx
lofi
billie jean
```

Run:

```bash
python ./yt-fetch.py --bulk-file bulk.txt --mode mp4 --flat --out ./downloads
```

### Dry-run (no downloads, just list results)

```bash
python ./yt-fetch.py --bulk-file bulk.txt --dry-run --top 2
```

### Force re-download

```bash
python ./yt-fetch.py --bulk-file bulk.txt --redownload
```

### Download subtitles

```bash
python ./yt-fetch.py --single "i use arch btw" --subs
```

---

## ⚙️ Options

### Required (choose one)

-   `--single, -s <URL|QUERY>`  
    Download a single URL or search query.

-   `--bulk-file, -b <FILE>`  
    Path to a text file with URLs or search queries (one per line). Lines starting with `#` are ignored.

### Search control

-   `--search <QUERY>` — Add an extra search query.
-   `--search-limit <N>` — Number of results per search (default: 1).
-   `--top <N>` — Alias for `--search-limit`.

### Modes & output

-   `--mode {mp4, mp3}` — Video or audio. Default: mp4.
-   `--container {mp4, mkv}` — Preferred container. Default: mp4.
-   `--out <DIR>` — Output directory. Default: `./downloads`.
-   `--flat` — Save all outputs into one folder.

### Metadata & subtitles

-   `--no-metadata` — Disable writing/embedding metadata, thumbnails, info JSON, and description.
-   `--subs` — Download and embed available subtitles.

### Archive & re-download

-   `--archive <FILE>` — Archive file path. Default: `./downloaded.txt`.
-   `--no-archive` — Disable archive.
-   `--redownload` — Ignore archive and overwrite existing files.
-   `--keep-video, -k` — Keep original video file when extracting MP3.

### Stability & networking

-   `--aria2c` — Use aria2c external downloader.
-   `--no-aria2c` — Disable aria2c.
-   `--force-ipv4` — Use IPv4 only.
-   `--cookies-file <FILE>` — Load cookies from cookies.txt.
-   `--cookies-from-browser <BROWSER>` — Load cookies from a browser (firefox, chrome, etc.).
-   `--retries <N>` — HTTP retries (default: 10).
-   `--fragment-retries <N>` — Fragment retries (default: 10).
-   `--sleep <SECONDS>` — Sleep between downloads (default: 1.0).
-   `--sleep-max <SECONDS>` — Max sleep (randomized).

### Dry-run & debugging

-   `--dry-run` — List what would be downloaded without saving files.
-   `--verbose` — Verbose output.
-   `--version` — Show version and exit.
-   `--help` — Show help.

---

## 🛠 Error tips

-   **403 Forbidden**  
    Try:

    ```bash
    python ./yt-fetch.py --no-aria2c --force-ipv4 --cookies-from-browser firefox
    ```

-   **ffmpeg errors**  
    Re-run with:

    ```bash
    python ./yt-fetch.py --redownload -k
    ```

-   **Dry-run slow**  
    Limit search results with `--top`:
    ```bash
    python ./yt-fetch.py --bulk-file bulk.txt --dry-run --top 3
    ```

---

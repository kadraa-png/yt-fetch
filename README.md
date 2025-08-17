# yt-fetch

`yt-fetch` is a **Linux-first YouTube downloader** written in Python.  
It downloads videos or audio in the **highest quality**, supports bulk mode, flat output folders, metadata embedding (or disabling), and comes with a dry-run feature and nice progress bars (via [rich](https://github.com/Textualize/rich)).

Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) + [ffmpeg](https://ffmpeg.org).

---

## Features

-   Download **MP4 (video)** or **MP3 (audio)** at highest quality
-   Bulk mode with URLs and/or search queries
-   Search queries with `--top N` for number of results
-   Dry-run mode to **list what would be downloaded**
-   Optional **metadata embedding** (title, uploader, chapters, thumbnail)
-   Optional **flat output** (all files in one folder)
-   Archive tracking to skip duplicates
-   Force re-download (`--redownload`)
-   Progress bars with [rich] for bulk runs and dry-run
-   Subtitles download and embedding
-   Compatible with Linux, macOS, Windows

---

## Installation

### Arch Linux

```bash
sudo pacman -S python ffmpeg
pip install -U yt-dlp
# optional for nice progress bars:
sudo pacman -S python-rich
```

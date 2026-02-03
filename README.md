# WoW POV Uploader

An automated YouTube uploader for World of Warcraft POV (Point of View) videos. This script monitors a folder for new video files and automatically uploads them to YouTube with proper naming conventions.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/gandolfoni/wow-pov-uploader)

// Trying to vibecode a way to automatically upload my raid POVs captured using Warcraft Recorder to YouTube + any other easily accessible platform. The goal is to have the video files Wacraft Recorder saves locally be automatically/periodically uploaded, compressed, orgranized into easily navigable playlists.

// to do:
- [x] create github repo for project [gh repo create wow-pov-uploader --public --source=. --remote=origin --push]
- [ ] add ability to sync with Google Drive folder
- [ ] add a way to compress the videos (using ffmpeg, detailed by ai later on in this doc)
- [ ] integrate with Google Console API, install dependencies, set up credentials.json
- [ ] clean up remaining ai slop in repo after review - want to be simple & functional, try to improve/interate over time. 
- [ ] add a way to organize the videos into playlists, improve naming conventions, clean up in general


## Features

- 🎮 **Automated Upload**: Monitors a folder for new MP4 files and uploads them automatically
- 🏷️ **Smart Naming**: Automatically generates descriptive filenames with timestamps
- 📁 **Google Drive Sync**: Optional integration to sync videos to Google Drive
- 🎵 **Playlist Support**: Automatically adds videos to specified YouTube playlists
- 📊 **Progress Tracking**: Real-time upload progress and comprehensive logging
- 🔒 **Secure**: Uses OAuth2 for YouTube API authentication
- 🗜️ **Optional Compression**: ffmpeg-based compression before upload
- 🔁 **Retries + Queue**: Automatic retry/backoff and a persisted pending upload queue

## 🚀 Quick Start

**One-click deployment with GitHub Codespaces:**

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/gandolfoni/wow-pov-uploader)

1. Click the "Open in GitHub Codespaces" button above
2. Wait 2-3 minutes for the environment to set up
3. Upload your `credentials.json` file
4. Configure your watch folder path
5. Run `python youtube_uploader.py`

## Prerequisites

- Python 3.7 or higher
- Google Cloud Console project with YouTube Data API v3 enabled
- YouTube channel for uploading videos

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/wow-pov-uploader.git
cd wow-pov-uploader
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Setup

### 1. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the YouTube Data API v3
4. Create credentials (OAuth 2.0 Client ID) for a desktop application
5. Download the credentials file and save it as `credentials.json` in the project root

### 2. Configuration

Create a `config.json` in the project root (minimal example):

```json
{
  "watch_folder": "C:\\Path\\To\\WarcraftRecorder",
  "youtube_privacy": "unlisted",
  "default_description": "Raid Upload",
  "default_tags": ["World of Warcraft", "WoW", "Raid", "POV"],
  "dry_run": false,
  "youtube_playlist_id": null,
  "stable_write_checks": 3,
  "stable_write_interval_seconds": 2,
  "min_file_age_seconds": 5,
  "ignore_patterns": ["*.tmp", "*.part", "*.crdownload"],
  "ignore_extensions": [".tmp", ".part", ".crdownload"]
}
```

You can override config values on the CLI:

```bash
python youtube_uploader.py --watch-folder "C:\Path\To\WarcraftRecorder" --dry-run
```

Process existing files and exit:

```bash
python youtube_uploader.py --once
```

### 3. First Run

1. Place your `credentials.json` file in the project directory
2. Run the script:
```bash
python youtube_uploader.py
```

3. On first run, you'll be prompted to authenticate with Google
4. A browser window will open for OAuth authentication
5. After authentication, a `token.json` file will be created for future runs

## Usage

1. Start the script:
```bash
python youtube_uploader.py
```

2. The script will monitor the configured folder for new MP4 files
3. When a new video is detected:
   - File is backed up
   - Optional ffmpeg compression is applied
   - Video is uploaded to YouTube as "unlisted"
   - Video is optionally synced to Google Drive
   - Original backup is removed after successful upload
4. If an upload fails, it is placed in `pending_uploads.json` and retried on next run
5. To clear the queue manually, run:
```bash
python reset_pending_uploads.py
```

## Quick Sanity Check

1. Run `python youtube_uploader.py --once --dry-run` and confirm it exits cleanly.
2. Drop a `.tmp` file in the watch folder and confirm it is ignored.
3. Enable compression and confirm “Compressing via ffmpeg…” appears for a test file.

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `watch_folder` | Folder to monitor for new videos | Required |
| `drive_sync_folder` | Google Drive folder for sync (optional) | None |
| `youtube_playlist_id` | YouTube playlist ID for auto-sorting | None |
| `youtube_privacy` | Upload privacy setting | `unlisted` |
| `default_description` | Default YouTube description | `Raid Upload` |
| `default_tags` | Default YouTube tags | `["World of Warcraft", "WoW", "Raid", "POV"]` |
| `dry_run` | Skip uploads and Drive sync for testing | `false` |
| `stable_write_checks` | File stability checks before processing | `3` |
| `stable_write_interval_seconds` | Seconds between stability checks | `2` |
| `min_file_age_seconds` | Minimum age before processing | `5` |
| `ignore_patterns` | Patterns to ignore | `*.tmp, *.part, *.crdownload` |
| `ignore_extensions` | Extensions to ignore | `.tmp, .part, .crdownload` |
| `pull_tracker_path` | Persisted pull counter file path | `pull_tracker.json` |
| `log_level` | Logging level | `INFO` |
| `compression_enabled` | Enable ffmpeg compression | `false` |
| `compression_preset` | ffmpeg preset | `medium` |
| `compression_crf` | ffmpeg CRF value | `23` |
| `compression_audio_bitrate` | ffmpeg audio bitrate | `128k` |
| `compression_max_width` | Scale to max width | `null` |
| `max_retries` | Upload retry attempts | `5` |
| `retry_backoff_seconds` | Base retry backoff | `5` |
| `retry_backoff_multiplier` | Backoff multiplier | `2` |
| `retry_jitter_seconds` | Retry jitter | `2` |
| `pending_uploads_path` | Pending upload queue | `pending_uploads.json` |
| `log_file` | Log file path | `youtube_uploader.log` |
| `log_max_bytes` | Max log size before rotation | `5000000` |
| `log_backup_count` | Number of rotated logs to keep | `3` |
| `uploaded_titles_path` | Uploaded title cache | `uploaded_titles.json` |
| `delete_after_upload` | Delete local file after upload | `false` |
| `drive_sync_mode` | Drive sync `move` or `copy` | `move` |
| `duplicate_guard_mode` | Duplicate guard `title`, `hash`, `none` | `title` |
| `compression_keep_original` | Keep original if compression used | `true` |

## File Naming

Videos are automatically renamed using the format:
```
Raid_YYYY-MM-DD_HH-MM.mp4
```

## Logging

The script creates detailed logs in `youtube_uploader.log` including:
- File detection events
- Upload progress
- Error messages
- Success confirmations

## Troubleshooting

### Common Issues

1. **"credentials.json not found"**
   - Download OAuth credentials from Google Cloud Console
   - Save as `credentials.json` in the project directory

3. **Upload fails**
   - Check your internet connection
   - Verify YouTube API quota limits
   - Check the log file for detailed error messages

4. **File not detected**
   - Ensure the watch folder path is correct
   - Check that files are .mp4 format
   - Verify folder permissions

5. **Compression not working**
   - Ensure `ffmpeg` is installed and available on PATH
   - Set `compression_enabled` to `true` in `config.json`

6. **Uploads stuck in queue**
   - Check `pending_uploads.json` entries are valid paths
   - Run `python reset_pending_uploads.py` to clear the queue

## Security Notes

- Never commit `credentials.json` or `token.json` to version control
- These files contain sensitive authentication information
- The `.gitignore` file is configured to exclude these files

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is open source. Feel free to modify and distribute according to your needs.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the log files
3. Create an issue on GitHub with detailed information

---

**Note**: This tool is designed for personal use with your own YouTube channel. Ensure you have the right to upload the content and comply with YouTube's Terms of Service.

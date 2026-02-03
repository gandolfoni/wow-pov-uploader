# Python script to upload videos to YouTube from a folder
import os
import time
import datetime
import json
import logging
import shutil
import sys
import argparse
import fnmatch
import subprocess
import random
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# ---------- CONFIG ----------
CONFIG_DEFAULTS = {
    "watch_folder": r"C:\Path\To\WarcraftRecorder",
    "drive_sync_folder": r"C:\Users\You\GoogleDrive\RaidVideos",
    "youtube_playlist_id": None,
    "season_start_date": "2024-09-01",
    "scopes": ["https://www.googleapis.com/auth/youtube.upload"],
    "youtube_privacy": "unlisted",
    "default_description": "Raid Upload",
    "default_tags": ["World of Warcraft", "WoW", "Raid", "POV"],
    "dry_run": False,
    "stable_write_checks": 3,
    "stable_write_interval_seconds": 2,
    "min_file_age_seconds": 5,
    "ignore_patterns": [
        "*.tmp",
        "*.part",
        "*.partial",
        "*.crdownload",
        "*.download",
    ],
    "ignore_extensions": [".tmp", ".part", ".crdownload"],
    "pull_tracker_path": "pull_tracker.json",
    "log_level": "INFO",
    "compression_enabled": False,
    "compression_preset": "medium",
    "compression_crf": 23,
    "compression_audio_bitrate": "128k",
    "compression_max_width": None,
    "max_retries": 5,
    "retry_backoff_seconds": 5,
    "retry_backoff_multiplier": 2,
    "retry_jitter_seconds": 2,
    "pending_uploads_path": "pending_uploads.json",
}

WATCH_FOLDER = CONFIG_DEFAULTS["watch_folder"]
DRIVE_SYNC_FOLDER = CONFIG_DEFAULTS["drive_sync_folder"]
YOUTUBE_PLAYLIST_ID = CONFIG_DEFAULTS["youtube_playlist_id"]
SEASON_START_DATE = CONFIG_DEFAULTS["season_start_date"]
SCOPES = CONFIG_DEFAULTS["scopes"]
YOUTUBE_PRIVACY = CONFIG_DEFAULTS["youtube_privacy"]
DEFAULT_DESCRIPTION = CONFIG_DEFAULTS["default_description"]
DEFAULT_TAGS = CONFIG_DEFAULTS["default_tags"]
DRY_RUN = CONFIG_DEFAULTS["dry_run"]
STABLE_WRITE_CHECKS = CONFIG_DEFAULTS["stable_write_checks"]
STABLE_WRITE_INTERVAL_SECONDS = CONFIG_DEFAULTS["stable_write_interval_seconds"]
MIN_FILE_AGE_SECONDS = CONFIG_DEFAULTS["min_file_age_seconds"]
IGNORE_PATTERNS = CONFIG_DEFAULTS["ignore_patterns"]
IGNORE_EXTENSIONS = CONFIG_DEFAULTS["ignore_extensions"]
PULL_TRACKER_PATH = CONFIG_DEFAULTS["pull_tracker_path"]
LOG_LEVEL = CONFIG_DEFAULTS["log_level"]
COMPRESSION_ENABLED = CONFIG_DEFAULTS["compression_enabled"]
COMPRESSION_PRESET = CONFIG_DEFAULTS["compression_preset"]
COMPRESSION_CRF = CONFIG_DEFAULTS["compression_crf"]
COMPRESSION_AUDIO_BITRATE = CONFIG_DEFAULTS["compression_audio_bitrate"]
COMPRESSION_MAX_WIDTH = CONFIG_DEFAULTS["compression_max_width"]
MAX_RETRIES = CONFIG_DEFAULTS["max_retries"]
RETRY_BACKOFF_SECONDS = CONFIG_DEFAULTS["retry_backoff_seconds"]
RETRY_BACKOFF_MULTIPLIER = CONFIG_DEFAULTS["retry_backoff_multiplier"]
RETRY_JITTER_SECONDS = CONFIG_DEFAULTS["retry_jitter_seconds"]
PENDING_UPLOADS_PATH = CONFIG_DEFAULTS["pending_uploads_path"]

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('youtube_uploader.log'),
        logging.StreamHandler()
    ]
)
# ----------------------------

def _merge_config(defaults, overrides):
    merged = dict(defaults)
    if not overrides:
        return merged
    for key, value in overrides.items():
        if key in merged:
            merged[key] = value
        else:
            merged[key] = value
    return merged

def load_config(path):
    if not path or not os.path.exists(path):
        return dict(CONFIG_DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            logging.warning("Config file %s is not a JSON object. Using defaults.", path)
            return dict(CONFIG_DEFAULTS)
        return _merge_config(CONFIG_DEFAULTS, data)
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Failed to load config %s: %s. Using defaults.", path, exc)
        return dict(CONFIG_DEFAULTS)

def parse_args():
    parser = argparse.ArgumentParser(description="WoW POV YouTube uploader")
    parser.add_argument("--config", default="config.json", help="Path to JSON config file")
    parser.add_argument("--watch-folder", help="Folder to monitor for videos")
    parser.add_argument("--drive-sync-folder", help="Google Drive sync folder (optional)")
    parser.add_argument("--playlist-id", help="YouTube playlist ID")
    parser.add_argument("--season-start-date", help="Season start date (YYYY-MM-DD)")
    parser.add_argument("--privacy", choices=["unlisted", "private", "public"], help="YouTube privacy status")
    parser.add_argument("--description", help="Default YouTube description")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--dry-run", action="store_true", help="Skip uploads and Drive sync")
    parser.add_argument("--stable-write-checks", type=int, help="Stable size/mtime checks")
    parser.add_argument("--stable-write-interval-seconds", type=int, help="Seconds between stability checks")
    parser.add_argument("--min-file-age-seconds", type=int, help="Minimum file age before processing")
    parser.add_argument("--ignore-patterns", help="Comma-separated ignore patterns (fnmatch)")
    parser.add_argument("--ignore-extensions", help="Comma-separated ignore extensions (.tmp,.part)")
    parser.add_argument("--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--compression-enabled", action="store_true", help="Enable ffmpeg compression")
    parser.add_argument("--compression-preset", help="ffmpeg preset (ultrafast..veryslow)")
    parser.add_argument("--compression-crf", type=int, help="ffmpeg CRF value (lower is higher quality)")
    parser.add_argument("--compression-audio-bitrate", help="ffmpeg audio bitrate (e.g., 128k)")
    parser.add_argument("--compression-max-width", type=int, help="Scale to max width (preserve aspect)")
    parser.add_argument("--max-retries", type=int, help="Max upload retries")
    parser.add_argument("--retry-backoff-seconds", type=int, help="Initial retry backoff in seconds")
    parser.add_argument("--retry-backoff-multiplier", type=int, help="Retry backoff multiplier")
    parser.add_argument("--retry-jitter-seconds", type=int, help="Random jitter seconds added to backoff")
    return parser.parse_args()

def apply_config(config, args):
    global WATCH_FOLDER
    global DRIVE_SYNC_FOLDER
    global YOUTUBE_PLAYLIST_ID
    global SEASON_START_DATE
    global SCOPES
    global YOUTUBE_PRIVACY
    global DEFAULT_DESCRIPTION
    global DEFAULT_TAGS
    global DRY_RUN
    global STABLE_WRITE_CHECKS
    global STABLE_WRITE_INTERVAL_SECONDS
    global MIN_FILE_AGE_SECONDS
    global IGNORE_PATTERNS
    global IGNORE_EXTENSIONS
    global PULL_TRACKER_PATH
    global LOG_LEVEL
    global COMPRESSION_ENABLED
    global COMPRESSION_PRESET
    global COMPRESSION_CRF
    global COMPRESSION_AUDIO_BITRATE
    global COMPRESSION_MAX_WIDTH
    global MAX_RETRIES
    global RETRY_BACKOFF_SECONDS
    global RETRY_BACKOFF_MULTIPLIER
    global RETRY_JITTER_SECONDS
    global PENDING_UPLOADS_PATH

    if args.watch_folder:
        config["watch_folder"] = args.watch_folder
    if args.drive_sync_folder is not None:
        config["drive_sync_folder"] = args.drive_sync_folder
    if args.playlist_id is not None:
        config["youtube_playlist_id"] = args.playlist_id
    if args.season_start_date:
        config["season_start_date"] = args.season_start_date
    if args.privacy:
        config["youtube_privacy"] = args.privacy
    if args.description is not None:
        config["default_description"] = args.description
    if args.tags is not None:
        config["default_tags"] = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
    if args.dry_run:
        config["dry_run"] = True
    if args.stable_write_checks is not None:
        config["stable_write_checks"] = args.stable_write_checks
    if args.stable_write_interval_seconds is not None:
        config["stable_write_interval_seconds"] = args.stable_write_interval_seconds
    if args.min_file_age_seconds is not None:
        config["min_file_age_seconds"] = args.min_file_age_seconds
    if args.ignore_patterns is not None:
        config["ignore_patterns"] = [p.strip() for p in args.ignore_patterns.split(",") if p.strip()]
    if args.ignore_extensions is not None:
        config["ignore_extensions"] = [e.strip() for e in args.ignore_extensions.split(",") if e.strip()]
    if args.log_level is not None:
        config["log_level"] = args.log_level
    if args.compression_enabled:
        config["compression_enabled"] = True
    if args.compression_preset is not None:
        config["compression_preset"] = args.compression_preset
    if args.compression_crf is not None:
        config["compression_crf"] = args.compression_crf
    if args.compression_audio_bitrate is not None:
        config["compression_audio_bitrate"] = args.compression_audio_bitrate
    if args.compression_max_width is not None:
        config["compression_max_width"] = args.compression_max_width
    if args.max_retries is not None:
        config["max_retries"] = args.max_retries
    if args.retry_backoff_seconds is not None:
        config["retry_backoff_seconds"] = args.retry_backoff_seconds
    if args.retry_backoff_multiplier is not None:
        config["retry_backoff_multiplier"] = args.retry_backoff_multiplier
    if args.retry_jitter_seconds is not None:
        config["retry_jitter_seconds"] = args.retry_jitter_seconds

    WATCH_FOLDER = config["watch_folder"]
    DRIVE_SYNC_FOLDER = config["drive_sync_folder"]
    YOUTUBE_PLAYLIST_ID = config["youtube_playlist_id"]
    SEASON_START_DATE = config["season_start_date"]
    SCOPES = config["scopes"]
    YOUTUBE_PRIVACY = config["youtube_privacy"]
    DEFAULT_DESCRIPTION = config["default_description"]
    DEFAULT_TAGS = config["default_tags"]
    DRY_RUN = config["dry_run"]
    STABLE_WRITE_CHECKS = config["stable_write_checks"]
    STABLE_WRITE_INTERVAL_SECONDS = config["stable_write_interval_seconds"]
    MIN_FILE_AGE_SECONDS = config["min_file_age_seconds"]
    IGNORE_PATTERNS = config["ignore_patterns"]
    IGNORE_EXTENSIONS = config["ignore_extensions"]
    PULL_TRACKER_PATH = config["pull_tracker_path"]
    LOG_LEVEL = config["log_level"]
    COMPRESSION_ENABLED = config["compression_enabled"]
    COMPRESSION_PRESET = config["compression_preset"]
    COMPRESSION_CRF = config["compression_crf"]
    COMPRESSION_AUDIO_BITRATE = config["compression_audio_bitrate"]
    COMPRESSION_MAX_WIDTH = config["compression_max_width"]
    MAX_RETRIES = config["max_retries"]
    RETRY_BACKOFF_SECONDS = config["retry_backoff_seconds"]
    RETRY_BACKOFF_MULTIPLIER = config["retry_backoff_multiplier"]
    RETRY_JITTER_SECONDS = config["retry_jitter_seconds"]
    PENDING_UPLOADS_PATH = config["pending_uploads_path"]

    logging.getLogger().setLevel(LOG_LEVEL)

def authenticate_youtube():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w", encoding="utf-8") as token:
            token.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def extract_context_from_filename(filename):
    """Extract context information from Warcraft Recorder filename.

    Expected format: YYYY-MM-DD HH-MM-SS - Marpally - [Context]...
    Returns: (date, time, context)
    """
    try:
        # Remove file extension
        name = os.path.splitext(filename)[0]

        # Split by " - " to get parts
        parts = name.split(" - ")
        if len(parts) >= 3:
            timestamp_part = parts[0]  # "2025-09-03 22-16-58"
            context_part = parts[2]    # "Fo..." or "Th..." etc.

            # Parse timestamp
            date_time = datetime.datetime.strptime(timestamp_part, "%Y-%m-%d %H-%M-%S")

            # Extract context (remove "..." if present)
            context = context_part.replace("...", "").strip()

            return date_time, context
    except (ValueError, IndexError) as exc:
        logging.warning("Could not parse filename %s: %s", filename, exc)

    # Fallback to current time and generic context
    return datetime.datetime.now(), "Unknown"

def load_pull_tracker(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        logging.warning("Failed to load pull tracker from %s: %s", path, exc)
        return {}

def save_pull_tracker(path, tracker):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(tracker, handle, indent=2, sort_keys=True)
    except OSError as exc:
        logging.warning("Failed to save pull tracker to %s: %s", path, exc)

def get_raid_week(start_date=None):
    """Calculate raid week number from season start date.

    Args:
        start_date: Season start date (defaults to SEASON_START_DATE config)
    Returns:
        Week number (W1, W2, etc.)
    """
    if start_date is None:
        # Use the configured season start date
        try:
            start_date = datetime.datetime.strptime(SEASON_START_DATE, "%Y-%m-%d").date()
        except ValueError:
            # Fallback to default if config is invalid
            start_date = datetime.date(2024, 9, 1)

    today = datetime.date.today()
    days_diff = (today - start_date).days
    week_num = max(1, (days_diff // 7) + 1)  # Ensure at least week 1
    return f"W{week_num}"

def get_boss_pull_count(boss_name, date, pull_tracker):
    """Get the pull count for a specific boss on a specific date.

    Args:
        boss_name: Name of the boss/encounter
        date: Date of the encounter
        pull_tracker: Dictionary to track pull counts

    Returns:
        Pull number for this boss on this date
    """
    date_key = date.strftime("%Y-%m-%d")
    boss_key = f"{date_key}_{boss_name}"

    if boss_key not in pull_tracker:
        pull_tracker[boss_key] = 0

    pull_tracker[boss_key] += 1
    return pull_tracker[boss_key]

def make_nice_name(file_path, pull_tracker=None):
    """Generate a context-aware filename with raid week, boss, and pull tracking.

    Format: RaidWeek_BossName_Pull#_Date_Time.mp4
    Example: W1_Fo_Pull1_Sep03_10-16PM.mp4
    """
    if pull_tracker is None:
        pull_tracker = {}

    filename = os.path.basename(file_path)
    _, ext = os.path.splitext(filename)

    # Extract context from Warcraft Recorder filename
    record_time, context = extract_context_from_filename(filename)

    # Get raid week
    raid_week = get_raid_week()

    # Get pull count for this boss on this date
    pull_count = get_boss_pull_count(context, record_time.date(), pull_tracker)

    # Format date and time
    date_str = record_time.strftime("%b%d")  # Sep03, Oct15, etc.
    time_str = record_time.strftime("%I-%M%p")  # 10-16PM, 2-30AM, etc.

    # Create the new filename
    new_name = f"{raid_week}_{context}_Pull{pull_count}_{date_str}_{time_str}{ext}"

    logging.info("Renamed: %s -> %s", filename, new_name)
    return new_name

def wait_for_file_stable(file_path):
    """Wait until a file stops changing size/mtime for a few checks."""
    stable_checks = 0
    previous_size = -1
    previous_mtime = -1

    while stable_checks < STABLE_WRITE_CHECKS:
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                "File disappeared before processing: %s" % file_path
            )
        current_size = os.path.getsize(file_path)
        current_mtime = os.path.getmtime(file_path)
        current_age = time.time() - current_mtime

        is_stable = current_size == previous_size and current_mtime == previous_mtime
        is_old_enough = current_age >= MIN_FILE_AGE_SECONDS

        if is_stable and is_old_enough:
            stable_checks += 1
        else:
            stable_checks = 0

        previous_size = current_size
        previous_mtime = current_mtime
        time.sleep(STABLE_WRITE_INTERVAL_SECONDS)

def should_ignore_file(file_path):
    filename = os.path.basename(file_path)
    _, ext = os.path.splitext(filename)
    lower_ext = ext.lower()

    if lower_ext in [e.lower() for e in IGNORE_EXTENSIONS]:
        return True

    for pattern in IGNORE_PATTERNS:
        if fnmatch.fnmatch(filename.lower(), pattern.lower()):
            return True

    return False

def build_upload_request(title, description, tags, privacy_status):
    return {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "20",  # Gaming
            "tags": tags
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }

def _ffmpeg_available():
    return shutil.which("ffmpeg") is not None

def _build_ffmpeg_command(input_path, output_path):
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-c:v",
        "libx264",
        "-preset",
        str(COMPRESSION_PRESET),
        "-crf",
        str(COMPRESSION_CRF),
        "-c:a",
        "aac",
        "-b:a",
        str(COMPRESSION_AUDIO_BITRATE),
    ]
    if COMPRESSION_MAX_WIDTH:
        cmd += ["-vf", f"scale='min({COMPRESSION_MAX_WIDTH},iw)':-2"]
    cmd.append(output_path)
    return cmd

def compress_video(input_path):
    if not COMPRESSION_ENABLED:
        return input_path, False
    if not _ffmpeg_available():
        logging.warning("ffmpeg not found in PATH; skipping compression.")
        return input_path, False

    base, ext = os.path.splitext(input_path)
    output_path = base + ".compressed" + ext
    cmd = _build_ffmpeg_command(input_path, output_path)

    logging.info("Compressing via ffmpeg: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError) as exc:
        logging.error("Compression failed: %s", exc)
        return input_path, False

    if not os.path.exists(output_path):
        logging.error("Compression output missing: %s", output_path)
        return input_path, False

    return output_path, True

def _should_retry_http_error(exc):
    status = getattr(exc, "status_code", None)
    if status is None and hasattr(exc, "resp"):
        status = getattr(exc.resp, "status", None)
    return status in {429, 500, 502, 503, 504}

def _sleep_backoff(attempt):
    base = RETRY_BACKOFF_SECONDS * (RETRY_BACKOFF_MULTIPLIER ** attempt)
    jitter = random.uniform(0, RETRY_JITTER_SECONDS)
    time.sleep(base + jitter)

def upload_to_youtube(youtube_service, file_path, title, upload_options):
    """Upload video to YouTube with error handling and progress tracking."""
    logging.info("Starting upload: %s", title)

    # Check if file exists and get size
    if not os.path.exists(file_path):
        raise FileNotFoundError("Video file not found: %s" % file_path)

    file_size = os.path.getsize(file_path)
    logging.info("File size: %.1f MB", file_size / (1024*1024))

    request_body = build_upload_request(
        title,
        upload_options["description"],
        upload_options["tags"],
        upload_options["privacy_status"],
    )

    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
            request = youtube_service.videos().insert(
                part="snippet,status",
                body=request_body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logging.info("Upload progress: %d%%", progress)

            video_id = response["id"]
            video_url = "https://youtu.be/%s" % video_id
            logging.info("Upload complete: %s", video_url)

            # Add to playlist if requested
            playlist_id = upload_options["playlist_id"]
            if playlist_id:
                try:
                    youtube_service.playlistItems().insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "playlistId": playlist_id,
                                "resourceId": {"kind": "youtube#video", "videoId": video_id}
                            }
                        }
                    ).execute()
                    logging.info("Added to playlist: %s", playlist_id)
                except HttpError as exc:
                    logging.error("Failed to add to playlist: %s", exc)

            return video_url

        except HttpError as exc:
            last_exc = exc
            if attempt >= MAX_RETRIES or not _should_retry_http_error(exc):
                logging.error("YouTube upload failed: %s", exc)
                raise
            logging.warning("Upload failed; retrying (%d/%d): %s", attempt + 1, MAX_RETRIES, exc)
            _sleep_backoff(attempt)
        except OSError as exc:
            last_exc = exc
            if attempt >= MAX_RETRIES:
                logging.error("YouTube upload failed: %s", exc)
                raise
            logging.warning("Upload failed; retrying (%d/%d): %s", attempt + 1, MAX_RETRIES, exc)
            _sleep_backoff(attempt)

    if last_exc:
        raise last_exc

    raise RuntimeError("Upload failed without exception.")

def move_to_drive(file_path, dest_folder):
    """Move file to Google Drive sync folder."""
    if not dest_folder:
        return
    os.makedirs(dest_folder, exist_ok=True)
    new_path = os.path.join(dest_folder, os.path.basename(file_path))
    shutil.move(file_path, new_path)
    logging.info("Moved to Drive sync folder: %s", new_path)

class PendingUploadQueued(Exception):
    """Raised when an upload is queued for later retry."""

def load_pending_uploads(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            logging.warning("Pending uploads file is invalid: %s", path)
            return []
        return data
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Failed to load pending uploads: %s", exc)
        return []

def save_pending_uploads(path, pending):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(pending, handle, indent=2, sort_keys=True)
    except OSError as exc:
        logging.warning("Failed to save pending uploads: %s", exc)

def process_pending_uploads(youtube_service):
    pending = load_pending_uploads(PENDING_UPLOADS_PATH)
    if not pending:
        return

    logging.info("Processing %d pending uploads...", len(pending))
    remaining = []
    for item in pending:
        file_path = item.get("file_path")
        title = item.get("title")
        upload_options = item.get("upload_options")
        original_path = item.get("original_path")
        cleanup_path = item.get("cleanup_path")
        drive_sync_folder = item.get("drive_sync_folder")
        if not file_path or not title or not upload_options:
            logging.warning("Skipping invalid pending upload entry: %s", item)
            continue
        if not os.path.exists(file_path):
            logging.warning("Pending file missing, skipping: %s", file_path)
            continue

        try:
            if DRY_RUN:
                logging.info("Dry run enabled; skipping pending upload for %s", title)
                remaining.append(item)
                continue
            upload_to_youtube(youtube_service, file_path, title, upload_options)
            if cleanup_path and os.path.exists(cleanup_path):
                os.remove(cleanup_path)
            if drive_sync_folder:
                if original_path and os.path.exists(original_path):
                    move_to_drive(original_path, drive_sync_folder)
                elif os.path.exists(file_path) and file_path != cleanup_path:
                    move_to_drive(file_path, drive_sync_folder)
        except (HttpError, OSError, ValueError) as exc:
            logging.error("Pending upload failed, keeping in queue: %s", exc)
            remaining.append(item)

    save_pending_uploads(PENDING_UPLOADS_PATH, remaining)

class VideoHandler(FileSystemEventHandler):
    """File system event handler for video file monitoring."""

    def __init__(self, youtube_service):
        """Initialize the video handler with YouTube service."""
        self.youtube = youtube_service
        self.processing_files = set()  # Track files being processed
        self.pull_tracker = load_pull_tracker(PULL_TRACKER_PATH)

    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        if should_ignore_file(event.src_path):
            return
        if not event.src_path.lower().endswith(".mp4"):
            return

        # Avoid processing the same file multiple times
        if event.src_path in self.processing_files:
            return

        self.processing_files.add(event.src_path)

        try:
            self._process_video(event.src_path)
        except (OSError, HttpError, ValueError) as exc:
            logging.error("Failed to process video %s: %s", event.src_path, exc)
        finally:
            self.processing_files.discard(event.src_path)

    def on_moved(self, event):
        """Handle file move events (e.g., temp file renamed to final)."""
        if event.is_directory:
            return
        dest_path = getattr(event, "dest_path", None)
        if not dest_path:
            return
        if should_ignore_file(dest_path):
            return
        if not dest_path.lower().endswith(".mp4"):
            return
        if dest_path in self.processing_files:
            return

        self.processing_files.add(dest_path)
        try:
            self._process_video(dest_path)
        except (OSError, HttpError, ValueError) as exc:
            logging.error("Failed to process video %s: %s", dest_path, exc)
        finally:
            self.processing_files.discard(dest_path)

    def _create_youtube_title(self, filename):
        """Create a descriptive YouTube title from the filename.

        Format: WoW Raid - [Raid Week] [Boss Name] Pull #X - [Date] [Time]
        Example: WoW Raid - W1 Fo Pull #1 - Sep 03 10:16 PM
        """
        try:
            # Remove file extension
            name = os.path.splitext(filename)[0]

            # Split by underscores to get parts
            parts = name.split('_')
            if len(parts) >= 5:
                raid_week = parts[0]  # W1
                boss_name = parts[1]  # Fo
                pull_info = parts[2]  # Pull1
                date_str = parts[3]   # Sep03
                time_str = parts[4]   # 10-16PM

                # Format time for better readability
                time_formatted = time_str.replace('-', ':').replace(
                    'PM', ' PM').replace('AM', ' AM')

                # Format date for better readability
                date_formatted = date_str.replace('Sep', 'September').replace(
                    'Oct', 'October').replace('Nov', 'November').replace(
                    'Dec', 'December')
                date_formatted = date_formatted.replace('Jan', 'January').replace(
                    'Feb', 'February').replace('Mar', 'March').replace(
                    'Apr', 'April')
                date_formatted = date_formatted.replace('May', 'May').replace(
                    'Jun', 'June').replace('Jul', 'July').replace(
                    'Aug', 'August')

                # Add day number
                if len(date_formatted) > 3:
                    day_num = date_formatted[3:]
                    month_name = date_formatted[:3]
                    date_formatted = f"{month_name} {day_num}"

                return (
                    "WoW Raid - %s %s %s - %s %s"
                    % (raid_week, boss_name, pull_info, date_formatted, time_formatted)
                )
        except (IndexError, ValueError) as exc:
            logging.warning(
                "Could not create YouTube title from %s: %s", filename, exc
            )

        # Fallback to original filename
        return filename

    def _process_video(self, file_path):
        """Process a single video file with proper error handling."""
        logging.info("New file detected: %s", file_path)

        wait_for_file_stable(file_path)

        new_name = make_nice_name(file_path, self.pull_tracker)
        save_pull_tracker(PULL_TRACKER_PATH, self.pull_tracker)
        temp_path = os.path.join(WATCH_FOLDER, new_name)

        # Create backup of original file
        backup_path = file_path + ".backup"
        shutil.copy2(file_path, backup_path)

        try:
            # Move file to final location
            shutil.move(file_path, temp_path)

            # Create a more descriptive YouTube title
            youtube_title = self._create_youtube_title(new_name)

            upload_path = temp_path
            compressed = False
            if not DRY_RUN:
                upload_path, compressed = compress_video(temp_path)

            if DRY_RUN:
                logging.info("Dry run enabled; skipping upload and Drive sync.")
            else:
                upload_succeeded = False
                # Upload to YouTube
                try:
                    upload_to_youtube(
                        self.youtube,
                        upload_path,
                        title=youtube_title,
                        upload_options={
                            "description": DEFAULT_DESCRIPTION,
                            "playlist_id": YOUTUBE_PLAYLIST_ID,
                            "tags": DEFAULT_TAGS,
                            "privacy_status": YOUTUBE_PRIVACY,
                        },
                    )
                    upload_succeeded = True
                except (HttpError, OSError) as exc:
                    logging.error("Upload failed, adding to pending queue: %s", exc)
                    pending = load_pending_uploads(PENDING_UPLOADS_PATH)
                    pending.append({
                        "file_path": upload_path,
                        "original_path": temp_path,
                        "cleanup_path": upload_path if compressed else None,
                        "drive_sync_folder": DRIVE_SYNC_FOLDER,
                        "title": youtube_title,
                        "upload_options": {
                            "description": DEFAULT_DESCRIPTION,
                            "playlist_id": YOUTUBE_PLAYLIST_ID,
                            "tags": DEFAULT_TAGS,
                            "privacy_status": YOUTUBE_PRIVACY,
                        },
                    })
                    save_pending_uploads(PENDING_UPLOADS_PATH, pending)
                    raise PendingUploadQueued(str(exc))
                finally:
                    if compressed and upload_succeeded and os.path.exists(upload_path):
                        os.remove(upload_path)

                # Copy to Drive folder (optional)
                move_to_drive(temp_path, DRIVE_SYNC_FOLDER)

            # Clean up backup if everything succeeded
            if os.path.exists(backup_path):
                os.remove(backup_path)

        except PendingUploadQueued as exc:
            logging.error("Processing failed after queuing pending upload: %s", exc)
            if os.path.exists(backup_path):
                os.remove(backup_path)
            raise
        except (OSError, HttpError, ValueError) as exc:
            logging.error("Processing failed, restoring backup: %s", exc)
            # Restore original file if something went wrong
            if os.path.exists(backup_path):
                shutil.move(backup_path, file_path)
            raise

if __name__ == "__main__":
    try:
        args = parse_args()
        config = load_config(args.config)
        apply_config(config, args)

        # Validate configuration
        if not os.path.exists(WATCH_FOLDER):
            logging.error("Watch folder does not exist: %s", WATCH_FOLDER)
            sys.exit(1)

        if not os.path.exists("credentials.json"):
            logging.error("credentials.json not found. Please download it from "
                         "Google Cloud Console.")
            sys.exit(1)

        logging.info("Starting YouTube Uploader...")
        youtube = authenticate_youtube()
        process_pending_uploads(youtube)
        event_handler = VideoHandler(youtube)
        observer = Observer()
        observer.schedule(event_handler, WATCH_FOLDER, recursive=False)
        observer.start()

        logging.info("Watching %s for new videos...", WATCH_FOLDER)
        logging.info("Press Ctrl+C to stop")

        while True:
            time.sleep(10)

    except KeyboardInterrupt:
        logging.info("Shutting down...")
        observer.stop()
    except (OSError, HttpError) as exc:
        logging.error("Fatal error: %s", exc)
    finally:
        observer.join()
        logging.info("YouTube Uploader stopped.")

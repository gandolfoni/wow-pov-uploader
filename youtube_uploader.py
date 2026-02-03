# Python script to upload videos to YouTube from a folder
import os
import time
import datetime
import json
import logging
import shutil
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# ---------- CONFIG ----------
WATCH_FOLDER = r"C:\Path\To\WarcraftRecorder"
DRIVE_SYNC_FOLDER = r"C:\Users\You\GoogleDrive\RaidVideos"  # Optional, leave empty if unused
YOUTUBE_PLAYLIST_ID = None  # Set to a playlist ID if you want automatic sorting
SEASON_START_DATE = "2024-09-01"  # Season start date for raid week calculation (YYYY-MM-DD)
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Upload behavior
YOUTUBE_PRIVACY = "unlisted"  # unlisted, private, public
DEFAULT_DESCRIPTION = "Raid Upload"
DEFAULT_TAGS = ["World of Warcraft", "WoW", "Raid", "POV"]
DRY_RUN = False  # Set True to skip uploads for testing

# File handling behavior
STABLE_WRITE_CHECKS = 3  # Number of consecutive stable checks before processing
STABLE_WRITE_INTERVAL_SECONDS = 2
PULL_TRACKER_PATH = "pull_tracker.json"

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
    """Wait until a file stops changing size for a few checks."""
    stable_checks = 0
    previous_size = -1

    while stable_checks < STABLE_WRITE_CHECKS:
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                "File disappeared before processing: %s" % file_path
            )
        current_size = os.path.getsize(file_path)
        if current_size == previous_size:
            stable_checks += 1
        else:
            stable_checks = 0
        previous_size = current_size
        time.sleep(STABLE_WRITE_INTERVAL_SECONDS)

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

def upload_to_youtube(youtube_service, file_path, title, upload_options):
    """Upload video to YouTube with error handling and progress tracking."""
    try:
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

        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        request = youtube_service.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=media
        )

        response = None
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logging.info("Upload progress: %d%%", progress)
            except HttpError as exc:
                logging.error("Upload chunk failed: %s", exc)
                raise

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

    except (HttpError, OSError) as exc:
        logging.error("YouTube upload failed: %s", exc)
        raise

def move_to_drive(file_path, dest_folder):
    """Move file to Google Drive sync folder."""
    if not dest_folder:
        return
    os.makedirs(dest_folder, exist_ok=True)
    new_path = os.path.join(dest_folder, os.path.basename(file_path))
    os.rename(file_path, new_path)
    logging.info("Copied to Drive sync folder: %s", new_path)

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
        if not event.src_path.endswith(".mp4"):
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

            if DRY_RUN:
                logging.info("Dry run enabled; skipping upload and Drive sync.")
            else:
                # Upload to YouTube
                upload_to_youtube(
                    self.youtube,
                    temp_path,
                    title=youtube_title,
                    upload_options={
                        "description": DEFAULT_DESCRIPTION,
                        "playlist_id": YOUTUBE_PLAYLIST_ID,
                        "tags": DEFAULT_TAGS,
                        "privacy_status": YOUTUBE_PRIVACY,
                    },
                )

                # Copy to Drive folder (optional)
                move_to_drive(temp_path, DRIVE_SYNC_FOLDER)

            # Clean up backup if everything succeeded
            if os.path.exists(backup_path):
                os.remove(backup_path)

        except (OSError, HttpError, ValueError) as exc:
            logging.error("Processing failed, restoring backup: %s", exc)
            # Restore original file if something went wrong
            if os.path.exists(backup_path):
                shutil.move(backup_path, file_path)
            raise

if __name__ == "__main__":
    try:
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

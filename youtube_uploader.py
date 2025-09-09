# Python script to upload videos to YouTube from a folder
import os
import time
import datetime
import subprocess
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

# ---------- CONFIG ----------
WATCH_FOLDER = r"C:\Path\To\WarcraftRecorder"
DRIVE_SYNC_FOLDER = r"C:\Users\You\GoogleDrive\RaidVideos"  # Optional, leave empty if unused
COMPRESS = True   # Use ffmpeg to shrink file size
YOUTUBE_PLAYLIST_ID = None  # Set to a playlist ID if you want automatic sorting
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

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

def make_nice_name(file_path):
    """Generate a nice filename with timestamp.

    Template: Boss_PullCount_YYYY-MM-DD_HH-MM.mp4
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    base = os.path.basename(file_path)
    _, ext = os.path.splitext(base)
    # Placeholder: replace with actual boss/pull logic if available
    return f"Raid_{timestamp}{ext}"

def compress_with_ffmpeg(input_path, output_path):
    """Compress video using FFmpeg with optimized settings for gaming content."""
    logging.info("Compressing %s...", input_path)
    try:
        # Better compression settings for gaming content
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-c:v", "libx264",           # Video codec
            "-crf", "23",                # Better quality (lower = better quality)
            "-preset", "medium",         # Balance between speed and compression
            "-c:a", "aac",               # Audio codec
            "-b:a", "128k",              # Audio bitrate
            "-movflags", "+faststart",   # Optimize for web streaming
            "-vf", "scale=1920:1080",    # Scale to 1080p if needed
            output_path
        ]

        subprocess.run(cmd, capture_output=True, text=True, check=True)
        logging.info("Compression completed successfully: %s", output_path)
        return output_path
    except subprocess.CalledProcessError as e:
        logging.error("FFmpeg compression failed: %s", e.stderr)
        raise
    except FileNotFoundError:
        logging.error("FFmpeg not found. Please install FFmpeg and ensure it's in your PATH.")
        raise

def upload_to_youtube(youtube_service, file_path, title, description="Raid Upload",
                     playlist_id=None):
    """Upload video to YouTube with error handling and progress tracking."""
    try:
        logging.info("Starting upload: %s", title)

        # Check if file exists and get size
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Video file not found: {file_path}")

        file_size = os.path.getsize(file_path)
        logging.info("File size: %.1f MB", file_size / (1024*1024))

        request_body = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": "20"  # Gaming
            },
            "status": {
                "privacyStatus": "unlisted"
            }
        }

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
            except Exception as e:
                logging.error("Upload chunk failed: %s", e)
                raise

        video_id = response['id']
        video_url = f"https://youtu.be/{video_id}"
        logging.info("Upload complete: %s", video_url)

        # Add to playlist if requested
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
            except Exception as e:
                logging.error("Failed to add to playlist: %s", e)

        return video_url

    except Exception as e:
        logging.error("YouTube upload failed: %s", e)
        raise

def move_to_drive(file_path, dest_folder):
    """Move file to Google Drive sync folder."""
    if not dest_folder:
        return
    os.makedirs(dest_folder, exist_ok=True)
    new_path = os.path.join(dest_folder, os.path.basename(file_path))
    os.rename(file_path, new_path)
    print(f"Copied to Drive sync folder: {new_path}")

class VideoHandler(FileSystemEventHandler):
    """File system event handler for video file monitoring."""

    def __init__(self, youtube_service):
        """Initialize the video handler with YouTube service."""
        self.youtube = youtube_service
        self.processing_files = set()  # Track files being processed

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
        except Exception as e:
            logging.error("Failed to process video %s: %s", event.src_path, e)
        finally:
            self.processing_files.discard(event.src_path)

    def _process_video(self, file_path):
        """Process a single video file with proper error handling."""
        logging.info("New file detected: %s", file_path)

        # Wait a bit to ensure file is fully written
        time.sleep(2)

        # Check if file is still being written to
        initial_size = os.path.getsize(file_path)
        time.sleep(1)
        if os.path.getsize(file_path) != initial_size:
            logging.info("File still being written, waiting...")
            time.sleep(5)

        new_name = make_nice_name(file_path)
        temp_path = os.path.join(WATCH_FOLDER, new_name)

        # Create backup of original file
        backup_path = file_path + ".backup"
        shutil.copy2(file_path, backup_path)

        try:
            # Compress if enabled
            final_path = temp_path
            if COMPRESS:
                final_path = temp_path.replace(".mp4", "_compressed.mp4")
                compress_with_ffmpeg(file_path, final_path)
            else:
                shutil.move(file_path, final_path)

            # Upload to YouTube
            upload_to_youtube(self.youtube, final_path, title=new_name,
                             playlist_id=YOUTUBE_PLAYLIST_ID)

            # Copy to Drive folder (optional)
            move_to_drive(final_path, DRIVE_SYNC_FOLDER)

            # Clean up backup if everything succeeded
            if os.path.exists(backup_path):
                os.remove(backup_path)

        except Exception as e:
            logging.error("Processing failed, restoring backup: %s", e)
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
    except Exception as e:
        logging.error("Fatal error: %s", e)
    finally:
        observer.join()
        logging.info("YouTube Uploader stopped.")

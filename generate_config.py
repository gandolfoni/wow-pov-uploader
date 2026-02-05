import json
import os

DEFAULTS = {
    "watch_folder": "C:\\Path\\To\\WarcraftRecorder",
    "youtube_privacy": "unlisted",
    "default_description": "Raid Upload",
    "default_tags": ["World of Warcraft", "WoW", "Raid", "POV"],
    "dry_run": False,
    "youtube_playlist_id": None,
    "stable_write_checks": 3,
    "stable_write_interval_seconds": 2,
    "min_file_age_seconds": 5,
    "ignore_patterns": ["*.tmp", "*.part", "*.crdownload"],
    "ignore_extensions": [".tmp", ".part", ".crdownload"],
    "drive_sync_mode": "move",
    "duplicate_guard_mode": "title",
    "compression_keep_original": True,
    "failed_folder": "failed",
    "max_uploads_per_run": None,
    "title_collision_suffix": "auto",
}

def main():
    path = "config.json"
    if os.path.exists(path):
        print("config.json already exists; not overwriting.")
        return
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(DEFAULTS, handle, indent=2)
    print("Wrote config.json")

if __name__ == "__main__":
    main()

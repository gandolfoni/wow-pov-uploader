# Setup Instructions

This guide will walk you through setting up the WoW POV Uploader for the first time.

## Step 1: Prerequisites

### Install Python
- Download Python 3.7+ from [python.org](https://www.python.org/downloads/)
- During installation, check "Add Python to PATH"

### Verify Installations
```bash
python --version
```

## Step 2: Google Cloud Console Setup

1. **Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Click "Select a project" → "New Project"
   - Name it "WoW POV Uploader" (or any name you prefer)
   - Click "Create"

2. **Enable YouTube Data API**
   - In the project dashboard, go to "APIs & Services" → "Library"
   - Search for "YouTube Data API v3"
   - Click on it and press "Enable"

3. **Create OAuth Credentials**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - If prompted, configure the OAuth consent screen:
     - Choose "External" user type
     - Fill in required fields (App name: "WoW POV Uploader")
     - Add your email to test users
   - For Application type, choose "Desktop application"
   - Name it "WoW POV Uploader Desktop"
   - Click "Create"

4. **Download Credentials**
   - Click the download button (⬇️) next to your new OAuth client
   - Save the file as `credentials.json` in your project folder

## Step 3: Project Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure via `config.json` (Recommended)**
   - Create a `config.json` in the project folder:
   ```json
   {
     "watch_folder": "C:\\Path\\To\\Your\\WarcraftRecorder",
     "drive_sync_folder": "C:\\Users\\YourName\\GoogleDrive\\RaidVideos",
     "youtube_privacy": "unlisted",
     "default_description": "Raid Upload",
     "default_tags": ["World of Warcraft", "WoW", "Raid", "POV"],
     "dry_run": false,
     "youtube_playlist_id": null,
     "stable_write_checks": 3,
     "stable_write_interval_seconds": 2,
     "min_file_age_seconds": 5,
     "ignore_patterns": ["*.tmp", "*.part", "*.crdownload"],
     "ignore_extensions": [".tmp", ".part", ".crdownload"],
     "pull_tracker_path": "pull_tracker.json",
     "log_level": "INFO"
   }
   ```

3. **CLI Overrides (Optional)**
   - You can override any config values at runtime:
   ```bash
   python youtube_uploader.py --watch-folder "C:\Path\To\Your\WarcraftRecorder" --dry-run
   ```

3. **Create Watch Folder**
   - Create the folder you specified in `WATCH_FOLDER`
   - This is where you'll place your WoW recording files

## Step 4: First Run

1. **Start the Script**
   ```bash
   python youtube_uploader.py
   ```

2. **Authenticate with Google**
   - A browser window will open
   - Sign in to your Google account
   - Click "Allow" to grant permissions
   - The script will save authentication tokens

3. **Test with a Video**
   - Place a test MP4 file in your watch folder
   - The script should detect it and start processing
   - Check the console output and `youtube_uploader.log` for progress

## Step 5: Optional Configurations

### YouTube Playlist Setup
1. Go to your YouTube channel
2. Create a new playlist (e.g., "WoW Raid Videos")
3. Copy the playlist ID from the URL
4. Update `YOUTUBE_PLAYLIST_ID` in the script
   - Or set `youtube_playlist_id` in `config.json`
   - Or pass `--playlist-id` on the CLI

### Google Drive Sync
1. Install Google Drive desktop app
2. Create a folder for your videos
3. Update `DRIVE_SYNC_FOLDER` path in the script

## Troubleshooting

### Common Issues

**"credentials.json not found"**
- Download OAuth credentials from Google Cloud Console
- Save as `credentials.json` in project folder

**"Watch folder does not exist"**
- Create the folder specified in `WATCH_FOLDER`
- Check the path is correct (use forward slashes or raw strings)

**Upload fails**
- Check internet connection
- Verify YouTube API quota (100 units/day for new projects)
- Check `youtube_uploader.log` for detailed errors

**File not detected**
- Ensure files are .mp4 format
- Check folder permissions
- Wait a few seconds after file creation

### Getting Help

1. Check the log file: `youtube_uploader.log`
2. Review console output for error messages
3. Ensure all prerequisites are installed correctly
4. Verify Google Cloud Console setup

## Security Notes

- Never share `credentials.json` or `token.json`
- These files contain sensitive authentication data
- The `.gitignore` file prevents them from being committed to Git

## Next Steps

Once everything is working:
1. Set up your WoW recording software to save to the watch folder (I am using Warcraft Recorder, find more detials about file paths to the watch folder in their docs)
2. Configure automatic recording triggers
3. Set up YouTube playlists for organization
4. Consider setting up Google Drive sync for backups

Keep yer feet on the ground! 

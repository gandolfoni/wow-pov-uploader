# Setup Instructions

This guide will walk you through setting up the WoW POV Uploader for the first time.

## Step 1: Prerequisites

### Install Python
- Download Python 3.7+ from [python.org](https://www.python.org/downloads/)
- During installation, check "Add Python to PATH"

### Install FFmpeg
- **Windows**: 
  - Download from [FFmpeg.org](https://ffmpeg.org/download.html)
  - Extract to `C:\ffmpeg`
  - Add `C:\ffmpeg\bin` to your system PATH
  - Or use: `winget install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

### Verify Installations
```bash
python --version
ffmpeg -version
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

2. **Configure the Script**
   - Open `youtube_uploader.py` in a text editor
   - Update the configuration section:
   ```python
   WATCH_FOLDER = r"C:\Path\To\Your\WarcraftRecorder"  # Change this path
   DRIVE_SYNC_FOLDER = r"C:\Users\YourName\GoogleDrive\RaidVideos"  # Optional
   COMPRESS = True   # Keep True for smaller file sizes
   YOUTUBE_PLAYLIST_ID = None  # Add playlist ID if you want auto-sorting
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

### Google Drive Sync
1. Install Google Drive desktop app
2. Create a folder for your videos
3. Update `DRIVE_SYNC_FOLDER` path in the script

### Video Compression Settings
The script uses these FFmpeg settings by default:
- Resolution: 1920x1080 (scales if needed)
- Video codec: H.264
- Quality: CRF 23 (good balance)
- Audio: AAC 128kbps

To modify, edit the `compress_with_ffmpeg()` function.

## Troubleshooting

### Common Issues

**"FFmpeg not found"**
- Ensure FFmpeg is in your system PATH
- Test with: `ffmpeg -version`

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
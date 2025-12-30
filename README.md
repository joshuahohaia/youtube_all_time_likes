# YouTube All-Time Likes Fetcher

This project allows you to retrieve all your YouTube comments, fetch their real-time like counts using the YouTube Data API v3, and sort them by popularity.

## Features

- **Analyze History**: Parses your Google Takeout comment data.
- **Real-time Likes**: Fetches the latest like counts directly from YouTube.
- **Clickable Report**: Generates a clean HTML report with clickable video links.
- **Auto-Discovery**: Automatically finds your `comments.csv` file.

## Prerequisites

1. **Python 3.8+**
2. **Google Cloud Project** with:
   - **YouTube Data API v3** enabled.
   - **OAuth 2.0 Credentials** (Desktop App) JSON file.

## Setup

1. **Clone the repository**.
2. **Install dependencies**:
   ```bash
   pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client pandas python-dotenv
   ```
3. **Configure Environment**:
   - Create a `.env` file in the root directory.
   - Add your client secret path: `YOUTUBE_CREDENTIALS=client_secret_xxxx.json`.
4. **Get your Data**:
   - Go to [Google Takeout](https://takeout.google.com/).
   - Select **YouTube and YouTube Music** -> **All YouTube data included** -> Select only **my-comments**.
   - **Important for Brand Accounts**: Ensure you are exporting data for the specific channel you want to analyze.
   - Download, extract, and place the `Takeout` folder (or just the `comments.csv` file) inside this project directory.

## Usage

Simply run the script. It will automatically find `comments.csv` in the current folder or subfolders:

```bash
python analyze_takeout.py
```

Or specify the file manually:

```bash
python analyze_takeout.py path/to/comments.csv
```

## Outputs

- **Terminal**: Displays the top 10 most liked comments.
- **`my_comments_with_likes.csv`**: Full raw data export.
- **`my_comments_with_likes.html`**: A formatted report with "Watch Video" links.

## Privacy & Security

- This tool runs locally on your machine.
- Your credentials (`.env`, `token.pickle`, `client_secret.json`) are ignored by Git. **Do not share them.**
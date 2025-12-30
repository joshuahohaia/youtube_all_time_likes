import os
import sys
import argparse
import glob
import re
import pickle
import pandas as pd
from typing import List, Optional
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CREDENTIALS")
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_FILE = "token.pickle"

def get_authenticated_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRETS_FILE or not os.path.exists(CLIENT_SECRETS_FILE):
                raise FileNotFoundError(
                    "Client secrets file not found. Please set YOUTUBE_CREDENTIALS in .env"
                )
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
            
    return build("youtube", "v3", credentials=creds)

def find_comments_file():
    print("Searching for 'comments.csv' in current directory...")
    files = glob.glob("**/comments.csv", recursive=True)
    if files:
        print(f"Found: {files[0]}")
        return files[0]
    return None

def clean_comment_text(text_str):
    if pd.isna(text_str): 
        return ""
    
    try:
        # Normalize: Google Takeout often uses double-double quotes ""text"" inside the CSV
        # converting them to single double quotes makes it standard JSON-like
        normalized = str(text_str).replace('""', '"')
        
        # Regex to capture content inside "text":"..."
        # We look for "text":" matches and capture until the next quote
        # The (.*?) is non-greedy
        matches = re.findall(r'"text":"(.*?)"', normalized)
        
        if matches:
            full_text = " ".join(matches)
            # Unescape newlines
            return full_text.replace('\\n', '\n')
            
    except Exception:
        pass
        
    return text_str

def fetch_comment_likes(youtube, comment_ids):
    comments_data = []
    total = len(comment_ids)
    
    print(f"Fetching details for {total} comments from YouTube API...")
    
    for i in range(0, total, 50):
        batch = comment_ids[i:i+50]
        ids_string = ",".join(batch)
        print(f"  - Batch {i//50 + 1}/{(total//50)+1} ({len(batch)} items)")
        
        try:
            request = youtube.comments().list(
                part="snippet",
                id=ids_string,
                textFormat="plainText"
            )
            response = request.execute()

            for item in response.get("items", []):
                snippet = item["snippet"]
                comments_data.append({
                    "Comment ID": item["id"],
                    "Like Count": int(snippet.get("likeCount", 0)),
                    "Published At": snippet.get("publishedAt"),
                    "Video ID": snippet.get("videoId")
                })
        except HttpError as e:
            print(f"    Warning: API Error on batch: {e}")
        except Exception as e:
            print(f"    Warning: Unexpected error: {e}")
            
    return pd.DataFrame(comments_data)

def generate_html_report(df, filename):
    html_df = df[["Like Count", "Cleaned Text", "Video URL", "Published At"]].copy()
    html_df["Video URL"] = html_df["Video URL"].apply(
        lambda x: f'<a href="{x}" target="_blank">Watch Video</a>'
    )
    pd.set_option('colheader_justify', 'center')
    html_string = f"""
    <html>
    <head>
        <title>YouTube Comment Analysis</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css">
    </head>
    <body class="container mt-5">
        <h1>My Top YouTube Comments</h1>
        <p>Sorted by Likes</p>
        <div class="table-responsive">
            {html_df.to_html(classes='table table-striped table-hover', escape=False, index=False)}
        </div>
    </body>
    </html>
    """
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_string)

def main():
    parser = argparse.ArgumentParser(description="Analyze YouTube Comment History")
    parser.add_argument("csv_path", nargs="?", help="Path to comments.csv from Google Takeout")
    args = parser.parse_args()

    csv_path = args.csv_path
    if not csv_path:
        csv_path = find_comments_file()
        
    if not csv_path or not os.path.exists(csv_path):
        print("Error: 'comments.csv' not found. Please provide the path or run inside the directory.")
        sys.exit(1)

    print(f"Reading: {csv_path}")
    df_takeout = pd.read_csv(csv_path)
    df_takeout['Cleaned Text'] = df_takeout['Comment Text'].apply(clean_comment_text)
    print(f"Parsed {len(df_takeout)} comments.")

    try:
        youtube = get_authenticated_service()
    except Exception as e:
        print(f"Authentication Failed: {e}")
        sys.exit(1)

    comment_ids = df_takeout["Comment ID"].tolist()
    if not comment_ids:
        print("No comments found to process.")
        sys.exit(0)
        
    df_likes = fetch_comment_likes(youtube, comment_ids)

    if not df_likes.empty:
        final_df = pd.merge(df_takeout, df_likes, on="Comment ID", how="inner")
        final_df = final_df.sort_values("Like Count", ascending=False)

        if "Video ID_y" in final_df.columns:
            final_df["Video ID"] = final_df["Video ID_y"]
        
        final_df["Video URL"] = "https://www.youtube.com/watch?v=" + final_df["Video ID"].astype(str)

        display_df = final_df[["Like Count", "Cleaned Text", "Video URL", "Published At"]].copy()
        display_df["Cleaned Text"] = display_df["Cleaned Text"].str.slice(0, 75) + "..."
        
        print("\n" + "="*60)
        print("TOP 10 MOST LIKED COMMENTS")
        print("="*60)
        print(display_df.head(10).to_string(index=False))
        print("\n")

        final_df.to_csv("my_comments_with_likes.csv", index=False)
        generate_html_report(final_df, "my_comments_with_likes.html")
        
        print("Success! Reports generated:")
        print(" -> my_comments_with_likes.csv")
        print(" -> my_comments_with_likes.html")
    else:
        print("Failed to retrieve like counts. Check your API quota or connection.")

if __name__ == "__main__":
    main()

import os
import sys
import argparse
import glob
import re
import pickle
import pathlib
import webbrowser
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
        # (Though pd.read_csv usually handles this, sometimes artifacts remain or we want to be safe)
        normalized = str(text_str).replace('""', '"')
        
        # Robust regex to capture content inside "text":"..." handling escaped quotes
        # Matches "text":" followed by (anything that is NOT a quote OR an escaped char)* until "
        matches = re.findall(r'"text":"((?:[^"\\]|\\.)*)"', normalized)
        
        if matches:
            # Unescape the captured JSON string content (e.g. \" -> ")
            decoded_matches = []
            for m in matches:
                try:
                    # simplistic unescape for common JSON escapes
                    decoded = m.replace(r'\"', '"').replace(r'\\', '\\').replace(r'\/', '/')
                    decoded_matches.append(decoded)
                except:
                    decoded_matches.append(m)
            
            full_text = " ".join(decoded_matches)
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
                    "Likes": int(snippet.get("likeCount", 0)),
                    "Published At": snippet.get("publishedAt"),
                    "Video ID": snippet.get("videoId")
                })
        except HttpError as e:
            print(f"    Warning: API Error on batch: {e}")
        except Exception as e:
            print(f"    Warning: Unexpected error: {e}")
            
    return pd.DataFrame(comments_data)

def fetch_video_titles(youtube, video_ids):
    video_data = {}
    unique_ids = list(set([vid for vid in video_ids if vid])) # Remove empty/None
    total = len(unique_ids)
    
    print(f"Fetching titles for {total} unique videos...")
    
    for i in range(0, total, 50):
        batch = unique_ids[i:i+50]
        ids_string = ",".join(batch)
        
        try:
            request = youtube.videos().list(
                part="snippet",
                id=ids_string
            )
            response = request.execute()

            for item in response.get("items", []):
                video_data[item["id"]] = item["snippet"]["title"]
                
        except Exception as e:
            print(f"    Warning: API Error fetching video titles: {e}")
            
    return video_data

def generate_html_report(df, filename):
    # 'Video' column already contains the HTML link with the Title
    html_df = df[["Likes", "Comment", "Video", "Published At"]].copy()
    
    pd.set_option('colheader_justify', 'center')
    
    table_html = html_df.to_html(classes='table table-striped table-hover', escape=False, index=False, table_id="commentsTable")
    
    html_string = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>YouTube Comment Analysis</title>
        <!-- Bootstrap 5 CSS -->
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css">
        <!-- DataTables CSS -->
        <link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/dataTables.bootstrap5.min.css">
        <style>
            body {{
                background-color: #f8f9fa;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            .container {{
                background-color: white;
                padding: 30px;
                border-radius: 10px;
                margin-top: 50px;
                margin-bottom: 50px;
            }}
            h1 {{
                color: #212529;
                text-align: center;
                margin-bottom: 10px;
                font-weight: bold;
            }}
            p.subtitle {{
                text-align: center;
                color: #6c757d;
                margin-bottom: 30px;
            }}
            table.dataTable thead th {{
                background-color: #212529;
                color: white;
            }}
            .dataTables_filter input {{
                border-radius: 20px;
                padding: 5px 15px;
            }}
            .dataTables_wrapper {{
                margin-top: 20px;
            }}
            /* Extra padding to prevent focus glow clipping */
            div.dataTables_wrapper div.dataTables_filter, 
            div.dataTables_wrapper div.dataTables_length {{
                margin-bottom: 10px;
                padding: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>My Top YouTube Comments</h1>
            <div class="table-responsive">
                {table_html}
            </div>
        </div>

        <!-- jQuery -->
        <script src="https://code.jquery.com/jquery-3.5.1.js"></script>
        <!-- DataTables JS -->
        <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.4/js/dataTables.bootstrap5.min.js"></script>
        
        <script>
            $(document).ready(function () {{
                $('#commentsTable').DataTable({{
                    "order": [[ 0, "desc" ]], // Sort by Likes (1st column) descending by default
                    "pageLength": 25,
                    "language": {{
                        "search": "Search:"
                    }}
                }});
            }});
        </script>
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
    df_takeout['Comment'] = df_takeout['Comment Text'].apply(clean_comment_text)
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
        final_df = final_df.sort_values("Likes", ascending=False)

        # Fix Video ID Merging Logic
        # We might have Video ID_x (Takeout) and Video ID_y (API)
        # We prefer API (y), but if null, use Takeout (x)
        if "Video ID_y" in final_df.columns and "Video ID_x" in final_df.columns:
            final_df["Video ID"] = final_df["Video ID_y"].fillna(final_df["Video ID_x"])
        elif "Video ID_y" in final_df.columns:
            final_df["Video ID"] = final_df["Video ID_y"]
        elif "Video ID_x" in final_df.columns:
            final_df["Video ID"] = final_df["Video ID_x"]
        
        # Ensure we have strings and drop NaNs for URL generation
        final_df["Video ID"] = final_df["Video ID"].fillna("")
        
        # Fetch Video Titles
        video_ids = final_df["Video ID"].tolist()
        video_titles_map = fetch_video_titles(youtube, video_ids)
        final_df["Video Title"] = final_df["Video ID"].map(video_titles_map).fillna("Unknown Video")

        final_df["Video"] = final_df.apply(
            lambda x: f'<a href="https://www.youtube.com/watch?v={x["Video ID"]}" target="_blank">{x["Video Title"]}</a>', axis=1
        )

        # Format Published At
        if "Published At" in final_df.columns:
            final_df["Published At"] = pd.to_datetime(final_df["Published At"]).dt.strftime("%Y-%m-%d %H:%M")

        display_df = final_df[["Likes", "Comment", "Video Title", "Published At"]].copy()
        
        print("\n" + "="*60)
        print("TOP 3 MOST LIKED COMMENTS")
        print("="*60)
        # Set pandas options to show full text in terminal without truncation
        with pd.option_context('display.max_colwidth', None, 'display.width', 2000):
            print(display_df.head(3).to_string(index=False))
        print("\n")

        final_df.to_csv("my_comments_with_likes.csv", index=False)
        generate_html_report(final_df, "my_comments_with_likes.html")
        
        print("Success! Reports generated:")
        print(" -> my_comments_with_likes.csv")
        
        uri = pathlib.Path("my_comments_with_likes.html").resolve().as_uri()
        print(f" -> {uri}")
        webbrowser.open(uri)
    else:
        print("Failed to retrieve like counts. Check your API quota or connection.")

if __name__ == "__main__":
    main()

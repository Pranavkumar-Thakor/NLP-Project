from flask import Flask, render_template, request, send_from_directory
import os
import boto3
import moviepy as mp
import whisper
import re

app = Flask(__name__)

# AWS S3 Configuration
S3_BUCKET = "pranavkumar-thakor-1264937"
s3_client = boto3.client("s3")

# Local storage directories
LOCAL_VIDEO_DIR = "dashboard_videos"
LOCAL_AUDIO_DIR = "dashboard_audios"
LOCAL_TRANSCRIPTS_DIR = "dashboard_transcriptions"
LOCAL_NORMALIZED_TEXT_DIR = "dashboard_normalized_text"
LOCAL_KEY_PHRASES_DIR = "dashboard_key_phrases"

# Ensure directories exist
for directory in [LOCAL_VIDEO_DIR, LOCAL_AUDIO_DIR, LOCAL_TRANSCRIPTS_DIR, LOCAL_NORMALIZED_TEXT_DIR, LOCAL_KEY_PHRASES_DIR]:
    os.makedirs(directory, exist_ok=True)

# Upload video
@app.route("/upload", methods=["POST"])
def upload_video():
    if "file" not in request.files:
        return "No file uploaded", 400
    file = request.files["file"]
    file_path = os.path.join(LOCAL_VIDEO_DIR, file.filename)
    file.save(file_path)
    return "Video uploaded successfully", 200

# Extract audio
@app.route("/extract_audio/<filename>")
def extract_audio(filename):
    video_path = os.path.join(LOCAL_VIDEO_DIR, filename)
    audio_filename = filename.replace(".mp4", ".mp3")
    audio_path = os.path.join(LOCAL_AUDIO_DIR, audio_filename)
    
    video = mp.VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path)
    return "Audio extracted successfully", 200

# Transcribe audio
@app.route("/transcribe/<filename>")
def transcribe(filename):
    audio_filename = filename.replace(".mp4", ".mp3")
    audio_path = os.path.join(LOCAL_AUDIO_DIR, audio_filename)
    transcript_filename = filename.replace(".mp4", ".txt")
    transcript_path = os.path.join(LOCAL_TRANSCRIPTS_DIR, transcript_filename)
    
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    
    with open(transcript_path, "w") as f:
        f.write(result["text"])
    
    return "Transcription completed", 200

# Normalize text
@app.route("/normalize/<filename>")
def normalize_text(filename):
    transcript_filename = filename.replace(".mp4", ".txt")
    transcript_path = os.path.join(LOCAL_TRANSCRIPTS_DIR, transcript_filename)
    normalized_filename = filename.replace(".mp4", "_normalized.txt")
    normalized_path = os.path.join(LOCAL_NORMALIZED_TEXT_DIR, normalized_filename)
    
    with open(transcript_path, "r") as f:
        text = f.read()
    normalized_text = text.lower()
    normalized_text = re.sub(r"[^a-z0-9 ]", "", normalized_text)
    
    with open(normalized_path, "w") as f:
        f.write(normalized_text)
    
    return "Text normalization completed", 200

# Extract key phrases
@app.route("/extract_key_phrases/<filename>")
def extract_key_phrases(filename):
    normalized_filename = filename.replace(".mp4", "_normalized.txt")
    normalized_path = os.path.join(LOCAL_NORMALIZED_TEXT_DIR, normalized_filename)
    key_phrases_filename = filename.replace(".mp4", "_key_phrases.txt")
    key_phrases_path = os.path.join(LOCAL_KEY_PHRASES_DIR, key_phrases_filename)
    
    with open(normalized_path, "r") as f:
        text = f.read()
    
    words = text.split()
    key_phrases = set([word for word in words if len(word) > 4])
    
    with open(key_phrases_path, "w") as f:
        f.write("\n".join(key_phrases))
    
    return "Key phrase extraction completed", 200

# Search functionality
@app.route("/search", methods=["GET"])
def search():
    keyword = request.args.get("query", "").lower()
    if not keyword:
        return "No keyword provided", 400
    
    s3_paginator = s3_client.get_paginator("list_objects_v2")
    s3_key_phrases_prefix = "key_phrases/"
    matching_videos = []
    
    for page in s3_paginator.paginate(Bucket=S3_BUCKET, Prefix=s3_key_phrases_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            file_content = s3_client.get_object(Bucket=S3_BUCKET, Key=key)["Body"].read().decode("utf-8")
            if keyword in file_content:
                video_filename = os.path.basename(key).replace("_key_phrases.txt", ".mp4")
                video_url = f"https://{S3_BUCKET}.s3.amazonaws.com/raw_videos/{video_filename}"
                matching_videos.append(video_url)
    
    return {"videos": matching_videos}, 200

# Run Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


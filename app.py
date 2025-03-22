from flask import Flask, request, render_template, jsonify
import boto3
import os
import moviepy as mp
import whisper
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import json


nltk.download('punkt')
nltk.download('stopwords')

app = Flask(__name__)

# AWS S3 Configuration
bucket_name = "pranavkumar-thakor-1264937"
videos_folder = "raw_videos/"
audio_folder = "audio/"
transcription_folder = "transcriptions/"
normalized_folder = "normalized_text/"
key_phrases_folder = "key_phrases/"

s3_client = boto3.client('s3')

def upload_to_s3(file_path, s3_key):
    """Uploads a file to S3."""
    s3_client.upload_file(file_path, bucket_name, s3_key)

def transcribe_audio(audio_path):
    """Transcribe audio using Whisper."""
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result['text']

def normalize_text(text):
    """Remove stopwords and normalize text."""
    tokens = word_tokenize(text.lower())
    stop_words = set(stopwords.words('english'))
    return ' '.join([word for word in tokens if word.isalnum() and word not in stop_words])

def extract_key_phrases(text):
    """Extract key phrases (dummy implementation)."""
    words = word_tokenize(text)
    return list(set(words[:10]))  # Mock extraction of key phrases

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_video():
    file = request.files['file']
    if file:
        file_path = os.path.join("uploads", file.filename)
        file.save(file_path)
        
        # Upload to S3
        s3_key = videos_folder + file.filename
        upload_to_s3(file_path, s3_key)
        os.remove(file_path)
        return "Video uploaded successfully!"
    return "Failed to upload."

@app.route('/transcribe', methods=['POST'])
def transcribe():
    file_name = request.json['file_name']
    video_key = videos_folder + file_name
    audio_key = audio_folder + file_name.replace('.mp4', '.wav')
    
    # Download video
    local_video = f"/tmp/{file_name}"
    s3_client.download_file(bucket_name, video_key, local_video)
    
    # Convert to audio
    clip = mp.VideoFileClip(local_video)
    audio_path = f"/tmp/{file_name.replace('.mp4', '.wav')}"
    clip.audio.write_audiofile(audio_path)
    
    # Upload audio to S3
    upload_to_s3(audio_path, audio_key)
    
    # Transcribe
    transcription = transcribe_audio(audio_path)
    trans_s3_key = transcription_folder + file_name.replace('.mp4', '.txt')
    with open("/tmp/transcription.txt", "w") as f:
        f.write(transcription)
    upload_to_s3("/tmp/transcription.txt", trans_s3_key)
    
    return "Transcription completed!"

@app.route('/normalize', methods=['POST'])
def normalize():
    file_name = request.json['file_name'].replace('.mp4', '.txt')
    s3_transcription = transcription_folder + file_name
    local_transcription = f"/tmp/{file_name}"
    
    s3_client.download_file(bucket_name, s3_transcription, local_transcription)
    
    with open(local_transcription, "r") as f:
        text = f.read()
    normalized_text = normalize_text(text)
    
    # Save & Upload
    with open("/tmp/normalized.txt", "w") as f:
        f.write(normalized_text)
    upload_to_s3("/tmp/normalized.txt", normalized_folder + file_name)
    return "Normalization complete!"

@app.route('/extract', methods=['POST'])
def extract():
    file_name = request.json['file_name'].replace('.mp4', '.txt')
    s3_transcription = transcription_folder + file_name
    local_transcription = f"/tmp/{file_name}"
    
    s3_client.download_file(bucket_name, s3_transcription, local_transcription)
    
    with open(local_transcription, "r") as f:
        text = f.read()
    key_phrases = extract_key_phrases(text)
    
    # Save & Upload
    with open("/tmp/key_phrases.json", "w") as f:
        json.dump(key_phrases, f)
    upload_to_s3("/tmp/key_phrases.json", key_phrases_folder + file_name.replace('.txt', '.json'))
    return "Key phrases extracted!"

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    
    # List transcription files
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=transcription_folder)
    if 'Contents' not in response:
        return "No transcriptions found."
    
    for obj in response['Contents']:
        file_key = obj['Key']
        local_file = f"/tmp/{os.path.basename(file_key)}"
        s3_client.download_file(bucket_name, file_key, local_file)
        
        with open(local_file, "r") as f:
            text = f.read()
        
        if query.lower() in text.lower():
            video_file = os.path.basename(file_key).replace('.txt', '.mp4')
            return jsonify({"video": video_file})
    
    return "No matching video found."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

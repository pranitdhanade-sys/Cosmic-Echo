import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
import base64
import json
import re

# --- 1. SETUP ---
basedir = os.path.abspath(os.path.dirname(__file__))  
env_path = os.path.join(basedir, '.env')
load_dotenv(env_path)

# Initialize Flask
app = Flask(__name__, static_folder='templates', static_url_path='')

# Load Keys
gemini_key = os.getenv("GEMINI_API_KEY")
murf_key = os.getenv("MURF_API_KEY")
deepgram_key = os.getenv("DEEPGRAM_API_KEY")

print(f"DEBUG: KEYS -> G:{bool(gemini_key)} M:{bool(murf_key)} D:{bool(deepgram_key)}")

if gemini_key:
    genai.configure(api_key=gemini_key)

# --- CONSTANTS ---
MURF_STREAM_URL = "https://api.murf.ai/v1/speech/stream"
DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true"

# --- 2. ROUTES --- 
@app.route('/')
@app.route('/homepage.html')
def home(): return render_template('homepage.html')

@app.route('/astronomy.html')
def astronomy(): return render_template('astronomy.html')

@app.route('/blogpage.html')
def blog(): return render_template('blogpage.html')

@app.route('/community.html')
def community(): return render_template('community.html')

@app.route('/missions.html')
def missions(): return render_template('missions.html')

@app.route('/pricing.html')
def pricing(): return render_template('pricing.html')

@app.route('/resources.html')
def resources(): return render_template('resources.html')

@app.route('/login.html')
def login_page(): return render_template('login.html')

# --- 3. API ENDPOINTS ---

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    return jsonify({"status": "success", "user": data.get('email').split('@')[0], "message": "Login Successful"})

@app.route('/send-calendar-event', methods=['POST'])
def newsletter():
    return jsonify({"status": "success", "message": "Subscribed!"})

@app.route('/send-pdf', methods=['POST'])
def send_pdf():
    return jsonify({"status": "success", "message": "Guide sent successfully!"})

@app.route('/process_audio', methods=['POST'])
def process_audio():
    if 'audio_data' not in request.files:
        return jsonify({"error": "No audio"}), 400
    
    audio_file = request.files['audio_data']
    image_file = request.files.get('image_data')
    
    image_part = None
    if image_file:
        print("Processing Vision Data...")
        image_bytes = image_file.read()
        image_part = {"mime_type": "image/jpeg", "data": image_bytes}

    # A. Transcribe (Deepgram) 
    transcript = ""
    try:
        audio_file.seek(0)
        # Using audio/* to handle WebM/WAV mismatch automatically
        dg_resp = requests.post(
            DEEPGRAM_API_URL, 
            headers={"Authorization": f"Token {deepgram_key}", "Content-Type": "audio/*"},
            data=audio_file.read()
        )
        
        if dg_resp.status_code != 200: 
            # If Deepgram fails (internet issue), log it but don't crash
            print(f"Deepgram Error: {dg_resp.text}")
        else:
            data = dg_resp.json()
            if 'results' in data and 'channels' in data['results']:
                alt = data['results']['channels'][0]['alternatives'][0]
                transcript = alt.get('transcript', '')
        
        print(f"User Transcript: {transcript}")
            
    except Exception as e:
        print(f"Transcription Failed: {e}")
        # Proceed even if transcription fails, so we can tell the user something went wrong via Voice

    # B. Brain (Gemini)
    ai_text = ""
    sonification_data = []

    # LOGIC FIX: If silence and no image, don't return early. Generate a "What?" response.
    if not transcript and not image_part:
        ai_text = "I'm sorry, I didn't catch that. Could you please speak closer to the microphone?"
    else:
        # Only call Gemini if we have input
        models_config = ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro']
        
        base_prompt = (
            "You are 'Astro-Brief', an expert astrophysicist. "
            "User Input: " + transcript + "\n"
            "INSTRUCTIONS:\n"
            "1. VISUALS: If an image is provided, explain it clearly in 2 sentences.\n"
            "2. DATA: If the topic involves stats, generate 5-10 integers (0-100) for sonification.\n"
            "3. FORMAT: You MUST return valid JSON. Example: {\"text\": \"This is Jupiter...\", \"data\": [45, 88, 12]}\n"
            "If you cannot produce JSON, just provide the text explanation."
        )

        for model_name in models_config:
            try:
                model = genai.GenerativeModel(model_name)
                content = [base_prompt]
                if image_part: 
                    content.append(image_part)
                
                response = model.generate_content(content)
                raw_text = response.text.strip()
                clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                
                try:
                    res_json = json.loads(clean_text)
                    ai_text = res_json.get("text", "Analysis complete.")
                    sonification_data = res_json.get("data", [])
                except json.JSONDecodeError:
                    ai_text = clean_text
                    sonification_data = []
                
                if ai_text: break 
            except Exception as e:
                print(f"Gemini Error: {e}")
                continue
    
    # If Gemini failed completely
    if not ai_text:
        ai_text = "I am having trouble connecting to the stars right now. Please try again."

    # Clean text for Murf
    import re
    ai_text_clean = re.sub(r'[#*]', '', ai_text)
    print(f"AI Response to User: {ai_text_clean}")

    # C. Voice (Murf Falcon Streaming)
    audio_b64 = None
    try:
        payload = {
            "voiceId": "en-US-ken",
            "text": ai_text_clean,
            "format": "MP3",
            "model": "FALCON"
        }
        
        headers = {"Content-Type": "application/json", "api-key": murf_key}

        murf_resp = requests.post(MURF_STREAM_URL, json=payload, headers=headers, stream=True)

        if murf_resp.status_code == 200:
            audio_content = b""
            for chunk in murf_resp.iter_content(chunk_size=1024):
                if chunk: audio_content += chunk
            
            if audio_content:
                audio_b64 = base64.b64encode(audio_content).decode('utf-8')
        else:
            print(f"Murf API Error: {murf_resp.status_code} - {murf_resp.text}")

    except Exception as e:
        print(f"Murf Exception: {e}")

    return jsonify({
        "user_text": transcript,
        "ai_text": ai_text,
        "audio_base64": audio_b64,
        "sonification_data": sonification_data
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
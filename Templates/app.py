import os
import google.generativeai as genai
from flask import Flask,  render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv
import requests
import base64
import json

# --- 1. SETUP ---
basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')
load_dotenv(env_path)

# Note the static_url_path='' allows loading images like /logo.png instead of /static/logo.png
# CHANGE THIS LINE:
app = Flask(__name__, static_folder='templates', static_url_path='')

gemini_key = os.getenv("GEMINI_API_KEY")
murf_key = os.getenv("MURF_API_KEY")
deepgram_key = os.getenv("DEEPGRAM_API_KEY")

print(f"DEBUG: KEYS -> G:{bool(gemini_key)} M:{bool(murf_key)} D:{bool(deepgram_key)}")

if gemini_key:
    genai.configure(api_key=gemini_key)
 
MURF_API_URL = "https://api.murf.ai/v1/speech/generate"
DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true"

# --- 2. ROUTES FOR ALL PAGES ---
@app.route('/')
@app.route('/homepage.html')
def home():
    return render_template('homepage.html')

@app.route('/astronomy.html') 
def astronomy():
    return render_template('astronomy.html')

@app.route('/blogpage.html')
def blog():
    return render_template('blogpage.html')

@app.route('/community.html')
def community():
    return render_template('community.html')

@app.route('/missions.html')
def missions():
    return render_template('missions.html') # Ensure filename matches (Missions.html vs missions.html)

@app.route('/pricing.html')
def pricing():
    return render_template('pricing.html')

@app.route('/resources.html')
def resources():
    return render_template('resources.html')

@app.route('/login.html')
def login_page():
    return render_template('login.html')

# --- 3. API ENDPOINTS ---

# Mock Auth
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    return jsonify({"status": "success", "user": data.get('email').split('@')[0], "message": "Login Successful"})

# Mock Newsletter
@app.route('/send-calendar-event', methods=['POST'])
def newsletter():
    return jsonify({"status": "success", "message": "Subscribed!"})

@app.route('/process_audio', methods=['POST'])
def process_audio():
    if 'audio_data' not in request.files: return jsonify({"error": "No audio"}), 400
    
    audio_file = request.files['audio_data']
    image_file = request.files.get('image_data')
    
    image_part = None
    if image_file:
        print("Processing Vision Data...")
        image_part = {"mime_type": "image/jpeg", "data": image_file.read()}

    # A. Transcribe (Deepgram)
    try:
        audio_file.seek(0)
        dg_resp = requests.post(
            DEEPGRAM_API_URL, 
            headers={"Authorization": f"Token {deepgram_key}", "Content-Type": "audio/wav"},
            data=audio_file.read()
        )
        if dg_resp.status_code != 200: raise Exception(dg_resp.text)
        transcript = dg_resp.json()['results']['channels'][0]['alternatives'][0]['transcript']
        print(f"User: {transcript}")
        if not transcript: return jsonify({"text": "Silence.", "data": []})
    except Exception as e:
        print(f"Deepgram Error: {e}")
        return jsonify({"error": "Audio Error"}), 500

    # B. Brain (Gemini)
    # Quick logic to use available models
    models_config = ['gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-pro-latest', 'gemini-2.0-flash-exp']
    ai_text = "Error connecting to AI."
    sonification_data = []
    
    base_prompt = (
        "You are 'Astro-Brief'. "
        "1. VISUALS: Give a 1-sentence summary. "
        "2. DATA: If data/trends exist, generate 5-10 integers (0-100). "
        "RETURN RAW JSON: {\"text\": \"...\", \"data\": [10, 20...]}"
    )

    for model_name in models_config:
        try:
            model = genai.GenerativeModel(model_name)
            content = [base_prompt, "\nUser: " + transcript]
            if image_part: content.append(image_part)
            
            response = model.generate_content(content)
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            res_json = json.loads(clean_text)
            ai_text = res_json.get("text")
            sonification_data = res_json.get("data", [])
            break
        except: continue

    # C. Voice (Murf)
    audio_b64 = None
    try:
        murf_resp = requests.post(
            MURF_API_URL, 
            json={"voiceId": "en-US-cooper", "style": "Promo", "text": ai_text, "format": "MP3"},
            headers={"Content-Type": "application/json", "api-key": murf_key}
        )
        audio_url = murf_resp.json().get("audioFile")
        if audio_url:
            audio_b64 = base64.b64encode(requests.get(audio_url).content).decode('utf-8')
    except Exception as e:
        print(f"Murf Error: {e}")

    return jsonify({
        "user_text": transcript,
        "ai_text": ai_text,
        "audio_base64": audio_b64,
        "sonification_data": sonification_data
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
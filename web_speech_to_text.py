from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import base64
import numpy as np
import torch
import whisper
import tempfile
import io
from datetime import datetime
import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, static_folder='static')

transcriber = None

class WhisperTranscriber:
    def __init__(self, model_name="medium"):
        self.model_name = model_name
        self.model = None
        self.is_loaded = False
        logging.debug(f"Loading model: {model_name}")
        self.load_model()
        logging.debug("Model loaded successfully.")
        
    def load_model(self):
        if not self.is_loaded:
            logging.debug("Loading Whisper model...")
            self.model = whisper.load_model(self.model_name)
            self.is_loaded = True
            logging.debug("Whisper model loaded.")
            
    def transcribe_audio(self, audio_data, language=None):
        if not self.is_loaded:
            self.load_model()
        
        try:
            import wave
            import array
            import struct
            
            logging.debug("Preparing audio data for transcription...")
            rate = 16000
            
            audio_array = np.frombuffer(audio_data, dtype=np.uint8)
            audio_array = audio_array.astype(np.float32) / 255.0 - 0.5
            audio_array = whisper.pad_or_trim(audio_array)
            
            logging.debug("Generating mel spectrogram...")
            # Gelişmiş ses özellikleri için daha kesin ayarlar
            options = {
                "fp16": False,
                "language": "tr",  # Kesinlikle Türkçe olarak ayarla
                "task": "transcribe",
                "beam_size": 5,     # Daha iyi sonuçlar için beam arama
                "best_of": 5,       # En iyi sonuçları bulmak için
                "temperature": 0,    # Sıfır sıcaklık - en yüksek güvenle tahmin
                "suppress_tokens": "-1",  # Tokenları bastırmayı kapat
                "condition_on_previous_text": False,  # Önceki metin şartını kapat
                "initial_prompt": "Bu bir Türkçe ses kaydı transkriptidir."  # Bu önemli ipucu modele yardımcı olur
            }
                
            logging.debug("Starting transcription process...")
            result = self.model.transcribe(audio_array, **options)
            logging.debug("Transcription completed.")
            
            return result["text"]
        except Exception as e:
            import traceback
            logging.error(f"Error in transcribe_audio: {str(e)}")
            logging.error(traceback.format_exc())
            raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/transcribe', methods=['POST'])
def transcribe():
    global transcriber
    
    if transcriber is None:
        transcriber = WhisperTranscriber("base")
    
    if 'audio' not in request.json:
        return jsonify({"error": "No audio data provided"}), 400
    
    try:
        audio_parts = request.json['audio'].split(',', 1)
        if len(audio_parts) < 2:
            return jsonify({"error": "Invalid audio data format"}), 400
            
        audio_data = base64.b64decode(audio_parts[1])
        language = request.json.get('language')
        model = request.json.get('model', 'base')
        
        if model != transcriber.model_name:
            transcriber = WhisperTranscriber(model)
        
        text = transcriber.transcribe_audio(audio_data, language)
        return jsonify({"text": text})
    except Exception as e:
        import traceback
        logging.error(f"Error in transcribe route: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/models', methods=['GET'])
def get_models():
    return jsonify({"models": ["tiny", "base", "small", "medium"]})

if __name__ == '__main__':
    if not os.path.exists('static'):
        os.makedirs('static')
    if not os.path.exists('templates'):
        os.makedirs('templates')
    app.run(debug=True, host='0.0.0.0', port=5000)

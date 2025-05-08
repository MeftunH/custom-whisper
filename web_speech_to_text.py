from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import base64
import numpy as np
import torch
import whisper
import tempfile
import io
from datetime import datetime

app = Flask(__name__, static_folder='static')

transcriber = None

class WhisperTranscriber:
    def __init__(self, model_name="tiny"):
        self.model_name = model_name
        self.model = None
        self.is_loaded = False
        self.load_model()
        
    def load_model(self):
        if not self.is_loaded:
            self.model = whisper.load_model(self.model_name)
            self.is_loaded = True
            
    def transcribe_audio(self, audio_data, language=None):
        if not self.is_loaded:
            self.load_model()
        
        try:
            import wave
            import array
            import struct
            
            rate = 16000
            
            audio_array = np.frombuffer(audio_data, dtype=np.uint8)
            audio_array = audio_array.astype(np.float32) / 255.0 - 0.5
            audio_array = whisper.pad_or_trim(audio_array)
            
            mel = whisper.log_mel_spectrogram(audio_array).to(self.model.device)
            
            options = {}
            if language:
                options["language"] = language
                
            if language == "tr":
                options["language"] = "tr"
                options["task"] = "transcribe"
                
            decode_options = whisper.DecodingOptions(**options)
            result = whisper.decode(self.model, mel, decode_options)
            
            return result.text
        except Exception as e:
            import traceback
            print(f"Error in transcribe_audio: {str(e)}")
            print(traceback.format_exc())
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
        print(f"Error in transcribe route: {str(e)}")
        print(traceback.format_exc())
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

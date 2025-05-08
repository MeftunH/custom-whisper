#!/usr/bin/env python3
import sys
import os
import threading
import queue
import tempfile
import time
import numpy as np
import torch
import whisper
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QComboBox, 
                            QTextEdit, QFrame, QSlider)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette
import sounddevice as sd

class AudioRecorder:
    def __init__(self, sample_rate=16000, chunk_size=1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.audio_buffer = []
        self.buffer_duration = 3
        self.buffer_samples = int(self.sample_rate * self.buffer_duration)
        
    def callback(self, indata, frames, time, status):
        if status:
            print(f"Status: {status}")
        if self.is_recording:
            self.audio_queue.put(indata.copy())
            self.audio_buffer.append(indata.copy())
            
            buffer_length = sum(len(chunk) for chunk in self.audio_buffer)
            while buffer_length > self.buffer_samples:
                removed = self.audio_buffer.pop(0)
                buffer_length -= len(removed)
    
    def start(self):
        self.is_recording = True
        self.stream = sd.InputStream(
            channels=1,
            samplerate=self.sample_rate,
            callback=self.callback,
            blocksize=self.chunk_size,
            dtype='float32'
        )
        self.stream.start()
        
    def stop(self):
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        self.is_recording = False
        
    def get_audio_data(self):
        audio_data = []
        while not self.audio_queue.empty():
            audio_data.append(self.audio_queue.get())
        
        if not audio_data:
            return None
            
        return np.concatenate(audio_data, axis=0).flatten()
    
    def get_buffer_audio(self):
        if not self.audio_buffer:
            return None
        return np.concatenate(self.audio_buffer, axis=0).flatten()


class WhisperTranscriber:
    def __init__(self, model_name="base"):
        self.model_name = model_name
        self.model = None
        self.is_loaded = False
        
    def load_model(self):
        if not self.is_loaded:
            self.model = whisper.load_model(self.model_name)
            self.is_loaded = True
            
    def transcribe_audio(self, audio_data, sample_rate=16000, language=None):
        if not self.is_loaded:
            self.load_model()
            
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name
            
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        audio = whisper.pad_or_trim(audio_data)
        
        mel = whisper.log_mel_spectrogram(audio).to(self.model.device)
        
        options = whisper.DecodingOptions(
            language=language if language else None,
            fp16=torch.cuda.is_available()
        )
        
        result = whisper.decode(self.model, mel, options)
        return result.text


class ModernTranscriberUI(QMainWindow):
    update_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerçek Zamanlı Konuşma Tanıma")
        self.setMinimumSize(800, 600)
        
        self.recorder = AudioRecorder()
        self.transcriber = WhisperTranscriber()
        self.is_transcribing = False
        self.transcription_thread = None
        self.language = None
        
        self.setup_ui()
        
        self.update_signal.connect(self.update_transcription)
        
    def setup_ui(self):
        self.set_dark_theme()
        
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        title_label = QLabel("Gerçek Zamanlı Konuşma Tanıma")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #4FC3F7; margin: 10px;")
        main_layout.addWidget(title_label)
        
        model_layout = QHBoxLayout()
        model_label = QLabel("Model:")
        model_label.setFont(QFont("Arial", 12))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large", "turbo"])
        self.model_combo.setCurrentText("base")
        self.model_combo.currentTextChanged.connect(self.change_model)
        
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        
        lang_label = QLabel("Dil:")
        lang_label.setFont(QFont("Arial", 12))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Otomatik", "Türkçe", "English", "Español", "Français", "Deutsch"])
        self.lang_combo.setCurrentText("Otomatik")
        self.lang_combo.currentTextChanged.connect(self.change_language)
        
        model_layout.addWidget(lang_label)
        model_layout.addWidget(self.lang_combo)
        
        main_layout.addLayout(model_layout)
        
        self.transcription_text = QTextEdit()
        self.transcription_text.setReadOnly(True)
        self.transcription_text.setFont(QFont("Arial", 12))
        self.transcription_text.setStyleSheet("""
            QTextEdit {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3F3F46;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        main_layout.addWidget(self.transcription_text)
        
        self.status_bar = QLabel("Hazır")
        self.status_bar.setFont(QFont("Arial", 10))
        self.status_bar.setStyleSheet("color: #4FC3F7; padding: 5px;")
        main_layout.addWidget(self.status_bar)
        
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Kaydı Başlat")
        self.start_button.setFont(QFont("Arial", 12))
        self.start_button.clicked.connect(self.toggle_recording)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.clear_button = QPushButton("Temizle")
        self.clear_button.setFont(QFont("Arial", 12))
        self.clear_button.clicked.connect(self.clear_transcription)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border-radius: 5px;
                padding: 10px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        
        button_layout.addStretch()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        
        self.status_bar.setText("Model yükleniyor...")
        threading.Thread(target=self.load_model_thread).start()
    
    def set_dark_theme(self):
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(45, 45, 48))
        dark_palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Base, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.AlternateBase, QColor(45, 45, 48))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Button, QColor(45, 45, 48))
        dark_palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
        self.setPalette(dark_palette)
    
    def load_model_thread(self):
        self.transcriber.load_model()
        self.update_signal.emit("Model yüklendi. Kayda başlayabilirsiniz.")
    
    def change_model(self, model_name):
        if self.is_transcribing:
            return
            
        self.transcriber = WhisperTranscriber(model_name)
        self.status_bar.setText(f"{model_name} modeli yükleniyor...")
        threading.Thread(target=self.load_model_thread).start()
    
    def change_language(self, language):
        if language == "Otomatik":
            self.language = None
        elif language == "Türkçe":
            self.language = "tr"
        elif language == "English":
            self.language = "en"
        elif language == "Español":
            self.language = "es"
        elif language == "Français":
            self.language = "fr"
        elif language == "Deutsch":
            self.language = "de"
    
    def toggle_recording(self):
        if not self.is_transcribing:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        self.is_transcribing = True
        self.start_button.setText("Kaydı Durdur")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border-radius: 5px;
                padding: 10px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.status_bar.setText("Kayıt yapılıyor...")
        
        self.recorder.start()
        
        self.transcription_thread = threading.Thread(target=self.transcribe_loop)
        self.transcription_thread.daemon = True
        self.transcription_thread.start()
    
    def stop_recording(self):
        self.is_transcribing = False
        self.start_button.setText("Kaydı Başlat")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.status_bar.setText("Kayıt durduruldu.")
        
        self.recorder.stop()
        
        audio_data = self.recorder.get_buffer_audio()
        if audio_data is not None and len(audio_data) > 0:
            text = self.transcriber.transcribe_audio(audio_data, language=self.language)
            self.update_signal.emit(text)
    
    def transcribe_loop(self):
        while self.is_transcribing:
            audio_data = self.recorder.get_buffer_audio()
            
            if audio_data is not None and len(audio_data) > 0:
                text = self.transcriber.transcribe_audio(audio_data, language=self.language)
                self.update_signal.emit(text)
            
            time.sleep(2)
    
    def update_transcription(self, text):
        if text.startswith("Model yüklendi"):
            self.status_bar.setText(text)
            return
            
        if text and text.strip():
            current_text = self.transcription_text.toPlainText()
            if not current_text or current_text.isspace():
                self.transcription_text.setText(text)
            else:
                if not current_text.strip().endswith(text.strip()):
                    self.transcription_text.setText(f"{current_text}\n{text}")
            
            cursor = self.transcription_text.textCursor()
            cursor.movePosition(cursor.End)
            self.transcription_text.setTextCursor(cursor)
    
    def clear_transcription(self):
        self.transcription_text.clear()
    
    def closeEvent(self, event):
        self.is_transcribing = False
        self.recorder.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernTranscriberUI()
    window.show()
    sys.exit(app.exec_())

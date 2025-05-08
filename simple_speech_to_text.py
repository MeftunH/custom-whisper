#!/usr/bin/env python3
import threading
import queue
import time
import numpy as np
import torch
import whisper
import tkinter as tk
from tkinter import ttk, scrolledtext
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
            
    def transcribe_audio(self, audio_data, language=None):
        if not self.is_loaded:
            self.load_model()
            
        audio = whisper.pad_or_trim(audio_data)
        
        mel = whisper.log_mel_spectrogram(audio).to(self.model.device)
        
        options = whisper.DecodingOptions(
            language=language if language else None,
            fp16=torch.cuda.is_available()
        )
        
        result = whisper.decode(self.model, mel, options)
        return result.text

class SpeechToTextApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Konuşma Tanıma Uygulaması")
        self.root.geometry("800x600")
        self.root.configure(bg="#2D2D30")
        
        self.recorder = AudioRecorder()
        self.transcriber = WhisperTranscriber()
        self.is_transcribing = False
        self.transcription_thread = None
        self.language = None
        
        self.setup_ui()
        
    def setup_ui(self):
        style = ttk.Style()
        style.configure("TFrame", background="#2D2D30")
        style.configure("TButton", font=("Arial", 12))
        style.configure("TLabel", font=("Arial", 12), background="#2D2D30", foreground="white")
        style.configure("TCombobox", font=("Arial", 12))
        
        main_frame = ttk.Frame(self.root, padding=10, style="TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text="Gerçek Zamanlı Konuşma Tanıma", font=("Arial", 18, "bold"), foreground="#4FC3F7")
        title_label.pack(pady=10)
        
        control_frame = ttk.Frame(main_frame, style="TFrame")
        control_frame.pack(fill=tk.X, pady=10)
        
        model_label = ttk.Label(control_frame, text="Model:")
        model_label.pack(side=tk.LEFT, padx=5)
        
        self.model_var = tk.StringVar(value="base")
        model_combo = ttk.Combobox(control_frame, textvariable=self.model_var, values=["tiny", "base", "small", "medium", "large"])
        model_combo.pack(side=tk.LEFT, padx=5)
        model_combo.bind("<<ComboboxSelected>>", self.change_model)
        
        lang_label = ttk.Label(control_frame, text="Dil:")
        lang_label.pack(side=tk.LEFT, padx=5)
        
        self.lang_var = tk.StringVar(value="Otomatik")
        lang_combo = ttk.Combobox(control_frame, textvariable=self.lang_var, 
                               values=["Otomatik", "Türkçe", "English", "Español", "Français", "Deutsch"])
        lang_combo.pack(side=tk.LEFT, padx=5)
        lang_combo.bind("<<ComboboxSelected>>", self.change_language)
        
        self.transcription_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("Arial", 12), 
                                                        bg="#2D2D30", fg="white", border=1, padx=10, pady=10)
        self.transcription_text.pack(fill=tk.BOTH, expand=True, pady=10)
        self.transcription_text.config(state=tk.DISABLED)
        
        self.status_var = tk.StringVar(value="Model yükleniyor...")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, foreground="#4FC3F7")
        status_label.pack(pady=5)
        
        button_frame = ttk.Frame(main_frame, style="TFrame")
        button_frame.pack(pady=10)
        
        self.record_button = tk.Button(button_frame, text="Konuşmaya Başla", font=("Arial", 12), 
                                  bg="#4CAF50", fg="white", padx=10, pady=10, width=15,
                                  command=self.toggle_recording)
        self.record_button.pack(side=tk.LEFT, padx=10)
        
        clear_button = tk.Button(button_frame, text="Temizle", font=("Arial", 12), 
                             bg="#F44336", fg="white", padx=10, pady=10, width=15,
                             command=self.clear_transcription)
        clear_button.pack(side=tk.LEFT, padx=10)
        
        threading.Thread(target=self.load_model_thread, daemon=True).start()
    
    def load_model_thread(self):
        self.transcriber.load_model()
        self.status_var.set("Model yüklendi. Konuşmaya başlayabilirsiniz.")
    
    def change_model(self, event=None):
        if self.is_transcribing:
            return
            
        model_name = self.model_var.get()
        self.transcriber = WhisperTranscriber(model_name)
        self.status_var.set(f"{model_name} modeli yükleniyor...")
        threading.Thread(target=self.load_model_thread, daemon=True).start()
    
    def change_language(self, event=None):
        language = self.lang_var.get()
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
        self.record_button.config(text="Konuşmayı Durdur", bg="#F44336")
        self.status_var.set("Kayıt yapılıyor...")
        
        self.recorder.start()
        
        self.transcription_thread = threading.Thread(target=self.transcribe_loop, daemon=True)
        self.transcription_thread.start()
    
    def stop_recording(self):
        self.is_transcribing = False
        self.record_button.config(text="Konuşmaya Başla", bg="#4CAF50")
        self.status_var.set("Kayıt durduruldu.")
        
        self.recorder.stop()
        
        audio_data = self.recorder.get_buffer_audio()
        if audio_data is not None and len(audio_data) > 0:
            text = self.transcriber.transcribe_audio(audio_data, language=self.language)
            self.update_transcription(text)
    
    def transcribe_loop(self):
        while self.is_transcribing:
            audio_data = self.recorder.get_buffer_audio()
            
            if audio_data is not None and len(audio_data) > 0:
                text = self.transcriber.transcribe_audio(audio_data, language=self.language)
                self.root.after(0, lambda t=text: self.update_transcription(t))
            
            time.sleep(2)
    
    def update_transcription(self, text):
        if text and text.strip():
            self.transcription_text.config(state=tk.NORMAL)
            current_text = self.transcription_text.get(1.0, tk.END).strip()
            
            if not current_text:
                self.transcription_text.insert(tk.END, text)
            else:
                if not current_text.endswith(text.strip()):
                    self.transcription_text.insert(tk.END, f"\n{text}")
                    
            self.transcription_text.see(tk.END)
            self.transcription_text.config(state=tk.DISABLED)
    
    def clear_transcription(self):
        self.transcription_text.config(state=tk.NORMAL)
        self.transcription_text.delete(1.0, tk.END)
        self.transcription_text.config(state=tk.DISABLED)
    
    def on_closing(self):
        self.is_transcribing = False
        if hasattr(self.recorder, 'stop'):
            self.recorder.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SpeechToTextApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

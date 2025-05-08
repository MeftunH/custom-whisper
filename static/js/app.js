document.addEventListener('DOMContentLoaded', () => {
    const recordButton = document.getElementById('record-button');
    const clearButton = document.getElementById('clear-button');
    const transcript = document.getElementById('transcript');
    const modelSelect = document.getElementById('model-select');
    const languageSelect = document.getElementById('language-select');
    const statusDisplay = document.getElementById('status');
    const visualizerCanvas = document.getElementById('visualizer-canvas');
    const copyButton = document.querySelector('.copy-button');
    const themeToggle = document.querySelector('.theme-toggle');
    const typingIndicator = document.querySelector('.typing-indicator');
    
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    let stream;
    let audioContext;
    let analyser;
    let canvasCtx;
    let dataArray;
    let animationFrame;
    let isDarkTheme = true;
    
    async function initializeAudio() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            statusDisplay.textContent = 'Hazır - Konuşmaya başlayabilirsiniz';
            
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioContext.createMediaStreamSource(stream);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 2048;
            const bufferLength = analyser.frequencyBinCount;
            dataArray = new Uint8Array(bufferLength);
            
            source.connect(analyser);
            
            canvasCtx = visualizerCanvas.getContext('2d');
            resizeCanvas();
            visualize();
            
            mediaRecorder = new MediaRecorder(stream, { 
                mimeType: 'audio/webm'
            });
            
            mediaRecorder.ondataavailable = event => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };
            
            mediaRecorder.onstop = async () => {
                if (audioChunks.length > 0) {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    await processAudio(audioBlob);
                    audioChunks = [];
                }
            };
            
            initializeAnimation();
            recordButton.disabled = false;
        } catch (error) {
            statusDisplay.textContent = 'Mikrofon erişimi hatası: ' + error.message;
            console.error('Mikrofon erişimi hatası:', error);
            recordButton.disabled = true;
        }
    }
    
    function resizeCanvas() {
        visualizerCanvas.width = visualizerCanvas.parentElement.clientWidth;
        visualizerCanvas.height = visualizerCanvas.parentElement.clientHeight;
    }
    
    function visualize() {
        if (!analyser) return;
        
        animationFrame = requestAnimationFrame(visualize);
        
        analyser.getByteTimeDomainData(dataArray);
        
        canvasCtx.clearRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
        
        canvasCtx.lineWidth = 2;
        canvasCtx.strokeStyle = isRecording ? '#ef4444' : '#4a6cf7';
        canvasCtx.beginPath();
        
        const sliceWidth = visualizerCanvas.width / dataArray.length;
        let x = 0;
        
        for(let i = 0; i < dataArray.length; i++) {
            const v = dataArray[i] / 128.0;
            const y = v * visualizerCanvas.height / 2;
            
            if(i === 0) {
                canvasCtx.moveTo(x, y);
            } else {
                canvasCtx.lineTo(x, y);
            }
            
            x += sliceWidth;
        }
        
        canvasCtx.lineTo(visualizerCanvas.width, visualizerCanvas.height / 2);
        canvasCtx.stroke();
    }
    
    function initializeAnimation() {
        gsap.to('.gradient-blob', {
            x: 'random(-20, 20)',
            y: 'random(-20, 20)',
            scale: 'random(0.95, 1.05)',
            duration: 10,
            ease: 'sine.inOut',
            repeat: -1,
            yoyo: true,
            stagger: 2
        });
        
        recordButton.addEventListener('mousedown', () => {
            gsap.to('.button-ripple', {
                scale: 1.5,
                opacity: 0.5,
                duration: 0.5,
                onComplete: () => {
                    gsap.to('.button-ripple', {
                        scale: 0,
                        opacity: 0,
                        duration: 0.3
                    });
                }
            });
        });
    }
    
    window.addEventListener('resize', resizeCanvas);
    
    initializeAudio();
    
    recordButton.addEventListener('click', toggleRecording);
    clearButton.addEventListener('click', clearTranscript);
    
    themeToggle.addEventListener('click', () => {
        const root = document.documentElement;
        if (isDarkTheme) {
            root.style.setProperty('--background-dark', '#f8fafc');
            root.style.setProperty('--background-light', '#f1f5f9');
            root.style.setProperty('--text-color', '#1e293b');
            root.style.setProperty('--text-color-secondary', '#64748b');
            themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
        } else {
            root.style.setProperty('--background-dark', '#0f172a');
            root.style.setProperty('--background-light', '#1e293b');
            root.style.setProperty('--text-color', '#e2e8f0');
            root.style.setProperty('--text-color-secondary', '#a0aec0');
            themeToggle.innerHTML = '<i class="fas fa-moon"></i>';
        }
        isDarkTheme = !isDarkTheme;
    });
    
    copyButton.addEventListener('click', () => {
        const textToCopy = transcript.textContent;
        if (textToCopy) {
            navigator.clipboard.writeText(textToCopy)
                .then(() => {
                    const originalText = copyButton.innerHTML;
                    copyButton.innerHTML = '<i class="fas fa-check"></i> Kopyalandı';
                    setTimeout(() => {
                        copyButton.innerHTML = originalText;
                    }, 2000);
                })
                .catch(err => {
                    console.error('Kopyalama hatası:', err);
                });
        }
    });
    
    function toggleRecording() {
        if (!isRecording) {
            startRecording();
        } else {
            stopRecording();
        }
    }
    
    function startRecording() {
        if (!mediaRecorder) return;
        
        isRecording = true;
        document.querySelector('.button-label').textContent = 'Konuşmayı Durdur';
        recordButton.querySelector('.button-inner i').className = 'fas fa-stop';
        recordButton.classList.add('recording');
        statusDisplay.textContent = 'Kayıt yapılıyor...';
        
        audioChunks = [];
        try {
            mediaRecorder.start(100);
        } catch (e) {
            console.error('MediaRecorder error:', e);
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mediaRecorder.ondataavailable = event => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };
            mediaRecorder.onstop = async () => {
                if (audioChunks.length > 0) {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    await processAudio(audioBlob);
                    audioChunks = [];
                }
            };
            mediaRecorder.start(100);
        }
    }
    
    function stopRecording() {
        if (!mediaRecorder || mediaRecorder.state === 'inactive') return;
        
        isRecording = false;
        document.querySelector('.button-label').textContent = 'Konuşmaya Başla';
        recordButton.querySelector('.button-inner i').className = 'fas fa-microphone';
        recordButton.classList.remove('recording');
        statusDisplay.textContent = 'Ses işleniyor...';
        typingIndicator.classList.add('active');
        
        mediaRecorder.stop();
    }
    
    async function processAudio(audioBlob) {
        try {
            const reader = new FileReader();
            
            reader.onloadend = async () => {
                try {
                    const base64Audio = reader.result;
                    await transcribeAudio(base64Audio);
                } catch (error) {
                    console.error('Error processing audio result:', error);
                    statusDisplay.textContent = 'Ses işleme hatası: ' + error.message;
                    typingIndicator.classList.remove('active');
                }
            };
            
            reader.onerror = () => {
                console.error('FileReader error:', reader.error);
                statusDisplay.textContent = 'Dosya okuma hatası';
                typingIndicator.classList.remove('active');
            };
            
            reader.readAsDataURL(audioBlob);
        } catch (error) {
            console.error('Error in processAudio:', error);
            statusDisplay.textContent = 'Ses işleme hatası: ' + error.message;
            typingIndicator.classList.remove('active');
        }
    }
    
    async function transcribeAudio(base64Audio) {
        try {
            showProcessingAnimation('Ses dönüştürülüyor...');
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 saniye zaman aşımı
            
            const response = await fetch('/transcribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    audio: base64Audio,
                    language: languageSelect.value || 'tr',  // Türkçe varsayılan
                    model: modelSelect.value
                }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Server error: ' + response.status);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            hideProcessingAnimation();
            typingIndicator.classList.remove('active');
            typeText(data.text);
            statusDisplay.textContent = 'Hazır - Konuşmaya başlayabilirsiniz';
        } catch (error) {
            hideProcessingAnimation();
            let errorMessage = 'Hata: ';
            
            if (error.name === 'AbortError') {
                errorMessage += 'İşlem zaman aşımına uğradı. Lütfen daha küçük ses kaydı yapın veya "tiny" modeli kullanın.';
            } else {
                errorMessage += error.message;
            }
            
            statusDisplay.textContent = errorMessage;
            console.error('Transcription error:', error);
            typingIndicator.classList.remove('active');
        }
    }
    
    function showProcessingAnimation(statusText) {
        statusDisplay.innerHTML = `
            <div class="processing-container">
                <div class="processing-animation">
                    <div class="processing-circle"></div>
                    <div class="processing-circle"></div>
                    <div class="processing-circle"></div>
                </div>
                <span>${statusText}</span>
            </div>
        `;
    }
    
    function hideProcessingAnimation() {
        statusDisplay.innerHTML = '';
    }
    
    function typeText(text) {
        if (!text || text.trim() === '') return;
        
        const currentText = transcript.textContent;
        const textToAdd = currentText && currentText.trim() !== '' ? `\n${text}` : text;
        
        const length = textToAdd.length;
        let i = 0;
        
        const interval = setInterval(() => {
            if (i < length) {
                if (i === 0 && currentText && currentText.trim() !== '') {
                    transcript.textContent += '\n';
                }
                transcript.textContent += textToAdd[i];
                i++;
            } else {
                clearInterval(interval);
            }
        }, 20);
    }
    
    function updateTranscript(text) {
        if (!text || text.trim() === '') return;
        
        const currentText = transcript.textContent;
        
        if (!currentText || currentText.trim() === '') {
            transcript.textContent = text;
        } else {
            transcript.textContent = `${currentText}\n${text}`;
        }
    }
    
    function clearTranscript() {
        transcript.textContent = '';
    }
    
    window.addEventListener('beforeunload', () => {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }
        if (audioContext) {
            audioContext.close();
        }
        if (animationFrame) {
            cancelAnimationFrame(animationFrame);
        }
    });
    
    // Varsayılan olarak Türkçe dili seç
    languageSelect.value = 'tr';
});

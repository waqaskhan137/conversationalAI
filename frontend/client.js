let socket;
let audioContext;
let processor;
let globalStream;

const startButton = document.getElementById('startButton');
const stopButton = document.getElementById('stopButton');
const transcriptionDiv = document.getElementById('transcription');

startButton.addEventListener('click', startTranscription);
stopButton.addEventListener('click', stopTranscription);

function startTranscription() {
  startButton.disabled = true;
  stopButton.disabled = false;

  // Initialize WebSocket connection to the server
  socket = new WebSocket('ws://localhost:8005');

  socket.onopen = function() {
    console.log('WebSocket connection established.');
  };

  socket.onmessage = function(event) {
    const message = event.data;
    transcriptionDiv.innerHTML += `<p>${message}</p>`;
  };

  socket.onclose = function() {
    console.log('WebSocket connection closed.');
  };

  // Start capturing audio
  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      globalStream = stream;

      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const input = audioContext.createMediaStreamSource(stream);

      let audioBuffer = [];

      processor = audioContext.createScriptProcessor(16384, 1, 1);
      processor.onaudioprocess = function(e) {
        const inputData = e.inputBuffer.getChannelData(0);
        console.log(`Original sample rate: ${audioContext.sampleRate}`); 
        
        // Resample audio to 16kHz
        const resampledAudio = resampleAudio(inputData, audioContext.sampleRate, 16000);

        // Convert Float32Array to Int16Array
        const int16Data = floatTo16BitPCM(resampledAudio);
        audioBuffer.push(int16Data);

        // Send accumulated audio chunks after a few seconds
        if (audioBuffer.length >= THRESHOLD_SIZE) {
          const combinedBuffer = mergeBuffers(audioBuffer);
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(combinedBuffer.buffer);
          }
          audioBuffer = []; // Clear buffer after sending
        }
      };

      input.connect(processor);
      processor.connect(audioContext.destination);
    })
    .catch(err => {
      console.error('Error accessing microphone:', err);
    });
}

function stopTranscription() {
  startButton.disabled = false;
  stopButton.disabled = true;

  // Close WebSocket connection
  if (socket) {
    socket.close();
  }

  // Stop audio processing
  if (processor) {
    processor.disconnect();
  }
  if (audioContext) {
    audioContext.close();
  }
  if (globalStream) {
    globalStream.getTracks().forEach(track => track.stop());
  }
}

function floatTo16BitPCM(float32Array) {
  const int16Array = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return int16Array;
}

// Resample audio from the original sample rate to the target sample rate
function resampleAudio(audioData, originalSampleRate, targetSampleRate) {
  if (originalSampleRate === targetSampleRate) {
    return audioData; // No resampling needed if rates match
  }

  const sampleRateRatio = originalSampleRate / targetSampleRate;
  const newLength = Math.round(audioData.length / sampleRateRatio);
  const resampledAudio = new Float32Array(newLength);

  for (let i = 0; i < newLength; i++) {
    const originalIndex = i * sampleRateRatio;
    const lowerIndex = Math.floor(originalIndex);
    const upperIndex = Math.ceil(originalIndex);
    const weight = originalIndex - lowerIndex;

    if (upperIndex < audioData.length) {
      resampledAudio[i] = audioData[lowerIndex] * (1 - weight) + audioData[upperIndex] * weight;
    } else {
      resampledAudio[i] = audioData[lowerIndex]; // Handle boundary case
    }
  }

  return resampledAudio;
}

// Helper function to merge Int16Array buffers
function mergeBuffers(buffers) {
  const totalLength = buffers.reduce((sum, buffer) => sum + buffer.length, 0);
  const mergedArray = new Int16Array(totalLength);

  let offset = 0;
  for (let buffer of buffers) {
    mergedArray.set(buffer, offset);
    offset += buffer.length;
  }

  return mergedArray;
}

// Define a threshold size for when to send the audio data to the server
const THRESHOLD_SIZE = 15; // Adjust this value based on your needs

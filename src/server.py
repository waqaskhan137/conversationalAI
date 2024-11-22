import argparse
import asyncio
import numpy as np
import websockets
import torch
import whisper
import logging
import json
from datetime import datetime, timedelta
from queue import Queue
from datetime import timezone
import os
from TTS.api import TTS

# Configure logging
logging.basicConfig(level=logging.INFO)

# Define argument parser for command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument("--model", default="medium", help="Model to use", choices=["tiny", "base", "small", "medium", "large"])
parser.add_argument("--non_english", action='store_true', help="Don't use the English model.")
parser.add_argument("--phrase_timeout", default=6, help="How much empty space between recordings before a new line in transcription.", type=float)
args = parser.parse_args()

# Load Whisper model with weights_only flag
model_name = args.model
if args.model != "large" and not args.non_english:
    model_name = model_name + ".en"

print(f"Loading model: {model_name}")   
model = whisper.load_model(model_name)

try:
    tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False)
    logging.info("TTS model initialized.")
except Exception as e:
    logging.error(f"Failed to initialize TTS model: {e}")

# Initialize queue for audio data
data_queue = Queue()

# Keep track of transcription chunks for naming files
chunk_index = 1

# Function to generate TTS from text and include chunk_index in filename
def generate_tts_from_text(transcription_text):
    global chunk_index 
    """Function to generate speech from text and save it to a file, including chunk_index in filename."""
    output_filename = f"output_{chunk_index}.wav"

    # Increment the chunk index for the next transcription
    chunk_index += 1
    
    logging.info(f"Generating TTS for transcription: {transcription_text}")
    try:
        tts.tts_to_file(text=transcription_text, file_path=output_filename)
        logging.info(f"TTS audio file generated: {output_filename}")
    except Exception as e:
        logging.error(f"Error generating TTS: {e}")
    return output_filename

# Function to process audio data and perform transcription
def transcribe_audio_from_queue():
    """Function to process queued audio and return transcription."""
    global chunk_index  # Access the global chunk_index
    phrase_time = None
    transcription = ['']

    while True:
        now = datetime.now(timezone.utc)
        if not data_queue.empty():
            phrase_complete = False
            if phrase_time and now - phrase_time > timedelta(seconds=args.phrase_timeout):
                phrase_complete = True
            phrase_time = now

            # Combine and process audio data from the queue
            audio_data = b''.join(list(data_queue.queue))
            data_queue.queue.clear()
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            # Transcribe the audio data
            logging.info("Transcribing audio data...")
            result = model.transcribe(audio_np, fp16=torch.cuda.is_available())
            text = result['text'].strip()

            # Handle new phrases
            if phrase_complete:
                transcription.append(text)
            else:
                transcription[-1] = text
            # Return transcription
            return '\n'.join(transcription)

# WebSocket audio handler
async def audio_handler(websocket):
    global chunk_index
    logging.info("Client connected.")
    try:
        async for message in websocket:
            logging.info(f"Received audio data of size: {len(message)} bytes")
            
            # Receive and process audio
            data_queue.put(message)
            transcription = transcribe_audio_from_queue()
            
            if transcription:
                # Send transcription text
                await websocket.send(json.dumps({"type": "text", "data": transcription}))
                
                # Generate TTS audio and send audio data
                audio_filename = generate_tts_from_text(transcription)
                with open(audio_filename, "rb") as audio_file:
                    audio_data = audio_file.read()
                await websocket.send(json.dumps({"type": "audio", "data": audio_data.hex()}))
                logging.info(f"Sent transcription and audio: {transcription}")
    except websockets.exceptions.ConnectionClosed as e:
        logging.info(f"Client disconnected: {e}")

# Main function
async def main():
    # Start the WebSocket server and listen on localhost port 8000
    async with websockets.serve(audio_handler, "0.0.0.0", int(os.getenv('port', 8000)), max_size=2**25):
        logging.info("Server started on ws://0.0.0.0:8000")
        await asyncio.Future()  # Run indefinitely

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Server error: {e}")
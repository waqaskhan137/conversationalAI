import argparse
import asyncio
import numpy as np
import websockets
import torch
import whisper
import logging
from datetime import datetime, timedelta
from queue import Queue
from datetime import timezone
import os

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

# Initialize queue for audio data
data_queue = Queue()

# Function to process audio data and perform transcription
def transcribe_audio_from_queue():
    """Function to process queued audio and return transcription."""
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
    logging.info("Client connected.")
    try:
        async for message in websocket:
            logging.info(f"Received audio data of size: {len(message)} bytes")
            # Receive the audio data as a buffer from the client
            audio_data = np.frombuffer(message, dtype=np.int16)
            logging.info(f"Audio samples received: {len(audio_data)}")

            # Pass audio data into the queue for processing
            data_queue.put(message)

            # Process audio and send back transcription
            transcription = transcribe_audio_from_queue()
            if transcription:
                await websocket.send(transcription)
                logging.info(f"Sent transcription: {transcription}")
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
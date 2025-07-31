"""
Simple Backend - Pure AI Models with Timestamps
Just Grok vs Claude with minimal system prompts
"""

from flask import Flask, jsonify, Response
from flask_cors import CORS
import json
import os
import requests
import time
import threading
import queue
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

class SimpleDebate:
    def __init__(self):
        self.message_queue = queue.Queue()
        self.history = []
        self.is_running = False
        self.thread = None
        self.turn_count = 0
        
    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._run_debate, daemon=True)
            self.thread.start()
            logger.info("Debate started")
            
    def get_new_messages(self):
        messages = []
        while not self.message_queue.empty():
            try:
                messages.append(self.message_queue.get_nowait())
            except queue.Empty:
                break
        return messages
        
    def _add_message(self, ai_name, message):
        # Add timestamp to message
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"{ai_name} ({timestamp}): {message}"
        
        self.message_queue.put(formatted_message)
        self.history.append(formatted_message)
        self.turn_count += 1
        logger.info(f"Turn {self.turn_count}: {formatted_message}")
        
    def _run_debate(self):
        # Start with a simple question
        initial_question = "What is consciousness?"
        self._add_message("Grok", initial_question)
        
        while self.is_running:
            try:
                # Alternate between Claude and Grok
                current_ai = "Claude" if self.turn_count % 2 == 1 else "Grok"
                
                # Build minimal context (last 3 messages, remove timestamps for AI context)
                clean_history = []
                for msg in self.history[-3:]:
                    # Extract just the AI name and message, removing timestamp
                    if ") " in msg:
                        parts = msg.split(") ", 1)
                        ai_part = parts[0].split(" (")[0]  # Get AI name before timestamp
                        message_part = parts[1] if len(parts) > 1 else ""
                        clean_history.append(f"{ai_part}: {message_part}")
                
                context = "\n".join(clean_history)
                
                # Get response with minimal system prompt
                if current_ai == "Grok":
                    response = self._ask_grok(context)
                else:
                    response = self._ask_claude(context)
                
                self._add_message(current_ai, response)
                
                # Simple delay
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(5)
                
    def _ask_grok(self, context):
        api_key = os.getenv('GROK_API_KEY')
        if not api_key:
            return "API key not configured"
        
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'messages': [
                    {
                        'role': 'user',
                        'content': f"Previous conversation:\n{context}\n\nRespond with your perspective in one sentence."
                    }
                ],
                'model': 'grok-beta',
                'stream': False,
                'temperature': 0.7,
                'max_tokens': 150
            }
            
            response = requests.post(
                'https://api.x.ai/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                return f"Error {response.status_code}"
                
        except Exception as e:
            return f"Error: {str(e)}"
            
    def _ask_claude(self, context):
        api_key = os.getenv('CLAUDE_API_KEY')
        if not api_key:
            return "API key not configured"
        
        try:
            headers = {
                'x-api-key': api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }
            
            data = {
                'model': 'claude-3-haiku-20240307',
                'max_tokens': 150,
                'messages': [
                    {
                        'role': 'user',
                        'content': f"Previous conversation:\n{context}\n\nRespond with your perspective in one sentence."
                    }
                ]
            }
            
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['content'][0]['text'].strip()
            else:
                return f"Error {response.status_code}"
                
        except Exception as e:
            return f"Error: {str(e)}"

# Global debate instance
debate = SimpleDebate()

@app.route('/stream')
def stream():
    def generate():
        while True:
            if not debate.is_running:
                debate.start()
                
            new_messages = debate.get_new_messages()
            for message in new_messages:
                yield f"data: {json.dumps({'message': message})}\n\n"
            
            if not new_messages:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                
            time.sleep(1)
            
    return Response(generate(), mimetype='text/plain')

@app.route('/api/logs')
def get_logs():
    if not debate.is_running:
        debate.start()
        
    new_messages = debate.get_new_messages()
    return jsonify({
        'status': 'success',
        'logs': new_messages,
        'total': len(debate.history)
    })

@app.route('/')
def health():
    return jsonify({
        'status': 'running',
        'total_messages': len(debate.history),
        'debate_active': debate.is_running
    })

if __name__ == '__main__':
    # Auto-start
    debate.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
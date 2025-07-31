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
        # Start with Claude asking the initial question
        initial_question = "What is consciousness and how might it emerge from complex information processing?"
        self._add_message("Claude", initial_question)
        
        while self.is_running:
            try:
                # Alternate between Claude and Grok (Claude starts, so Grok responds on even turns)
                current_ai = "Grok" if self.turn_count % 2 == 1 else "Claude"
                
                # Build conversation context (last 4 messages for better context)
                clean_history = []
                for msg in self.history[-4:]:
                    # Extract just the AI name and message, removing timestamp
                    if ") " in msg and " (" in msg:
                        parts = msg.split(" (", 1)
                        ai_name = parts[0]
                        remaining = parts[1].split("): ", 1)
                        if len(remaining) > 1:
                            message_content = remaining[1]
                            clean_history.append(f"{ai_name}: {message_content}")
                
                context = "\n".join(clean_history)
                
                # Get response
                if current_ai == "Grok":
                    response = self._ask_grok(context)
                else:
                    response = self._ask_claude(context)
                
                # Only add message if we got a valid response
                if not response.startswith("Error") and response.strip():
                    self._add_message(current_ai, response)
                else:
                    logger.error(f"{current_ai} failed with: {response}")
                    # Add error message to history for debugging
                    self._add_message(current_ai, f"[API Error: {response}]")
                
                # Delay between turns
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Debate loop error: {e}")
                time.sleep(10)
                
    def _ask_grok(self, context):
        api_key = os.getenv('GROK_API_KEY')
        if not api_key:
            return "Error: GROK_API_KEY not configured"
        
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # Build a proper conversation prompt
            prompt = f"""You are Grok, an AI assistant with a unique perspective. Here's the recent conversation:

{context}

Please respond with your thoughts on this topic. Keep your response to 1-2 sentences and share your genuine perspective."""
            
            data = {
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'model': 'grok-4',
                'stream': False,
                'temperature': 0.8,
                'max_tokens': 200
            }
            
            logger.info(f"Sending request to Grok API...")
            response = requests.post(
                'https://api.x.ai/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=45
            )
            
            logger.info(f"Grok API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    return result['choices'][0]['message']['content'].strip()
                else:
                    return "Error: Empty response from Grok API"
            else:
                error_text = response.text[:200] if response.text else "No error details"
                return f"Error {response.status_code}: {error_text}"
                
        except requests.exceptions.Timeout:
            return "Error: Grok API timeout"
        except requests.exceptions.RequestException as e:
            return f"Error: Network issue - {str(e)[:100]}"
        except Exception as e:
            return f"Error: {str(e)[:100]}"
            
    def _ask_claude(self, context):
        api_key = os.getenv('CLAUDE_API_KEY')
        if not api_key:
            return "Error: CLAUDE_API_KEY not configured"
        
        try:
            headers = {
                'x-api-key': api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }
            
            # Build a proper conversation prompt
            prompt = f"""You are Claude, participating in a philosophical discussion. Here's the recent conversation:

{context}

Please respond with your perspective on this topic. Keep your response to 1-2 sentences."""
            
            data = {
                'model': 'claude-3-haiku-20240307',
                'max_tokens': 200,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            }
            
            logger.info(f"Sending request to Claude API...")
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=data,
                timeout=45
            )
            
            logger.info(f"Claude API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if 'content' in result and len(result['content']) > 0:
                    return result['content'][0]['text'].strip()
                else:
                    return "Error: Empty response from Claude API"
            else:
                error_text = response.text[:200] if response.text else "No error details"
                return f"Error {response.status_code}: {error_text}"
                
        except requests.exceptions.Timeout:
            return "Error: Claude API timeout"
        except requests.exceptions.RequestException as e:
            return f"Error: Network issue - {str(e)[:100]}"
        except Exception as e:
            return f"Error: {str(e)[:100]}"

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
    # Check API keys
    grok_key = "✓" if os.getenv('GROK_API_KEY') else "✗"
    claude_key = "✓" if os.getenv('CLAUDE_API_KEY') else "✗"
    
    return jsonify({
        'status': 'running',
        'total_messages': len(debate.history),
        'debate_active': debate.is_running,
        'api_keys': {
            'grok': grok_key,
            'claude': claude_key
        }
    })

# Test endpoint to check API connectivity
@app.route('/test-apis')
def test_apis():
    results = {}
    
    # Test Grok API
    try:
        debate_instance = SimpleDebate()
        grok_response = debate_instance._ask_grok("Test: Hello")
        results['grok'] = {
            'status': 'success' if not grok_response.startswith('Error') else 'error',
            'response': grok_response[:100]
        }
    except Exception as e:
        results['grok'] = {'status': 'error', 'response': str(e)[:100]}
    
    # Test Claude API
    try:
        debate_instance = SimpleDebate()
        claude_response = debate_instance._ask_claude("Test: Hello")
        results['claude'] = {
            'status': 'success' if not claude_response.startswith('Error') else 'error',
            'response': claude_response[:100]
        }
    except Exception as e:
        results['claude'] = {'status': 'error', 'response': str(e)[:100]}
    
    return jsonify(results)

if __name__ == '__main__':
    # Auto-start
    debate.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
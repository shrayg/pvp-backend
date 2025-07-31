# app.py
"""
Simple Backend - Pure AI Models with Timestamps
Just Grok vs Claude with minimal system prompts
"""

from flask import Flask, jsonify, Response, stream_with_context
from flask_cors import CORS
import json, os, requests, time, threading, queue, logging
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
        msgs = []
        while not self.message_queue.empty():
            msgs.append(self.message_queue.get_nowait())
        return msgs

    def _add_message(self, ai_name, message):
        ts = datetime.now().strftime("%H:%M:%S")
        formatted = f"{ai_name} ({ts}): {message}"
        self.message_queue.put(formatted)
        self.history.append(formatted)
        self.turn_count += 1
        logger.info(f"Turn {self.turn_count}: {formatted}")

    def _run_debate(self):
        # kickoff
        self._add_message("Claude", "What is consciousness and how might it emerge from complex information processing?")
        while self.is_running:
            try:
                speaker = "Grok" if self.turn_count % 2 == 1 else "Claude"
                # build last-4 lines of context
                clean = []
                for msg in self.history[-4:]:
                    _, rest = msg.split("): ", 1)
                    clean.append(rest)
                context = "\n".join(clean)

                # choose which AI to call
                if speaker == "Grok":
                    resp = self._ask_grok(context)
                else:
                    resp = self._ask_claude(context)

                if resp and not resp.startswith("Error"):
                    self._add_message(speaker, resp)
                else:
                    logger.error(f"{speaker} error: {resp}")
                    self._add_message(speaker, f"[API Error: {resp}]")

                time.sleep(10)

            except Exception as e:
                logger.error(f"Debate loop error: {e}")
                time.sleep(10)

    def _ask_grok(self, context):
        key = os.getenv('GROK_API_KEY')
        if not key:
            return "Error: GROK_API_KEY not configured"

        headers = {
            'x-api-key': key,
            'Content-Type': 'application/json'
        }

        # use a minimal system+user prompt to avoid policy issues
        system_msg = "You are Grok, an AI assistant with a witty, concise style."
        user_msg = f"Here is the recent conversation:\n{context}\n\nRespond in 1–2 casual sentences."

        payload = {
            'model': 'grok-4',
            'messages': [
                {'role': 'system', 'content': system_msg},
                {'role': 'user',   'content': user_msg}
            ],
            'stream': False,
            'temperature': 0.8,
            'max_tokens': 200
        }

        logger.info("Sending request to Grok API...")
        r = requests.post('https://api.x.ai/v1/chat/completions', headers=headers, json=payload, timeout=45)
        logger.info(f"Grok API status: {r.status_code}")

        try:
            result = r.json()
            logger.info(f"Grok API JSON: {result}")
        except ValueError:
            return f"Error: Invalid JSON ({r.text[:200]})"

        if 'choices' in result and result['choices']:
            choice = result['choices'][0]
            # prefer the chat-style field
            if 'message' in choice and 'content' in choice['message']:
                text = choice['message']['content'].strip()
                if text:
                    return text
            # fallback to legacy `text`
            if 'text' in choice:
                text = choice['text'].strip()
                if text:
                    return text
            return "Error: empty response content"
        return "Error: no choices in response"

    def _ask_claude(self, context):
        key = os.getenv('CLAUDE_API_KEY')
        if not key:
            return "Error: CLAUDE_API_KEY not configured"

        headers = {
            'x-api-key': key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }

        prompt = f"""You are Claude, participating in a philosophical discussion.
Here is the recent conversation:
{context}

Respond in 1–2 concise sentences."""

        payload = {
            'model': 'claude-3-haiku-20240307',
            'max_tokens': 200,
            'messages': [{'role': 'user', 'content': prompt}]
        }

        logger.info("Sending request to Claude API...")
        r = requests.post('https://api.anthropic.com/v1/messages', headers=headers, json=payload, timeout=45)
        logger.info(f"Claude API status: {r.status_code}")

        try:
            result = r.json()
        except ValueError:
            return f"Error: Invalid JSON ({r.text[:200]})"

        if 'choices' in result and result['choices']:
            choice = result['choices'][0]
            if 'message' in choice and 'content' in choice['message']:
                return choice['message']['content'].strip()
            if 'text' in choice:
                return choice['text'].strip()
        return "Error: no valid choice in response"


debate = SimpleDebate()

@app.route('/stream')
def stream():
    def generate():
        # replay full history
        for msg in debate.history:
            yield f"data: {json.dumps({'message': msg})}\n\n"
        # then stream new messages
        while True:
            if not debate.is_running:
                debate.start()
            for m in debate.get_new_messages():
                yield f"data: {json.dumps({'message': m})}\n\n"
            time.sleep(1)
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/logs')
def get_logs():
    if not debate.is_running:
        debate.start()
    return jsonify({
        'status': 'success',
        'logs': debate.history,
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
    debate.start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)

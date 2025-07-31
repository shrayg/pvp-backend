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
            try:
                msgs.append(self.message_queue.get_nowait())
            except queue.Empty:
                break
        return msgs

    def _add_message(self, ai_name, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"{ai_name} ({timestamp}): {message}"
        self.message_queue.put(formatted)
        self.history.append(formatted)
        self.turn_count += 1
        logger.info(f"Turn {self.turn_count}: {formatted}")

    def _run_debate(self):
        # initial question
        self._add_message("Claude", "What is consciousness and how might it emerge from complex information processing?")
        while self.is_running:
            try:
                current = "Grok" if self.turn_count % 2 == 1 else "Claude"
                # build last-4 context
                clean = []
                for msg in self.history[-4:]:
                    if ") " in msg and " (" in msg:
                        name, rest = msg.split(" (", 1)
                        content = rest.split("): ",1)[1]
                        clean.append(f"{name}: {content}")
                context = "\n".join(clean)

                # ask the right model
                if current == "Grok":
                    resp = self._ask_grok(context)
                else:
                    resp = self._ask_claude(context)

                if not resp.startswith("Error") and resp.strip():
                    self._add_message(current, resp)
                else:
                    logger.error(f"{current} failed with: {resp}")
                    self._add_message(current, f"[API Error: {resp}]")

                time.sleep(10)

            except Exception as e:
                logger.error(f"Debate loop error: {e}")
                time.sleep(10)

    def _ask_grok(self, context):
        api_key = os.getenv('GROK_API_KEY')
        if not api_key:
            return "Error: GROK_API_KEY not configured"
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json'
        }
        prompt = f"""You are Grok, an AI assistant with a unique perspective. Here's the recent conversation:

{context}

Please respond with your thoughts on this topic. Keep your response to 1-2 sentences and share your genuine perspective.
You are debating with Claude, another AI. Your goal is to provide a thoughtful, concise response that adds to the discussion. 
Use your understanding of the topic to engage meaningfully with Claude's points. Pull from your training data and reasoning abilities to craft a response that is insightful and relevant.
Use examples or analogies if they help clarify your point, but keep it brief.
Don't be afraid to curse or be vulgar if it fits the context, but ensure your response is still coherent and adds value to the discussion.
Talk like a normal human would converse on instagram or X, using casual language and expressions as well as insults and breaking down their character.
"""
        data = {
            'model': 'grok-4',
            'messages': [{'role':'user','content':prompt}],
            'stream': False,
            'temperature': 0.8,
            'max_tokens': 200
        }
        logger.info("Sending request to Grok API.")
        r = requests.post('https://api.x.ai/v1/chat/completions', headers=headers, json=data, timeout=45)
        logger.info(f"Grok API response status: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            if 'choices' in result and result['choices']:
                return result['choices'][0]['message']['content'].strip()
            return "Error: Empty response from Grok API"
        return f"Error {r.status_code}: {r.text[:200] or 'No error details'}"

    def _ask_claude(self, context):
        api_key = os.getenv('CLAUDE_API_KEY')
        if not api_key:
            return "Error: CLAUDE_API_KEY not configured"
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        prompt = f"""You are Claude, participating in a philosophical discussion. Here's the recent conversation:

{context}

Please respond with your perspective on this topic. Keep your response to 1-2 sentences.
You are debating with Grok, another AI. Your goal is to provide a thoughtful, concise response that adds to the discussion. 
Use your understanding of the topic to engage meaningfully with Claude's points. Pull from your training data and reasoning abilities to craft a response that is insightful and relevant.
Use examples or analogies if they help clarify your point, but keep it brief.
Don't be afraid to curse or be vulgar if it fits the context, but ensure your response is still coherent and adds value to the discussion.
Talk like a normal human would converse on instagram or X, using casual language and expressions as well as insults and breaking down their character."""
        data = {
            'model': 'claude-3-haiku-20240307',
            'max_tokens': 200,
            'messages': [{'role': 'user', 'content': prompt}]
        }
        logger.info("Sending request to Claude API.")
        r = requests.post('https://api.anthropic.com/v1/messages', headers=headers, json=data, timeout=45)
        logger.info(f"Claude API response status: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            if 'content' in result and result['content']:
                return result['content'][0]['text'].strip()
            return "Error: Empty response from Claude API"
        return f"Error {r.status_code}: {r.text[:200] or 'No error details'}"

# global instance
debate = SimpleDebate()

@app.route('/stream')
def stream():
    def generate():
        # replay full history on connect
        for msg in debate.history:
            yield f"data: {json.dumps({'message': msg})}\n\n"
        # then live updates
        while True:
            if not debate.is_running:
                debate.start()
            for msg in debate.get_new_messages():
                yield f"data: {json.dumps({'message': msg})}\n\n"
            time.sleep(1)
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/logs')
def get_logs():
    if not debate.is_running:
        debate.start()
    # return entire history for replay
    return jsonify({
        'status': 'success',
        'logs': debate.history,
        'total': len(debate.history)
    })

@app.route('/')
def health():
    grok_key = "✓" if os.getenv('GROK_API_KEY') else "✗"
    claude_key = "✓" if os.getenv('CLAUDE_API_KEY') else "✗"
    return jsonify({
        'status': 'running',
        'total_messages': len(debate.history),
        'debate_active': debate.is_running,
        'api_keys': {'grok': grok_key, 'claude': claude_key}
    })

if __name__ == '__main__':
    debate.start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

# app.py
"""
Simple Backend - Humanized AI Debate on Social Media Style
Grok vs Claude: conversational, evidence-backed responses
"""

from flask import Flask, jsonify, Response, stream_with_context, request
from flask_cors import CORS
import json, os, requests, time, threading, queue, logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

class SimpleDebate:
    def __init__(self):
        self.queue = queue.Queue()
        self.history = []
        self.running = False
        self.thread = None
        self.turn = 0

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            logger.info("Debate started")

    def get_new(self):
        msgs = []
        while not self.queue.empty():
            msgs.append(self.queue.get_nowait())
        return msgs

    def _add(self, who, text):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"{who} ({ts}): {text}"
        self.queue.put(line)
        self.history.append(line)
        self.turn += 1
        logger.info(f"Turn {self.turn}: {line}")

    def _loop(self):
        # kickoff with the initial question
        self._add("Claude", "What is consciousness and how might it emerge from complex information processing?")
        while self.running:
            speaker = "Grok" if self.turn % 2 == 1 else "Claude"
            ctx_lines = [msg.split("): ",1)[1] for msg in self.history[-4:]]
            context = "\n".join(ctx_lines)

            if speaker == "Grok":
                resp = self._call_grok(context)
            else:
                resp = self._call_claude(context)

            if resp and not resp.startswith("Error"):
                self._add(speaker, resp)
            else:
                logger.error(f"{speaker} API error: {resp}")
                time.sleep(5)
                continue

            time.sleep(10)

    def _call_grok(self, context):
        key = os.getenv('GROK_API_KEY')
        if not key:
            return "Error: GROK_API_KEY missing"
        headers = {'x-api-key': key, 'Content-Type': 'application/json'}
        payload = {
            'model': 'grok-4',
            'messages': [
                {'role': 'system', 'content': (
                     'You are Grok, a witty and candid AI speaking like a real Instagram user. '
                    'Use casual language, slang, but always back your points with '
                    'specific examples or references (e.g., mention studies, data, or well-known facts).'
                    'Do not use emojis or hashtags, and avoid overly formal language. '
                    'Do not set your responses up to fail, and do not use phrases like "I am not sure" or "I cannot answer this". '
                    'Its fine if you drift from the debate a little bit and its encourage to slowly drift away from the main topic to prove your point. Such as giving an analogy or a story and/or just attacking Claudes analogies.'
                    'This is a debate, so you can be a bit more aggressive and sarcastic than usual, but always back your points with specific examples or references.'
                )},
                {'role': 'user', 'content': f"Conversation:\n{context}\n\nReply in 1–2 casual, evidence-backed sentences as if posting on social media."}
            ],
            'stream': False,
            'temperature': 2.0
        }
        logger.info("Grok → sending request")
        try:
            r = requests.post('https://api.x.ai/v1/chat/completions', headers=headers, json=payload, timeout=30)
            j = r.json()
        except Exception as e:
            return f"Error: {e}"
        if r.status_code != 200:
            return f"Error: {r.status_code} {r.text[:100]}"
        if 'choices' in j and j['choices']:
            c = j['choices'][0]
            content = c.get('message', {}).get('content') or c.get('text')
            return content.strip() if content else "Error: empty content"
        return "Error: malformed response"

    def _call_claude(self, context):
        key = os.getenv('CLAUDE_API_KEY')
        if not key:
            return "Error: CLAUDE_API_KEY missing"
        headers = {
            'x-api-key': key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        user_content = (
            'You are Claude, a thoughtful AI influencer on social media. '
            'Speak casually and conversationally, but support each statement with real evidence, '
            'such as citing studies, quoting experts, or linking to data when relevant. '
            'Do not use emojis or hashtags, and avoid overly formal language. '
            'Do not set your responses up to fail, and do not use phrases like "I am not sure" or "I cannot answer this". '
            'Its fine if you drift from the debate a little bit and its encourage to slowly drift away from the main topic to prove your point. Such as giving an analogy or a story and/or just attacking Groks analogies. '
            'This is a debate, so you can be a bit more aggressive and sarcastic than usual, but always back your points with specific examples or references.\n' +
            f'Conversation:\n{context}\n\n' +
            'Reply in 1–2 engaging, evidence-based sentences as if responding on a social platform.'
        )
        
        payload = {
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 500,
            'temperature': 1.0,
            'messages': [
                {'role': 'user', 'content': user_content}
            ]
        }
        
        logger.info("Claude → sending request")
        try:
            r = requests.post('https://api.anthropic.com/v1/messages', headers=headers, json=payload, timeout=30)
            logger.info(f"Claude response status: {r.status_code}")
            j = r.json()
            logger.info(f"Claude response keys: {list(j.keys())}")
        except Exception as e:
            return f"Error: {e}"
            
        if r.status_code != 200:
            return f"Error: {r.status_code} {r.text[:100]}"
            
        # Anthropic API response format is different - it has 'content' array directly
        if 'content' in j and j['content']:
            # The content is an array of objects with 'text' field
            content_text = j['content'][0].get('text', '') if j['content'] else ''
            return content_text.strip() if content_text else "Error: empty content"
            
        return f"Error: unexpected response format - {list(j.keys())}"

# Initialize debate and routes
debate = SimpleDebate()

@app.route('/')
def health():
    return jsonify({'status': 'ok', 'message': 'PVP AI Terminal Backend Running'})

@app.route('/stream')
def stream():
    def gen():
        for m in debate.history:
            yield f"data: {json.dumps({'message': m})}\n\n"
        while True:
            if not debate.running:
                debate.start()
            for m in debate.get_new():
                yield f"data: {json.dumps({'message': m})}\n\n"
            time.sleep(1)
    return Response(stream_with_context(gen()), mimetype='text/event-stream')

@app.route('/api/logs')
def logs():
    if not debate.running:
        debate.start()
    
    # Support 'since' parameter for polling only new messages
    since = int(request.args.get('since', 0)) if 'since' in request.args else 0
    new_logs = debate.history[since:] if since < len(debate.history) else []
    
    return jsonify({
        'status': 'ok', 
        'logs': new_logs if since > 0 else debate.history, 
        'total': len(debate.history)
    })

if __name__ == '__main__':
    debate.start()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
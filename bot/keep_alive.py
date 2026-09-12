from flask import Flask
from threading import Thread
import os

app = Flask(__name__)


@app.route('/')
def home():
    return 'Bot is alive', 200


@app.route('/health')
def health():
    return 'OK', 200


def run():
    port = int(os.getenv('PORT', '10000'))
    app.run(host='0.0.0.0', port=port, use_reloader=False)


def keep_alive():
    Thread(target=run, daemon=True, name='render-health-server').start()

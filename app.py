#!/usr/bin/env python3
from flask import Flask, render_template, jsonify
import config

app = Flask(__name__)
scanner_instance = None

def init_web_server(scanner):
    global scanner_instance
    scanner_instance = scanner
    return app

@app.route('/')
def index():
    return render_template('index.html', max_range=config.MAX_RANGE_KM)

@app.route('/api/telemetry')
def telemetry():
    if not scanner_instance:
        return jsonify({"error": "Scanner system context offline"}), 500
    return jsonify(scanner_instance.state)
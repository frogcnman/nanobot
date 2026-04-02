#!/usr/bin/env python3
"""Entry point for running webchat as a module"""

from nanobot.webchat.app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=False, threaded=True)

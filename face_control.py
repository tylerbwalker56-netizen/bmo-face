#!/usr/bin/env python3
"""
BMO Face Control Server
Runs alongside bmo_face.py — accepts commands over a simple socket
so other programs (mic, camera, brain) can change expressions.

Usage:
    # From any script on the Pi:
    echo "happy" | nc localhost 5555
    echo "talking" | nc localhost 5555
    echo "idle" | nc localhost 5555

    # Or use the Python client:
    from face_client import set_expression
    set_expression("surprised")
"""

import socket
import threading
import json
import time

CONTROL_PORT = 5555
CONTROL_HOST = "127.0.0.1"

# Valid expressions
VALID_EXPRESSIONS = {
    "idle", "happy", "talking", "surprised", "love",
    "sleepy", "angry", "sad", "confused", "wink", "excited"
}


class FaceControlServer:
    """Simple TCP server that receives expression commands."""

    def __init__(self, callback, host=CONTROL_HOST, port=CONTROL_PORT):
        """
        callback: function(command_dict) called when a command arrives.
                  command_dict has at least {"action": "expression", "value": "happy"}
        """
        self.callback = callback
        self.host = host
        self.port = port
        self.server = None
        self.running = False
        self.thread = None

    def start(self):
        """Start the control server in a background thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print(f"[FaceControl] Listening on {self.host}:{self.port}")

    def stop(self):
        """Stop the server."""
        self.running = False
        if self.server:
            self.server.close()

    def _run(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        self.server.settimeout(1.0)

        while self.running:
            try:
                conn, addr = self.server.accept()
                threading.Thread(target=self._handle_client,
                                 args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_client(self, conn):
        try:
            data = conn.recv(1024).decode("utf-8").strip()
            if not data:
                return

            # Try JSON first
            try:
                cmd = json.loads(data)
            except json.JSONDecodeError:
                # Plain text — treat as expression name
                if data.lower() in VALID_EXPRESSIONS:
                    cmd = {"action": "expression", "value": data.lower()}
                else:
                    conn.sendall(b"ERROR: unknown command\n")
                    return

            # Process the command
            response = self._process_command(cmd)
            conn.sendall((json.dumps(response) + "\n").encode("utf-8"))

        except Exception as e:
            try:
                conn.sendall(f"ERROR: {e}\n".encode("utf-8"))
            except Exception:
                pass
        finally:
            conn.close()

    def _process_command(self, cmd):
        action = cmd.get("action", "expression")

        if action == "expression":
            value = cmd.get("value", "idle")
            if value in VALID_EXPRESSIONS:
                self.callback(cmd)
                return {"ok": True, "expression": value}
            else:
                return {"ok": False, "error": f"Unknown expression: {value}"}

        elif action == "talk":
            # Syllable-synced talking: {"action":"talk","text":"Hello!","duration":2.0}
            text = cmd.get("text", "")
            if text:
                self.callback(cmd)
                return {"ok": True, "action": "talk", "text": text[:50]}
            return {"ok": False, "error": "No text provided"}

        elif action == "stop_talk":
            self.callback(cmd)
            return {"ok": True, "action": "stop_talk"}

        elif action == "status":
            return {"ok": True, "status": "running"}

        elif action == "ping":
            return {"ok": True, "pong": time.time()}

        else:
            return {"ok": False, "error": f"Unknown action: {action}"}

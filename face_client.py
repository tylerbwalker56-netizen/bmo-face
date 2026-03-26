#!/usr/bin/env python3
"""
BMO Face Client — send commands to the face from any script.

Usage:
    from face_client import set_expression, get_status

    set_expression("happy")
    set_expression("talking")
    set_expression("idle")
    get_status()
"""

import socket
import json

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5555


def send_command(cmd, host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=2.0):
    """Send a command to the face control server and return the response."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))

        if isinstance(cmd, dict):
            data = json.dumps(cmd)
        else:
            data = str(cmd)

        sock.sendall((data + "\n").encode("utf-8"))
        response = sock.recv(1024).decode("utf-8").strip()
        sock.close()

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw": response}

    except ConnectionRefusedError:
        return {"ok": False, "error": "Face server not running"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def set_expression(expression, host=DEFAULT_HOST, port=DEFAULT_PORT):
    """Change the face expression."""
    return send_command({"action": "expression", "value": expression},
                        host=host, port=port)


def talk(text, duration=None, host=DEFAULT_HOST, port=DEFAULT_PORT):
    """
    Start syllable-synced talking animation.
    text: what Pip is saying (used to estimate syllable timing)
    duration: optional hint for how long speech will take (seconds)
    """
    cmd = {"action": "talk", "text": text}
    if duration is not None:
        cmd["duration"] = duration
    return send_command(cmd, host=host, port=port)


def stop_talk(host=DEFAULT_HOST, port=DEFAULT_PORT):
    """Stop talking and return to idle."""
    return send_command({"action": "stop_talk"}, host=host, port=port)


def get_status(host=DEFAULT_HOST, port=DEFAULT_PORT):
    """Check if face server is running."""
    return send_command({"action": "status"}, host=host, port=port)


def ping(host=DEFAULT_HOST, port=DEFAULT_PORT):
    """Ping the face server."""
    return send_command({"action": "ping"}, host=host, port=port)


# CLI usage
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        expr = sys.argv[1].lower()
        result = set_expression(expr)
        print(result)
    else:
        print("Usage: python3 face_client.py <expression>")
        print("Expressions: idle, happy, talking, surprised, love, sleepy, angry")

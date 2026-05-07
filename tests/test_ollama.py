import requests

print("Testing Ollama connection...")

try:
    r = requests.post("http://localhost:11434/api/generate", json={"model": "mistral", "prompt": "hi", "stream": False})
    print("Localhost status:", r.status_code)
    print("Localhost response:", r.json().get("response"))
except Exception as e:
    print("Localhost failed:", e)

try:
    r = requests.post("http://127.0.0.1:11434/api/generate", json={"model": "mistral", "prompt": "hi", "stream": False})
    print("127.0.0.1 status:", r.status_code)
    print("127.0.0.1 response:", r.json().get("response"))
except Exception as e:
    print("127.0.0.1 failed:", e)

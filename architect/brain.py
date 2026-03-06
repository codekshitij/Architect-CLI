import requests

class InferenceEngine:
    def __init__(self, model="qwen2.5-coder:7b"):
        self.url = "http://localhost:11434/api/generate"
        self.model = model

    def get_relationship(self, file_a, code_a, file_b, code_b):
        # Truncate code to 1000 chars each for speed/context limits
        prompt = (
            f"File A: {file_a}\nCode Snippet: {code_a[:1000]}\n\n"
            f"File B: {file_b}\nCode Snippet: {code_b[:1000]}\n\n"
            "File B depends on File A. Describe their architectural relationship "
            "in 10 words or less."
        )
        try:
            res = requests.post(self.url, json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "system": "You are a concise software architect."
            }, timeout=10)
            return res.json().get("response", "dependency").strip().replace('"', "'")
        except:
            return "direct dependency"
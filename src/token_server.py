import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler

from dotenv import load_dotenv
from livekit.api import AccessToken, VideoGrants

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
ROOM_NAME = "armenian-voice-room"


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/token":
            token = AccessToken(api_key=API_KEY, api_secret=API_SECRET)
            token.with_identity("user")
            token.with_name("user")
            token.with_grants(VideoGrants(room_join=True, room=ROOM_NAME))
            jwt = token.to_jwt()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"token": jwt}).encode())
        elif self.path == "/" or self.path == "":
            self.path = "/index.html"
            return SimpleHTTPRequestHandler.do_GET(self)
        else:
            return SimpleHTTPRequestHandler.do_GET(self)


if __name__ == "__main__":
    os.chdir(FRONTEND_DIR)
    server = HTTPServer(("localhost", 8081), Handler)
    print("Frontend running at http://localhost:8081")
    server.serve_forever()

import os
from dotenv import load_dotenv
from livekit.api import AccessToken, VideoGrants

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
ROOM_NAME = "armenian-voice-room"
PARTICIPANT_NAME = "user"


def create_token() -> str:
    token = AccessToken(api_key=API_KEY, api_secret=API_SECRET)
    token.with_identity(PARTICIPANT_NAME)
    token.with_name(PARTICIPANT_NAME)
    token.with_grants(
        VideoGrants(
            room_join=True,
            room=ROOM_NAME,
        )
    )
    return token.to_jwt()


if __name__ == "__main__":
    jwt = create_token()
    print(f"\nToken: {jwt}\n")
    http_url = LIVEKIT_URL.replace("ws://", "http://").replace("wss://", "https://")
    meet_url = f"https://meet.livekit.io/custom?liveKitUrl={http_url}&token={jwt}"
    print(f"Open this in your browser to connect:\n{meet_url}\n")

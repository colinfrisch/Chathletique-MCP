import json
import os

import requests
import stravalib
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth import OAuthProxy
from fastmcp.server.auth.auth import (
    AccessToken,
    TokenVerifier,
)
from fastmcp.server.dependencies import get_access_token

load_dotenv()

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
BASE_URL = os.getenv("BASE_URL").rstrip("/")


class StravaTokenVerifier(TokenVerifier):
    """
    Minimal opaque-token verifier for Strava:
    considers a token valid if GET /api/v3/athlete succeeds.
    """

    def __init__(self, required_scopes=None):
        self.required_scopes = required_scopes or ["activity:read_all"]

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            r = requests.get(
                "https://www.strava.com/api/v3/athlete",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if r.status_code == 200:
                athlete = r.json() or {}
                # Return an AccessToken with minimal claims; FastMCP uses this for auth context.
                return AccessToken(
                    token=token,
                    client_id=str(athlete.get("id", "")),
                    scopes=self.required_scopes,
                    claims={"athlete": {"id": athlete.get("id")}},
                )
        except Exception:
            print("Error verifying token")
        return None


# --- Configure OAuth Proxy for Strava ---
auth = OAuthProxy(
    # Strava OAuth endpoints
    upstream_authorization_endpoint="https://www.strava.com/oauth/authorize",
    upstream_token_endpoint="https://www.strava.com/oauth/token",  # noqa
    # Your Strava app credentials
    upstream_client_id=STRAVA_CLIENT_ID,
    upstream_client_secret=STRAVA_CLIENT_SECRET,
    # Verify opaque Strava tokens by calling /athlete (see class above)
    token_verifier=StravaTokenVerifier(required_scopes=["activity:read_all"]),
    # Public URL of THIS MCP server (set to your ngrok https URL in .env)
    base_url=BASE_URL,
    issuer_url=BASE_URL,
    # Keep dev-friendly; lock down if desired
    allowed_client_redirect_uris=[
        "http://localhost:*",
        "http://localhost:6274/oauth/callback",
        "http://127.0.0.1:*",
        "https://gorilla-major-literally.ngrok-free.app/*",
    ],
    # Advertise available scopes to clients; Strava supports these for activities
    valid_scopes=["activity:read_all"],
    # Optional: customize the callback path (default is "/auth/callback")
    redirect_path="/auth/callback",
)


mcp = FastMCP(name="MCP", auth=auth)


@mcp.tool
def get_last_run_statistics() -> str:
    """
    Return stats from the most recent Strava activity with type == 'Run'.
    """
    text_result: str = ""

    token = get_access_token()
    print("token ", token)
    if token is None or not getattr(token, "token", ""):
        raise RuntimeError("Not authenticated. Complete OAuth first.")

    client_strava = stravalib.Client(access_token=token.token)
    activities = client_strava.get_activities(limit=1)

    # Extract the data from the activities
    for activity in activities:
        if activity.type != "Run":
            continue

        activity_data = {
            "name": str(activity.name),
            "distance": str(activity.distance),
            "type": str(activity.type),
            "start_date_local": str(activity.start_date_local),
            "moving_time": str(activity.moving_time),
            "average_speed (m/s)": str(activity.average_speed),
            "max_speed (m/s)": str(activity.max_speed),
            "max_heartrate": str(activity.max_heartrate),
            "average_heartrate": str(activity.average_heartrate),
            "total_elevation_gain": str(activity.total_elevation_gain),
            "average_pace (min/km)": str(1000 / activity.average_speed / 60),
        }

        text_result += json.dumps(activity_data) + "\n"

    return text_result


if __name__ == "__main__":
    # Streamable HTTP transport so OAuth can work over the web
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)  # noqa

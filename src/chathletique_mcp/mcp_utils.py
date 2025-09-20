"""MCP utilities for Strava coaching server."""

import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastmcp import FastMCP
from fastmcp.server.auth.oauth import AccessToken, TokenVerifier
from fastmcp.server.auth.oauth_proxy import OAuthProxy

mcp = FastMCP("Chathletique MCP Server", port=3000, stateless_http=True, debug=True)

load_dotenv()


# Strava OAuth config
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
BASE_URL = "https://gorilla-major-literally.ngrok-free.app"
REDIRECT_URI = "https://gorilla-major-literally.ngrok-free.app/auth/callback"

# Store user tokens in memory (for demo; use a DB in production)
user_tokens = {}
current_user_token = None  # Simple single-user token storage

auth = FastAPI()


def get_current_token():
    """Get the current user's Strava access token."""
    global current_user_token  # noqa
    if current_user_token:
        return current_user_token

    # Fallback: try to get from environment (for dev)
    token = os.getenv("STRAVA_ACCESS_TOKEN")
    if token:
        current_user_token = token
        return token

    return None


@auth.get("/auth/strava")
async def auth_strava():
    """Redirect user to Strava for OAuth authorization."""
    auth_url = (
        f"https://www.strava.com/oauth/authorize?"
        f"client_id={STRAVA_CLIENT_ID}&"
        f"response_type=code&"
        f"redirect_uri={REDIRECT_URI}&"
        f"scope=read,activity:read_all"
    )
    return {"url": auth_url}


@auth.get("/auth/callback")
async def callback(request: Request):
    """Handle Strava OAuth callback and store user token."""
    global current_user_token  # noqa

    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch access token")

        token_data = response.json()
        access_token = token_data["access_token"]

        # Store token globally for MCP tools to use
        current_user_token = access_token
        user_tokens[access_token] = token_data

        return {"status": "success", "access_token": access_token}


class StravaTokenVerifier(TokenVerifier):
    """
    Minimal verifier for opaque Strava tokens.
    Strategy: call GET /api/v3/athlete; 200 => valid token.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token:
            return None

        try:
            async with httpx.AsyncClient(timeout=6) as cx:
                r = await cx.get(
                    "https://www.strava.com/api/v3/athlete",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError:
            return None

        if r.status_code != 200:
            return None

        me = r.json()  # includes id, username, etc.
        # Return the smallest valid AccessToken object
        return AccessToken(
            token=token,
            # subject/client identifiers are optional; include athlete id for convenience
            subject=str(me.get("id")) if "id" in me else None,
            scopes=[],  # Strava doesn't expose scopes post-exchange
            expires_at=None,  # let the OAuth client handle refresh
            extra={"athlete_id": me.get("id")},
        )


auth = OAuthProxy(
    # Provider's OAuth endpoints (from their documentation)
    upstream_authorization_endpoint="https://www.strava.com/oauth/authorize",
    upstream_token_endpoint="https://www.strava.com/oauth/token",  # noqa
    # Your registered app credentials
    upstream_client_id=STRAVA_CLIENT_ID,
    upstream_client_secret=STRAVA_CLIENT_SECRET,
    # Token validation (see Token Verification guide)
    token_verifier=StravaTokenVerifier(),
    # Your FastMCP server's public URL
    base_url=BASE_URL,
)


mcp = FastMCP(name="strava-mcp", auth=auth)

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

TIMEOUT = 15
SPOTIFY_VARS = ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REFRESH_TOKEN")
GITHUB_USER = "tanrendev"
PROJECT_LIMIT = 5
PROJECT_MAX_AGE = timedelta(days=90)
CARD_TRACKS = 3
MAX_GENRES = 3
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3


def missing_credentials() -> list[str]:
    return [name for name in SPOTIFY_VARS if not os.environ.get(name)]


def top_tracks() -> list[dict]:
    token = _spotify_token()
    data = _request_json(
        url="https://api.spotify.com/v1/me/top/tracks?time_range=short_term&limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    tracks = []
    seen = set()
    for item in data["items"]:
        title, artist = item["name"], item["artists"][0]["name"]
        key = (title.casefold(), artist.casefold())
        if key in seen:
            continue
        seen.add(key)
        tracks.append({"title": title, "artist": artist, "spotify_id": item["id"]})
        if len(tracks) == CARD_TRACKS:
            break
    return tracks


def deezer_genres(*, title: str, artist: str) -> list[str]:
    query = urllib.parse.quote(f'artist:"{artist}" track:"{title}"')
    hits = _request_json(url=f"https://api.deezer.com/search?q={query}&limit=5").get("data", [])
    for hit in hits:
        if hit["artist"]["name"].casefold() != artist.casefold() or hit["title"].casefold() != title.casefold():
            continue
        album = _request_json(url=f"https://api.deezer.com/album/{hit['album']['id']}")
        names = [genre["name"] for genre in album.get("genres", {}).get("data", [])]
        if names:
            return _normalize(raw=names)
    return []


def youtube_link(*, title: str, artist: str) -> str | None:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return None
    query = urllib.parse.quote(f"{artist} {title}")
    data = _request_json(
        url=f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&maxResults=1&q={query}&key={key}"
    )
    items = data.get("items", [])
    if not items:
        return None
    return f"https://www.youtube.com/watch?v={items[0]['id']['videoId']}"


def github_projects() -> list[dict]:
    headers = {}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    repos = _request_json(
        url=f"https://api.github.com/users/{GITHUB_USER}/repos?type=owner&sort=pushed&per_page=100",
        headers=headers,
    )
    cutoff = datetime.now(tz=UTC) - PROJECT_MAX_AGE
    fresh = []

    for repo in repos:
        if repo["fork"] or repo["name"] == GITHUB_USER:
            continue
        if datetime.fromisoformat(repo["pushed_at"]) < cutoff:
            continue
        fresh.append(repo)
        if len(fresh) == PROJECT_LIMIT:
            break

    fresh.sort(key=lambda repo: repo["name"].casefold())
    return [
        {
            "name": repo["name"],
            "url": repo["html_url"],
            "description": repo["description"] or "",
            "language": repo["language"] or "",
        }
        for repo in fresh
    ]


def _normalize(*, raw: list[str]) -> list[str]:
    genres = []
    for value in raw:
        for part in value.split("/"):
            word = part.strip().lower()
            if word and word not in genres:
                genres.append(word)
    return genres[:MAX_GENRES]


def _spotify_token() -> str:
    basic = base64.b64encode(
        f"{os.environ['SPOTIFY_CLIENT_ID']}:{os.environ['SPOTIFY_CLIENT_SECRET']}".encode()
    ).decode()
    body = urllib.parse.urlencode(
        {"grant_type": "refresh_token", "refresh_token": os.environ["SPOTIFY_REFRESH_TOKEN"]}
    ).encode()
    data = _request_json(
        url="https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {basic}"},
        body=body,
    )
    return data["access_token"]


def _request_json(*, url: str, headers: dict[str, str] | None = None, body: bytes | None = None) -> Any:  # noqa: ANN401
    attempt = 0
    while True:
        try:
            request = urllib.request.Request(url, data=body, headers=headers or {})  # noqa: S310
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS - 1:
                raise
        except urllib.error.URLError:
            if attempt == MAX_ATTEMPTS - 1:
                raise
        else:
            return payload
        time.sleep(2**attempt)
        attempt += 1

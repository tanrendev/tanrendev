import contextlib
import json
import sys
from pathlib import Path

from builder import rendering, sources

STACK = ["Python", "Django", "FastAPI", "PostgreSQL", "Redis", "Docker", "AWS", "Linux"]


def main() -> int:
    match sys.argv[1:]:
        case ["render"]:
            return render()
        case ["fetch"]:
            return fetch()
        case _:
            print("usage: main.py {render,fetch}", file=sys.stderr)
            return 1


def render() -> int:
    music = json.loads(Path("music.json").read_text(encoding="utf-8"))
    tracks = music["tracks"]
    projects = json.loads(Path("projects.json").read_text(encoding="utf-8"))["projects"]
    primary_template = Path("templates/music-primary.svg").read_text(encoding="utf-8")
    row_template = Path("templates/music-row.svg").read_text(encoding="utf-8")
    stack_template = Path("templates/stack.svg").read_text(encoding="utf-8")

    for theme, palette in rendering.THEMES:
        svg = rendering.render_primary(track=tracks[0], palette=palette, template_text=primary_template)
        write_if_changed(path=Path("assets") / f"music-primary-{theme}.svg", content=svg)
        for rank, track in enumerate(tracks[1:], start=2):
            svg = rendering.render_row(track=track, rank=rank, palette=palette, template_text=row_template)
            write_if_changed(path=Path("assets") / f"music-row-{rank - 1}-{theme}.svg", content=svg)
        svg = rendering.render_stack(items=STACK, palette=palette, template_text=stack_template)
        write_if_changed(path=Path("assets") / f"stack-{theme}.svg", content=svg)
    readme_path = Path("README.md")
    readme = readme_path.read_text(encoding="utf-8")
    readme = rendering.splice(document=readme, marker="music", block=rendering.music_block(tracks=tracks))
    readme = rendering.splice(document=readme, marker="projects", block=rendering.projects_block(projects=projects))
    readme = rendering.splice(document=readme, marker="stack", block=rendering.stack_block(items=STACK))
    write_if_changed(path=readme_path, content=readme)
    return 0


def fetch() -> int:
    fetch_projects()
    return fetch_music()


def fetch_projects() -> None:
    try:
        projects = sources.github_projects()
    except Exception as error:  # noqa: BLE001
        print(f"fetch: github fetch failed: {error!r}", file=sys.stderr)
        return
    text = json.dumps({"projects": projects}, ensure_ascii=False, indent=2) + "\n"
    write_if_changed(path=Path("projects.json"), content=text)


def fetch_music() -> int:
    missing = sources.missing_credentials()
    if missing:
        print("fetch: missing environment variables:", ", ".join(missing), file=sys.stderr)
        return 1

    path = Path("music.json")
    current = {track["spotify_id"]: track for track in json.loads(path.read_text(encoding="utf-8"))["tracks"]}
    try:
        fresh = sources.top_tracks()
    except sources.FETCH_ERRORS as error:
        print(f"fetch: spotify request failed: {error!r}", file=sys.stderr)
        return 1
    if not fresh:
        print("fetch: spotify returned no tracks, music.json kept", file=sys.stderr)
        return 0

    tracks = [resolve_track(entry=entry, known=current.get(entry["spotify_id"])) for entry in fresh]
    text = json.dumps({"tracks": tracks}, ensure_ascii=False, indent=2) + "\n"
    write_if_changed(path=path, content=text)
    return 0


def resolve_track(*, entry: dict, known: dict | None) -> dict:
    fallback = f"https://open.spotify.com/track/{entry['spotify_id']}"
    track = {
        "title": entry["title"],
        "artist": entry["artist"],
        "link": fallback,
        "spotify_id": entry["spotify_id"],
        "genres": [],
    } | (known or {})
    if not track["genres"]:
        with contextlib.suppress(*sources.FETCH_ERRORS):
            track["genres"] = sources.deezer_genres(title=entry["title"], artist=entry["artist"])
    if track["link"] == fallback:
        with contextlib.suppress(*sources.FETCH_ERRORS):
            track["link"] = sources.youtube_link(title=entry["title"], artist=entry["artist"]) or fallback
    return track


def write_if_changed(*, path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

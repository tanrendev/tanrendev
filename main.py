import argparse
import json
import sys
import urllib.error
from pathlib import Path

from builder import rendering, sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tanrendev")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser(name="render", help="generate music SVGs and README sections from local data")
    subcommands.add_parser(name="fetch", help="refresh music.json from Spotify top tracks and Deezer genres")

    args = parser.parse_args(args=argv)
    match args.command:
        case "render":
            return render()
        case "fetch":
            return fetch()
        case _:
            parser.print_help()
            return 0


def render() -> int:
    music = json.loads(s=Path("music.json").read_text(encoding="utf-8"))
    tracks = music["tracks"]
    projects = json.loads(s=Path("projects.json").read_text(encoding="utf-8"))["projects"]
    primary_template = Path("templates/music-primary.svg").read_text(encoding="utf-8")
    row_template = Path("templates/music-row.svg").read_text(encoding="utf-8")

    for theme, palette in (("light", rendering.LIGHT), ("dark", rendering.DARK)):
        svg = rendering.render_primary(track=tracks[0], palette=palette, template_text=primary_template)
        write_if_changed(Path("assets") / f"music-primary-{theme}.svg", svg)
        for rank, track in enumerate(iterable=tracks[1:], start=2):
            svg = rendering.render_row(track=track, rank=rank, palette=palette, template_text=row_template)
            write_if_changed(Path("assets") / f"music-row-{rank - 1}-{theme}.svg", svg)

    readme_path = Path("README.md")
    readme = readme_path.read_text(encoding="utf-8")
    readme = rendering.splice(document=readme, marker="music", block=rendering.music_block(tracks=tracks))
    readme = rendering.splice(document=readme, marker="projects", block=rendering.projects_block(projects=projects))
    write_if_changed(readme_path, readme)
    return 0


def fetch() -> int:
    missing = sources.missing_credentials()
    if missing:
        print("fetch: missing environment variables:", ", ".join(missing), file=sys.stderr)
        return 1

    path = Path("music.json")
    current = {track["spotify_id"]: track for track in json.loads(s=path.read_text(encoding="utf-8"))["tracks"]}
    try:
        fresh = sources.top_tracks()
    except urllib.error.URLError as error:
        print(f"fetch: spotify request failed: {error}", file=sys.stderr)
        return 1

    tracks = []
    for entry in fresh:
        known = current.get(entry["spotify_id"])
        if known is not None:
            tracks.append(known)
            continue
        try:
            genres = sources.deezer_genres(entry["title"], entry["artist"])
        except urllib.error.URLError:
            genres = []
        try:
            link = sources.youtube_link(entry["title"], entry["artist"])
        except urllib.error.URLError:
            link = None
        tracks.append(
            {
                "title": entry["title"],
                "artist": entry["artist"],
                "link": link or f"https://open.spotify.com/track/{entry['spotify_id']}",
                "spotify_id": entry["spotify_id"],
                "genres": genres,
            }
        )

    text = json.dumps({"tracks": tracks}, ensure_ascii=False, indent=2) + "\n"
    if write_if_changed(path, text):
        print("fetch: music.json updated")
    else:
        print("fetch: no change")
    return 0


def write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(data=content, encoding="utf-8")
    return True


if __name__ == "__main__":
    sys.exit(main())

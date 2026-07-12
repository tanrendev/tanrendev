import string
from html import escape

LIGHT = {
    "panel": "#F3EEE5",
    "line": "#D7CDBA",
    "text": "#211B14",
    "muted": "#6C6256",
    "faint": "#9A9082",
    "lead": "#A4380F",
    "hot": "#BF451C",
    "vinyl_a": "#211B14",
    "vinyl_b": "#2C241C",
    "sheen_opacity": "0.10",
}
DARK = {
    "panel": "#141B23",
    "line": "#26313C",
    "text": "#DFE6EE",
    "muted": "#8A98A8",
    "faint": "#5D6C7C",
    "lead": "#739ABF",
    "hot": "#E8703A",
    "vinyl_a": "#05070A",
    "vinyl_b": "#10151C",
    "sheen_opacity": "0.08",
}

PRIMARY_TITLE_EM = 19.0
ROW_TITLE_EM = 24.0

CHIP_CHAR_W = 6.6
CHIP_PAD = 7.0
CHIP_GAP = 8.0
CHIP_H = 20.0
ROW_RIGHT_EDGE = 806.0
CHIP_FONT = "'IBM Plex Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace"


def render_primary(*, track: dict, palette: dict[str, str], template_text: str) -> str:
    values = palette | {
        "title": escape(s=truncate_to_width(text=track["title"], max_width=PRIMARY_TITLE_EM)),
        "artist": escape(s=track["artist"]),
        "chips": chips(genres=track.get("genres", [])[:3], palette=palette, x=210.0, y=150.0),
    }
    return string.Template(template_text).substitute(values)


def render_row(*, track: dict, rank: int, palette: dict[str, str], template_text: str) -> str:
    genres = track.get("genres", [])[:2]
    total = sum(chip_width(genre=genre) for genre in genres) + CHIP_GAP * max(len(genres) - 1, 0)
    values = palette | {
        "title": escape(s=truncate_to_width(text=track["title"], max_width=ROW_TITLE_EM)),
        "artist": escape(s=track["artist"]),
        "rank": f"{rank:02d}",
        "chips": chips(genres=genres, palette=palette, x=ROW_RIGHT_EDGE - total, y=18.0),
    }
    return string.Template(template_text).substitute(values)


def music_block(*, tracks: list[dict]) -> str:
    pieces = [("music-primary", tracks[0], "Now spinning: ")]
    pieces += [(f"music-row-{position}", track, "") for position, track in enumerate(tracks[1:], start=1)]
    lines = []
    for stem, track, prefix in pieces:
        title = truncate_to_width(text=track["title"], max_width=ROW_TITLE_EM)
        alt = escape(s=f"{prefix}{title} by {track['artist']}", quote=True)
        link = escape(s=track["link"], quote=True)
        lines.append(
            f'<a href="{link}"><picture>'
            f'<source media="(prefers-color-scheme: dark)" srcset="assets/{stem}-dark.svg">'
            f'<img src="assets/{stem}-light.svg" alt="{alt}" width="100%">'
            f"</picture></a>"
        )
    return "\n".join(lines)


def projects_block(*, projects: list[dict]) -> str:
    lines = [f"- [{project['name']}]({project['url']}): {project['description']}" for project in projects]
    return "\n".join(lines)


def splice(*, document: str, marker: str, block: str) -> str:
    start = f"<!-- {marker}:start -->"
    end = f"<!-- {marker}:end -->"
    head, found_start, rest = document.partition(start)
    _, found_end, tail = rest.partition(end)
    if not found_start or not found_end:
        message = f"README marker {marker!r} missing or incomplete"
        raise ValueError(message)
    return f"{head}{start}\n{block}\n{end}{tail}"


def chips(*, genres: list[str], palette: dict[str, str], x: float, y: float) -> str:
    fragments = []
    for genre in genres:
        width = chip_width(genre=genre)
        text_x = x + width / 2
        fragments.append(
            f'<g><rect x="{x:g}" y="{y:g}" width="{width:g}" height="{CHIP_H:g}" rx="5"'
            f' fill="none" stroke="{palette["line"]}"/>'
            f'<text x="{text_x:g}" y="{y + 14:g}" font-family="{CHIP_FONT}" font-size="11"'
            f' text-anchor="middle" fill="{palette["muted"]}">{escape(s=genre)}</text></g>'
        )
        x += width + CHIP_GAP
    return "".join(fragments)


def chip_width(*, genre: str) -> float:
    return len(genre) * CHIP_CHAR_W + 2 * CHIP_PAD


def truncate_to_width(*, text: str, max_width: float) -> str:
    used = 0.0
    kept = []
    for character in text:
        used += 0.52 if character.isascii() else 1.0
        if used > max_width:
            return "".join(kept) + "…"
        kept.append(character)
    return text

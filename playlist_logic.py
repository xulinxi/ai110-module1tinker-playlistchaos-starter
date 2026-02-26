from typing import Dict, List, Optional, Tuple

Song = Dict[str, object]
PlaylistMap = Dict[str, List[Song]]

DEFAULT_PROFILE = {
    "name": "Default",
    "hype_min_energy": 7,
    "chill_max_energy": 3,
    "favorite_genre": "rock",
    "include_mixed": True,
}


def normalize_title(title: str) -> str:
    """Normalize a song title for comparisons."""
    if not isinstance(title, str):
        return ""
    return title.strip()


def normalize_artist(artist: str) -> str:
    """Normalize an artist name for comparisons."""
    if not artist:
        return ""
    return artist.strip().lower()


def normalize_genre(genre: str) -> str:
    """Normalize a genre name for comparisons."""
    return genre.lower().strip()


def normalize_song(raw: Song) -> Song:
    """Return a normalized song dict with expected keys."""
    title = normalize_title(str(raw.get("title", "")))
    artist = normalize_artist(str(raw.get("artist", "")))
    genre = normalize_genre(str(raw.get("genre", "")))
    energy = raw.get("energy", 0)

    if isinstance(energy, str):
        try:
            energy = int(energy)
        except ValueError:
            energy = 0

    tags = raw.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    # Normalize tags: ensure list of trimmed, lowercase strings
    norm_tags: List[str] = []
    for t in tags:
        if not isinstance(t, str):
            continue
        tt = t.strip()
        if tt:
            norm_tags.append(tt.lower())

    return {
        "title": title,
        "artist": artist,
        "genre": genre,
        "energy": energy,
        "tags": norm_tags,
    }


def classify_song(song: Song, profile: Dict[str, object]) -> str:
    """Return a mood label given a song and user profile.

    Rules:
    - Hype: energy >= hype_min_energy OR genre == favorite_genre OR genre contains any hype keywords
    - Chill: energy <= chill_max_energy OR title contains any chill keywords
    - Mixed: otherwise
    """
    energy = song.get("energy", 0)
    genre = str(song.get("genre", "")).lower()
    title = str(song.get("title", ""))
    title_lower = title.lower()

    hype_min_energy = int(profile.get("hype_min_energy", 7))
    chill_max_energy = int(profile.get("chill_max_energy", 3))
    favorite_genre = str(profile.get("favorite_genre", "")).lower()

    hype_keywords = ["rock", "punk", "party"]
    chill_keywords = ["lofi", "ambient", "sleep"]

    is_hype_keyword = any(k in genre for k in hype_keywords)
    is_chill_keyword = any(k in title_lower for k in chill_keywords)

    # Hype checks are evaluated first per requirements
    if (genre == favorite_genre) or (isinstance(energy, (int, float)) and energy >= hype_min_energy) or is_hype_keyword:
        return "Hype"

    if (isinstance(energy, (int, float)) and energy <= chill_max_energy) or is_chill_keyword:
        return "Chill"

    return "Mixed"


def build_playlists(songs: List[Song], profile: Dict[str, object]) -> PlaylistMap:
    """Group songs into playlists based on mood and profile."""
    playlists: PlaylistMap = {
        "Hype": [],
        "Chill": [],
        "Mixed": [],
    }

    for song in songs:
        normalized = normalize_song(song)
        mood = classify_song(normalized, profile)
        normalized["mood"] = mood
        playlists[mood].append(normalized)

    return playlists


def merge_playlists(a: PlaylistMap, b: PlaylistMap) -> PlaylistMap:
    """Merge two playlist maps into a new map without mutating inputs."""
    merged: PlaylistMap = {}
    for key in set(list(a.keys()) + list(b.keys())):
        merged[key] = list(a.get(key, []))
        merged[key].extend(list(b.get(key, [])))
    return merged


def compute_playlist_stats(playlists: PlaylistMap) -> Dict[str, object]:
    """Compute statistics across all playlists.

    - Total Songs: unique count across playlists (deduplicated by title+artist)
    - Average Energy: average energy across unique songs
    - Hype Ratio: percentage of Hype songs relative to the total number of songs
    """
    # Collect all songs (may contain duplicates after merges)
    all_songs_raw: List[Song] = []
    for songs in playlists.values():
        all_songs_raw.extend(songs)

    # Deduplicate by title + artist
    unique_map: Dict[Tuple[str, str], Song] = {}
    for s in all_songs_raw:
        title = str(s.get("title", "")).strip()
        artist = str(s.get("artist", "")).strip()
        key = (title.lower(), artist.lower())
        if key not in unique_map:
            unique_map[key] = s

    unique_songs = list(unique_map.values())
    total_unique = len(unique_songs)

    hype_count = len(playlists.get("Hype", []))
    chill_count = len(playlists.get("Chill", []))
    mixed_count = len(playlists.get("Mixed", []))

    # Hype ratio as percentage of total unique songs
    hype_ratio = (hype_count / total_unique * 100.0) if total_unique > 0 else 0.0

    avg_energy = 0.0
    if total_unique > 0:
        total_energy = sum(float(s.get("energy", 0) or 0) for s in unique_songs)
        avg_energy = total_energy / total_unique

    top_artist, top_count = most_common_artist(unique_songs)

    return {
        "total_songs": total_unique,
        "hype_count": hype_count,
        "chill_count": chill_count,
        "mixed_count": mixed_count,
        "hype_ratio": hype_ratio,
        "avg_energy": avg_energy,
        "top_artist": top_artist,
        "top_artist_count": top_count,
    }


def most_common_artist(songs: List[Song]) -> Tuple[str, int]:
    """Return the most common artist and count."""
    counts: Dict[str, int] = {}
    for song in songs:
        artist = str(song.get("artist", "")).strip()
        if not artist:
            continue
        key = artist.lower()
        counts[key] = counts.get(key, 0) + 1

    if not counts:
        return "", 0

    items = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    # return artist in original casing if possible
    top_key, top_count = items[0]
    return top_key, top_count


def search_songs(
    songs: List[Song],
    query: str,
    field: str = "artist",
) -> List[Song]:
    """Return songs matching the query on a given field.

    Case-insensitive partial match: returns songs where query is contained in the
    song's field value.
    """
    if not query:
        return songs

    q = query.lower().strip()
    filtered: List[Song] = []

    for song in songs:
        value = str(song.get(field, "")).lower()
        if value and q in value:
            filtered.append(song)

    return filtered


def lucky_pick(
    playlists: PlaylistMap,
    mode: str = "any",
) -> Optional[Song]:
    """Pick a song from the playlists according to mode.

    - 'hype' -> only from Hype
    - 'chill' -> only from Chill
    - 'any' -> from Hype + Chill + Mixed
    """
    if mode == "hype":
        songs = playlists.get("Hype", [])
    elif mode == "chill":
        songs = playlists.get("Chill", [])
    else:
        # include Mixed when picking from any
        songs = playlists.get("Hype", []) + playlists.get("Chill", []) + playlists.get("Mixed", [])

    return random_choice_or_none(songs)


def random_choice_or_none(songs: List[Song]) -> Optional[Song]:
    """Return a random song or None if list is empty."""
    import random

    if not songs:
        return None
    return random.choice(songs)


def history_summary(history: List[Song]) -> Dict[str, int]:
    """Return a summary of moods seen in the history."""
    counts = {"Hype": 0, "Chill": 0, "Mixed": 0}
    for song in history:
        mood = song.get("mood", "Mixed")
        if mood not in counts:
            counts["Mixed"] += 1
        else:
            counts[mood] += 1
    return counts

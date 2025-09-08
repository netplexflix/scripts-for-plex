import requests
from plexapi.server import PlexServer

# -----------------------------
# CONFIGURATION
# -----------------------------
PLEX_URL = "http://localhost:32400"
PLEX_TOKEN = "YOUR_PLEX_TOKEN"

RADARR_URL = "http://localhost:7878/api/v3"
RADARR_API_KEY = "YOUR_RADARR_TOKEN"

SONARR_URL = "http://localhost:8989/api/v3"
SONARR_API_KEY = "YOUR_SONARR_TOKEN"

# -----------------------------
# HELPERS
# -----------------------------
def lookup_tmdb_from_imdb(imdb_id: str) -> int | None:
    """Convert IMDb ID to TMDb via Radarr API"""
    url = f"{RADARR_URL}/movie/lookup/imdb"
    resp = requests.get(url, params={"apikey": RADARR_API_KEY, "imdbId": imdb_id})
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, dict) and data.get("tmdbId"):
            return int(data["tmdbId"])
    return None

def lookup_tmdb_from_tvdb(tvdb_id: str) -> int | None:
    """Convert TVDb ID to TMDb via Radarr API"""
    url = f"{RADARR_URL}/movie/lookup/tvdb"
    resp = requests.get(url, params={"apikey": RADARR_API_KEY, "tvdbId": tvdb_id})
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, dict) and data.get("tmdbId"):
            return int(data["tmdbId"])
    return None

def lookup_tvdb_from_imdb_tv(imdb_id: str) -> int | None:
    """Convert IMDb ID to TVDb via Sonarr API"""
    url = f"{SONARR_URL}/series/lookup"
    resp = requests.get(url, params={"apikey": SONARR_API_KEY, "term": f"imdb:{imdb_id}"})
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list) and len(data) > 0 and data[0].get("tvdbId"):
            return int(data[0]["tvdbId"])
    return None

# -----------------------------
# PLEX: Fetch Movies
# -----------------------------
print("🎬 Fetching Plex movies...")
plex = PlexServer(PLEX_URL, PLEX_TOKEN)
plex_movies = plex.library.section("Movies")

plex_tmdb_ids = set()
plex_movie_id_to_title = {}

for movie in plex_movies.all():
    movie.reload()

    tmdb_id = None
    imdb_id = None
    tvdb_id = None

    for guid in movie.guids:
        if guid.id.startswith("tmdb://"):
            tmdb_id = int(guid.id.split("tmdb://")[1])
            break
        elif guid.id.startswith("imdb://"):
            imdb_id = guid.id.split("imdb://")[1]
        elif guid.id.startswith("tvdb://"):
            tvdb_id = guid.id.split("tvdb://")[1]

    # Fallback lookups if no TMDb ID
    if not tmdb_id and imdb_id:
        tmdb_id = lookup_tmdb_from_imdb(imdb_id)
    if not tmdb_id and tvdb_id:
        tmdb_id = lookup_tmdb_from_tvdb(tvdb_id)

    if tmdb_id:
        plex_tmdb_ids.add(tmdb_id)
        plex_movie_id_to_title[tmdb_id] = movie.title
    else:
        print(f"[DEBUG] No usable ID for Plex movie: {movie.title}")
        print("        GUIDs:", [g.id for g in movie.guids])

# -----------------------------
# PLEX: Fetch TV Shows
# -----------------------------
print("📺 Fetching Plex TV shows...")
plex_shows = plex.library.section("TV Shows")

plex_tvdb_ids = set()
plex_show_id_to_title = {}

for show in plex_shows.all():
    show.reload()

    tvdb_id = None
    imdb_id = None

    for guid in show.guids:
        if guid.id.startswith("tvdb://"):
            tvdb_id = int(guid.id.split("tvdb://")[1])
            break
        elif guid.id.startswith("imdb://"):
            imdb_id = guid.id.split("imdb://")[1]

    # Fallback lookup if no TVDb ID
    if not tvdb_id and imdb_id:
        tvdb_id = lookup_tvdb_from_imdb_tv(imdb_id)

    if tvdb_id:
        plex_tvdb_ids.add(tvdb_id)
        plex_show_id_to_title[tvdb_id] = show.title
    else:
        print(f"[DEBUG] No usable ID for Plex TV show: {show.title}")
        print("        GUIDs:", [g.id for g in show.guids])

# -----------------------------
# RADARR: Fetch Movies
# -----------------------------
print("🎞️ Fetching Radarr movies...")
radarr_resp = requests.get(
    f"{RADARR_URL}/movie",
    params={"apikey": RADARR_API_KEY}
)
radarr_resp.raise_for_status()
radarr_movies = radarr_resp.json()

radarr_tmdb_ids = set()
radarr_movie_id_to_title = {}

for m in radarr_movies:
    if m.get("hasFile") and m.get("tmdbId"):
        tmdb_id = int(m["tmdbId"])
        radarr_tmdb_ids.add(tmdb_id)
        radarr_movie_id_to_title[tmdb_id] = m["title"]

# -----------------------------
# SONARR: Fetch TV Shows
# -----------------------------
print("📡 Fetching Sonarr TV shows...")
sonarr_resp = requests.get(
    f"{SONARR_URL}/series",
    params={"apikey": SONARR_API_KEY}
)
sonarr_resp.raise_for_status()
sonarr_shows = sonarr_resp.json()

sonarr_tvdb_ids = set()
sonarr_show_id_to_title = {}

for show in sonarr_shows:
    # Check if the show has downloaded episodes
    has_episodes = False
    if show.get("statistics", {}).get("episodeFileCount", 0) > 0:
        has_episodes = True
    
    if has_episodes and show.get("tvdbId"):
        tvdb_id = int(show["tvdbId"])
        sonarr_tvdb_ids.add(tvdb_id)
        sonarr_show_id_to_title[tvdb_id] = show["title"]

# -----------------------------
# MOVIE COMPARISONS
# -----------------------------
print("\n" + "="*50)
print("🎬 MOVIE COMPARISON")
print("="*50)

plex_movies_not_in_radarr = plex_tmdb_ids - radarr_tmdb_ids
radarr_movies_not_in_plex = radarr_tmdb_ids - plex_tmdb_ids

print(f"\nMovies in Plex but not in Radarr ({len(plex_movies_not_in_radarr)}):")
for tmdb_id in sorted(plex_movies_not_in_radarr):
    print(f" - {plex_movie_id_to_title[tmdb_id]} (tmdbId: {tmdb_id})")

print(f"\nMovies in Radarr (downloaded) but not in Plex ({len(radarr_movies_not_in_plex)}):")
for tmdb_id in sorted(radarr_movies_not_in_plex):
    print(f" - {radarr_movie_id_to_title[tmdb_id]} (tmdbId: {tmdb_id})")

# -----------------------------
# TV SHOW COMPARISONS
# -----------------------------
print("\n" + "="*50)
print("📺 TV SHOW COMPARISON")
print("="*50)

plex_shows_not_in_sonarr = plex_tvdb_ids - sonarr_tvdb_ids
sonarr_shows_not_in_plex = sonarr_tvdb_ids - plex_tvdb_ids

print(f"\nTV Shows in Plex but not in Sonarr ({len(plex_shows_not_in_sonarr)}):")
for tvdb_id in sorted(plex_shows_not_in_sonarr):
    print(f" - {plex_show_id_to_title[tvdb_id]} (tvdbId: {tvdb_id})")

print(f"\nTV Shows in Sonarr (downloaded) but not in Plex ({len(sonarr_shows_not_in_plex)}):")
for tvdb_id in sorted(sonarr_shows_not_in_plex):
    print(f" - {sonarr_show_id_to_title[tvdb_id]} (tvdbId: {tvdb_id})")

# -----------------------------
# SUMMARY
# -----------------------------
print("\n" + "="*50)
print("📊 SUMMARY")
print("="*50)
print(f"Total Movies in Plex: {len(plex_tmdb_ids)}")
print(f"Total Movies in Radarr (downloaded): {len(radarr_tmdb_ids)}")
print(f"Total TV Shows in Plex: {len(plex_tvdb_ids)}")
print(f"Total TV Shows in Sonarr (downloaded): {len(sonarr_tvdb_ids)}")
print(f"\nMovies only in Plex: {len(plex_movies_not_in_radarr)}")
print(f"Movies only in Radarr: {len(radarr_movies_not_in_plex)}")
print(f"TV Shows only in Plex: {len(plex_shows_not_in_sonarr)}")
print(f"TV Shows only in Sonarr: {len(sonarr_shows_not_in_plex)}")
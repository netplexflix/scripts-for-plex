import requests
from plexapi.server import PlexServer
from difflib import SequenceMatcher

VERSION = 1.1

# -----------------------------
# CONFIGURATION
# -----------------------------
PLEX_URL = "http://localhost:32400"
PLEX_TOKEN = "YOUR_PLEX_TOKEN"

RADARR_URL = "http://localhost:7878/api/v3"
RADARR_API_KEY = "YOUR_RADARR_API_KEY"

SONARR_URL = "http://localhost:8989/api/v3"
SONARR_API_KEY = "YOUR_SONARR_API_KEY"

# -----------------------------
# UTILITY FUNCTIONS
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

def normalize_title(title: str) -> str:
    """Normalize title for comparison by removing common variations"""
    import re
    # Convert to lowercase
    title = title.lower()
    # Remove common punctuation and extra spaces
    title = re.sub(r'[:\-\(\)&]', '', title)
    title = re.sub(r'\s+', ' ', title)
    title = title.strip()
    # Remove common country indicators
    title = re.sub(r'\s+(us|uk|au|ca)$', '', title)
    return title

def titles_similar(title1: str, title2: str, threshold: float = 0.85) -> bool:
    """Check if two titles are similar using normalized comparison"""
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    
    # First check for exact match after normalization
    if norm1 == norm2:
        return True
    
    # Then check similarity ratio
    return SequenceMatcher(None, norm1, norm2).ratio() >= threshold

def find_name_matches(plex_dict, external_dict, threshold: float = 0.85):
    """Find potential matches based on title similarity"""
    matches = {}
    for plex_id, plex_title in plex_dict.items():
        for ext_id, ext_title in external_dict.items():
            if titles_similar(plex_title, ext_title, threshold):
                matches[plex_id] = ext_id
                break
    return matches

# -----------------------------
# PLEX DATA FETCHING
# -----------------------------
def fetch_plex_movies():
    print("\n🎬 Fetching Plex movies...")
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    plex_movies = plex.library.section("Movies")

    plex_tmdb_ids = set()
    plex_movie_id_to_title = {}
    movies_without_usable_ids = []
    total_plex_movies = 0
    duplicate_movies = {}

    for movie in plex_movies.all():
        total_plex_movies += 1
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
            # Check for duplicates
            if tmdb_id in plex_movie_id_to_title:
                if tmdb_id not in duplicate_movies:
                    duplicate_movies[tmdb_id] = [plex_movie_id_to_title[tmdb_id]]
                duplicate_movies[tmdb_id].append(movie.title)
            else:
                plex_tmdb_ids.add(tmdb_id)
                plex_movie_id_to_title[tmdb_id] = movie.title
        else:
            movies_without_usable_ids.append(movie.title)
#            print(f"[DEBUG] No usable ID for Plex movie: {movie.title}")
#            print("        GUIDs:", [g.id for g in movie.guids])

    # Print summary of movies without usable IDs
    if movies_without_usable_ids:
        print(f"\n📋 Movies in Plex without usable IDs ({len(movies_without_usable_ids)}):")
        for movie_title in sorted(movies_without_usable_ids):
            print(f" - {movie_title}")
    
    # Print duplicate movies
    if duplicate_movies:
        total_duplicate_entries = sum(len(titles) for titles in duplicate_movies.values())
        total_unique_duplicates = len(duplicate_movies)
        print(f"\n🔄 Duplicate movies ({total_unique_duplicates} unique IDs with {total_duplicate_entries} total entries):")
        for tmdb_id, titles in duplicate_movies.items():
            print(f" - TMDb ID {tmdb_id}:")
            for title in titles:
                print(f"   • {title}")
    
    return plex_tmdb_ids, plex_movie_id_to_title, total_plex_movies, movies_without_usable_ids, duplicate_movies

def fetch_plex_tv_shows():
    print("\n📺 Fetching Plex TV shows...")
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    plex_shows = plex.library.section("TV Shows")

    plex_tvdb_ids = set()
    plex_show_id_to_title = {}
    shows_without_usable_ids = []
    total_plex_shows = 0
    duplicate_shows = {}

    for show in plex_shows.all():
        total_plex_shows += 1
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
            # Check for duplicates
            if tvdb_id in plex_show_id_to_title:
                if tvdb_id not in duplicate_shows:
                    duplicate_shows[tvdb_id] = [plex_show_id_to_title[tvdb_id]]
                duplicate_shows[tvdb_id].append(show.title)
            else:
                plex_tvdb_ids.add(tvdb_id)
                plex_show_id_to_title[tvdb_id] = show.title
        else:
            shows_without_usable_ids.append(show.title)
#            print(f"[DEBUG] No usable ID for Plex TV show: {show.title}")
#            print("        GUIDs:", [g.id for g in show.guids])

    # Print summary of shows without usable IDs
    if shows_without_usable_ids:
        print(f"\n📋 TV Shows in Plex without usable IDs ({len(shows_without_usable_ids)}):")
        for show_title in sorted(shows_without_usable_ids):
            print(f" - {show_title}")
    
    # Print duplicate shows
    if duplicate_shows:
        total_duplicate_entries = sum(len(titles) for titles in duplicate_shows.values())
        total_unique_duplicates = len(duplicate_shows)
        print(f"\n🔄 Duplicate TV shows ({total_unique_duplicates} unique IDs with {total_duplicate_entries} total entries):")
        for tvdb_id, titles in duplicate_shows.items():
            print(f" - TVDb ID {tvdb_id}:")
            for title in titles:
                print(f"   • {title}")
    
    return plex_tvdb_ids, plex_show_id_to_title, total_plex_shows, shows_without_usable_ids, duplicate_shows

# -----------------------------
# ARR DATA FETCHING
# -----------------------------
def fetch_radarr_movies():
    print("\n🎞️ Fetching Radarr movies...")
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

    return radarr_tmdb_ids, radarr_movie_id_to_title

def fetch_sonarr_tv_shows():
    print("\n📡 Fetching Sonarr TV shows...")
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
        has_episodes = show.get("statistics", {}).get("episodeFileCount", 0) > 0
        
        if has_episodes and show.get("tvdbId"):
            tvdb_id = int(show["tvdbId"])
            sonarr_tvdb_ids.add(tvdb_id)
            sonarr_show_id_to_title[tvdb_id] = show["title"]

    return sonarr_tvdb_ids, sonarr_show_id_to_title

# -----------------------------
# COMPARISON FUNCTIONS
# -----------------------------
def compare_movies(plex_tmdb_ids, plex_movie_id_to_title, radarr_tmdb_ids, radarr_movie_id_to_title, movies_without_usable_ids):
    print("\n" + "="*50)
    print("🎬 MOVIE COMPARISON")
    print("="*50)

    plex_movies_not_in_radarr = plex_tmdb_ids - radarr_tmdb_ids
    radarr_movies_not_in_plex = radarr_tmdb_ids - plex_tmdb_ids

    # Find potential name matches for movies with IDs
    plex_unmatched_movies = {id: plex_movie_id_to_title[id] for id in plex_movies_not_in_radarr}
    radarr_unmatched_movies = {id: radarr_movie_id_to_title[id] for id in radarr_movies_not_in_plex}
    movie_name_matches = find_name_matches(plex_unmatched_movies, radarr_unmatched_movies)

    # Now find matches for movies without usable IDs
    if movies_without_usable_ids:
        # Create a temporary dict for movies without IDs (use title as both key and value)
        plex_no_id_dict = {title: title for title in movies_without_usable_ids}
        no_id_matches = find_name_matches(plex_no_id_dict, radarr_unmatched_movies)
        
        # Add these matches to our main matches dict (using a special key format)
        for plex_title, radarr_id in no_id_matches.items():
            movie_name_matches[f"NO_ID:{plex_title}"] = radarr_id
            # Remove from radarr unmatched since we found a match
            radarr_movies_not_in_plex.discard(radarr_id)

    # Remove name matches from unmatched lists
    final_plex_movies_not_in_radarr = plex_movies_not_in_radarr - set(movie_name_matches.keys())
    final_radarr_movies_not_in_plex = radarr_movies_not_in_plex - set(movie_name_matches.values())

    print(f"\nMovies in Plex but not in Radarr ({len(final_plex_movies_not_in_radarr)}):")
    for tmdb_id in sorted(final_plex_movies_not_in_radarr, key=lambda x: plex_movie_id_to_title[x].lower()):
        print(f" - {plex_movie_id_to_title[tmdb_id]} (tmdbId: {tmdb_id})")

    print(f"\nMovies in Radarr (downloaded) but not in Plex ({len(final_radarr_movies_not_in_plex)}):")
    for tmdb_id in sorted(final_radarr_movies_not_in_plex, key=lambda x: radarr_movie_id_to_title[x].lower()):
        print(f" - {radarr_movie_id_to_title[tmdb_id]} (tmdbId: {tmdb_id})")

    if movie_name_matches:
        print(f"\nMovies matched by title (likely same content with different IDs) ({len(movie_name_matches)}):")
        # Sort matches for consistent output
        sorted_matches = []
        for plex_id, radarr_id in movie_name_matches.items():
            if isinstance(plex_id, int):
                sorted_matches.append((plex_id, radarr_id, plex_movie_id_to_title[plex_id], radarr_movie_id_to_title[radarr_id]))
            else:
                plex_title = plex_id.split("NO_ID:")[1]
                sorted_matches.append((None, radarr_id, plex_title, radarr_movie_id_to_title[radarr_id]))
        
        # Sort by title
        sorted_matches.sort(key=lambda x: x[2].lower())
        
        for plex_id, radarr_id, plex_title, radarr_title in sorted_matches:
            if plex_id is not None:
                print(f" - Plex: {plex_title} (tmdbId: {plex_id})")
                print(f"   Radarr: {radarr_title} (tmdbId: {radarr_id})")
            else:
                print(f" - Plex: {plex_title} (no usable ID)")
                print(f"   Radarr: {radarr_title} (tmdbId: {radarr_id})")

    return {
        'plex_only': len(final_plex_movies_not_in_radarr),
        'radarr_only': len(final_radarr_movies_not_in_plex),
        'matched_by_title': len(movie_name_matches)
    }

def compare_tv_shows(plex_tvdb_ids, plex_show_id_to_title, sonarr_tvdb_ids, sonarr_show_id_to_title, shows_without_usable_ids):
    print("\n" + "="*50)
    print("📺 TV SHOW COMPARISON")
    print("="*50)

    plex_shows_not_in_sonarr = plex_tvdb_ids - sonarr_tvdb_ids
    sonarr_shows_not_in_plex = sonarr_tvdb_ids - plex_tvdb_ids

    # Find potential name matches for TV shows with IDs
    plex_unmatched_shows = {id: plex_show_id_to_title[id] for id in plex_shows_not_in_sonarr}
    sonarr_unmatched_shows = {id: sonarr_show_id_to_title[id] for id in sonarr_shows_not_in_plex}
    show_name_matches = find_name_matches(plex_unmatched_shows, sonarr_unmatched_shows)

    # Now find matches for shows without usable IDs
    if shows_without_usable_ids:
        print("\n🔍 Checking for matches with TV shows without usable IDs...")
        # Create a temporary dict for shows without IDs (use title as both key and value)
        plex_no_id_dict = {title: title for title in shows_without_usable_ids}
        no_id_matches = find_name_matches(plex_no_id_dict, sonarr_unmatched_shows)
        
        for plex_title, sonarr_id in no_id_matches.items():
            show_name_matches[f"NO_ID:{plex_title}"] = sonarr_id
            # Remove from sonarr unmatched since we found a match
            sonarr_shows_not_in_plex.discard(sonarr_id)

    # Remove name matches from unmatched lists
    final_plex_shows_not_in_sonarr = plex_shows_not_in_sonarr - set(show_name_matches.keys())
    final_sonarr_shows_not_in_plex = sonarr_shows_not_in_plex - set(show_name_matches.values())

    print(f"\nTV Shows in Plex but not in Sonarr ({len(final_plex_shows_not_in_sonarr)}):")
    for tvdb_id in sorted(final_plex_shows_not_in_sonarr, key=lambda x: plex_show_id_to_title[x].lower()):
        print(f" - {plex_show_id_to_title[tvdb_id]} (tvdbId: {tvdb_id})")

    print(f"\nTV Shows in Sonarr (downloaded) but not in Plex ({len(final_sonarr_shows_not_in_plex)}):")
    for tvdb_id in sorted(final_sonarr_shows_not_in_plex, key=lambda x: sonarr_show_id_to_title[x].lower()):
        print(f" - {sonarr_show_id_to_title[tvdb_id]} (tvdbId: {tvdb_id})")

    if show_name_matches:
        print(f"\nTV Shows matched by title (likely same content with different IDs) ({len(show_name_matches)}):")
        # Sort matches for consistent output
        sorted_show_matches = []
        for plex_id, sonarr_id in show_name_matches.items():
            if isinstance(plex_id, int):
                sorted_show_matches.append((plex_id, sonarr_id, plex_show_id_to_title[plex_id], sonarr_show_id_to_title[sonarr_id]))
            else:
                plex_title = plex_id.split("NO_ID:")[1]
                sorted_show_matches.append((None, sonarr_id, plex_title, sonarr_show_id_to_title[sonarr_id]))
        
        # Sort by title
        sorted_show_matches.sort(key=lambda x: x[2].lower())
        
        for plex_id, sonarr_id, plex_title, sonarr_title in sorted_show_matches:
            if plex_id is not None:
                print(f" - Plex: {plex_title} (tvdbId: {plex_id})")
                print(f"   Sonarr: {sonarr_title} (tvdbId: {sonarr_id})")
            else:
                print(f" - Plex: {plex_title} (no usable ID)")
                print(f"   Sonarr: {sonarr_title} (tvdbId: {sonarr_id})")

    return {
        'plex_only': len(final_plex_shows_not_in_sonarr),
        'sonarr_only': len(final_sonarr_shows_not_in_plex),
        'matched_by_title': len(show_name_matches)
    }

# -----------------------------
# SUMMARY FUNCTION
# -----------------------------
def print_summary(plex_movie_count, radarr_movie_count, plex_show_count, sonarr_show_count, 
                 movie_stats, show_stats, total_plex_movies, total_plex_shows,
                 movies_without_usable_ids, shows_without_usable_ids, 
                 movie_duplicates, show_duplicates):
    print("\n" + "="*50)
    print("📊 SUMMARY")
    print("="*50)
    print(f"Total Movies in Plex: {total_plex_movies}")
    print(f"Total Movies with usable IDs: {plex_movie_count}")
    print(f"Total Movies without usable IDs: {len(movies_without_usable_ids)}")
    print(f"Total duplicate movies (unique IDs): {len(movie_duplicates)}")
    print(f"Total Movies in Radarr (downloaded): {radarr_movie_count}")
    
    print(f"\nTotal TV Shows in Plex: {total_plex_shows}")
    print(f"Total TV Shows with usable IDs: {plex_show_count}")
    print(f"Total TV Shows without usable IDs: {len(shows_without_usable_ids)}")
    print(f"Total duplicate TV shows (unique IDs): {len(show_duplicates)}")
    print(f"Total TV Shows in Sonarr (downloaded): {sonarr_show_count}")
    
    print(f"\nMovies only in Plex: {movie_stats['plex_only']}")
    print(f"Movies only in Radarr: {movie_stats['radarr_only']}")
    print(f"TV Shows only in Plex: {show_stats['plex_only']}")
    print(f"TV Shows only in Sonarr: {show_stats['sonarr_only']}")
    
    # Verify the math
    total_duplicate_movie_entries = sum(len(titles) for titles in movie_duplicates.values())
    total_duplicate_show_entries = sum(len(titles) for titles in show_duplicates.values())
    
    movie_expected_total = plex_movie_count + len(movies_without_usable_ids) + total_duplicate_movie_entries
    show_expected_total = plex_show_count + len(shows_without_usable_ids) + total_duplicate_show_entries

# -----------------------------
# MAIN FUNCTION
# -----------------------------
def main():
    print(f"Plex VS ARRs Check {VERSION} (https://github.com/netplexflix/scripts-for-plex)")
    try:
        # Fetch Plex data
        plex_tmdb_ids, plex_movie_id_to_title, total_plex_movies, movies_without_usable_ids, movie_duplicates = fetch_plex_movies()
        plex_tvdb_ids, plex_show_id_to_title, total_plex_shows, shows_without_usable_ids, show_duplicates = fetch_plex_tv_shows()
        
        # Fetch ARR data
        radarr_tmdb_ids, radarr_movie_id_to_title = fetch_radarr_movies()
        sonarr_tvdb_ids, sonarr_show_id_to_title = fetch_sonarr_tv_shows()
        
        # Perform comparisons
        movie_stats = compare_movies(plex_tmdb_ids, plex_movie_id_to_title, 
                                   radarr_tmdb_ids, radarr_movie_id_to_title,
                                   movies_without_usable_ids)
        
        show_stats = compare_tv_shows(plex_tvdb_ids, plex_show_id_to_title, 
                                    sonarr_tvdb_ids, sonarr_show_id_to_title,
                                    shows_without_usable_ids)
        
        # Print summary
        print_summary(len(plex_tmdb_ids), len(radarr_tmdb_ids), 
                     len(plex_tvdb_ids), len(sonarr_tvdb_ids),
                     movie_stats, show_stats, total_plex_movies, total_plex_shows,
                     movies_without_usable_ids, shows_without_usable_ids,
                     movie_duplicates, show_duplicates)
        
    except Exception as e:
        print(f"❌ Error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main()
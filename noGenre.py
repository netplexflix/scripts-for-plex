from plexapi.server import PlexServer


plex_url = 'http://localhost:32400'
plex_token = 'your_plex_token'

def find_movies_without_genre():
    try:
        plex = PlexServer(plex_url, plex_token)
        
        movies = plex.library.section('Movies')
        
        movies_without_genre = []
        for movie in movies.all():
            if not movie.genres:
                movies_without_genre.append({
                    'title': movie.title,
                    'year': movie.year
                })
        
        if movies_without_genre:
            print("\nMovies without genres:")
            print("=====================")
            for movie in movies_without_genre:
                print(f"{movie['title']} ({movie['year']})")
            print(f"\nTotal movies without genres: {len(movies_without_genre)}")
        else:
            print("No movies found without genres!")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    find_movies_without_genre()
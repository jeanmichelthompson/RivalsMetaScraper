from playwright.sync_api import sync_playwright
from supabase import create_client, Client
import os

# Supabase Configuration
SUPABASE_URL = "https://bqffurypbsbmcuvlsmll.supabase.co"
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
if not SUPABASE_KEY:
    raise ValueError("No API key provided. Please set the API_KEY environment variable.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def scrape_leaderboard(url_character_name: str, db_character_name: str):
    """
    Scrape the leaderboard for a specific character and update the Supabase database.

    :param url_character_name: The character name as it appears in the URL (e.g., "black-panther").
    :param db_character_name: The character name as it should appear in the database (e.g., "Black Panther").
    """
    with sync_playwright() as p:
        # Launch a browser (headless mode)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to the character's leaderboard
        url = f"https://rivalsmeta.com/characters/{url_character_name}/leaderboard"
        print(f"Scraping leaderboard for {db_character_name} from {url}")
        page.goto(url)

        # Wait for the leaderboard table to load
        page.wait_for_selector("div.leaderboard-table")

        # Initialize a list to store all players across all pages
        all_scraped_players = []
        current_page = 1

        while True:
            print(f"Scraping page {current_page}...")

            # Extract leaderboard data for the current page
            rows = page.query_selector_all("div.leaderboard-table tr[class^='rank']")
            for row in rows:
                # Extract player name
                name_element = row.query_selector("div.name")
                player_name = name_element.inner_text() if name_element else "Unknown"

                # Extract rank name (e.g., "Grandmaster 2")
                rank_name_element = row.query_selector("div.rank-info div.name")
                rank_name = rank_name_element.inner_text() if rank_name_element else "Unknown"

                # Extract rank score (e.g., "4,682") and handle missing score
                rank_score_element = row.query_selector("div.rank-info div.score")
                rank_score = (
                    int(rank_score_element.inner_text().strip().replace(",", ""))
                    if rank_score_element
                    else 0
                )

                # Extract matches played
                matches_element = row.query_selector("div.hero div.data div.matches")
                matches_text = matches_element.inner_text() if matches_element else "0 games"
                matches_played = int(matches_text.split(" ")[0])  # Extract numeric value

                # Add the player data to the list as a dictionary (even if they don't meet thresholds yet)
                all_scraped_players.append({
                    "character_name": db_character_name,
                    "rank": None,  # Will assign ranks after sorting
                    "player_name": player_name,
                    "rank_name": rank_name,
                    "score": rank_score,
                    "matches": matches_played
                })

            # Find the "Next" button in pagination
            next_button = page.query_selector("div.pagination div.page.active + div.page button")
            if next_button:
                next_button.click()
                # Wait for the page content to update
                page.wait_for_selector("div.leaderboard-table")
                current_page += 1
            else:
                # No "Next" button means we're on the last page
                print(f"No more pages to scrape for {db_character_name}.")
                break

        # Filter out players who don't meet the thresholds
        filtered_players = [
            player for player in all_scraped_players
            if player["matches"] >= 30 and player["score"] >= 4200
        ]

        # Sort the filtered players by rank score in descending order
        filtered_players.sort(key=lambda x: x["score"], reverse=True)

        # Limit to the top 100 players
        top_100_players = filtered_players[:100]

        # Assign ranks to the top 100 players
        for i, player in enumerate(top_100_players, start=1):
            player["rank"] = i

        # Delete old leaderboard entries for this character
        print(f"Deleting old leaderboard data for {db_character_name}...")
        supabase.table("leaderboards").delete().eq("character_name", db_character_name).execute()

        # Upsert the top 100 players into the database
        print(f"Upserting new leaderboard data for {db_character_name}...")
        response = supabase.table("leaderboards").upsert(top_100_players).execute()
        if response.data:
            print(f"Leaderboard for {db_character_name} updated successfully!")
        else:
            print(f"Failed to update leaderboard for {db_character_name}: {response}")

        # Close the browser
        browser.close()

# List of characters to scrape
characters = [
    ("captain-america", "Captain America"),
    ("doctor-strange", "Doctor Strange"),
    ("groot", "Groot"),
    ("hulk", "Hulk"),
    ("magneto", "Magneto"),
    ("peni-parker", "Peni Parker"),
    ("thor", "Thor"),
    ("venom", "Venom"),
    ("black-panther", "Black Panther"),
    ("black-widow", "Black Widow"),
    ("hawkeye", "Hawkeye"),
    ("hela", "Hela"),
    ("iron-fist", "Iron Fist"),
    ("iron-man", "Iron Man"),
    ("magik", "Magik"),
    ("mister-fantastic", "Mister Fantastic"),
    ("moon-knight", "Moon Knight"),
    ("namor", "Namor"),
    ("psylocke", "Psylocke"),
    ("scarlet-witch", "Scarlet Witch"),
    ("spider-man", "Spider Man"),
    ("squirrel-girl", "Squirrel Girl"),
    ("star-lord", "Star Lord"),
    ("storm", "Storm"),
    ("the-punisher", "The Punisher"),
    ("winter-soldier", "Winter Soldier"),
    ("wolverine", "Wolverine"),
    ("adam-warlock", "Adam Warlock"),
    ("cloak-dagger", "Cloak & Dagger"),
    ("invisible-woman", "Invisible Woman"),
    ("jeff-the-land-shark", "Jeff The Land Shark"),
    ("loki", "Loki"),
    ("luna-snow", "Luna Snow"),
    ("mantis", "Mantis"),
    ("rocket-raccoon", "Rocket Raccoon")
]

# Run the scraper for all characters
for url_name, db_name in characters:
    scrape_leaderboard(url_name, db_name)
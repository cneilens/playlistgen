from openai import OpenAI

import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import os
import time
from googleapiclient.errors import HttpError
import csv

# needs follow modules to be installed via pip
# google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client openai

# Initialize OpenAI API client
# Replace with your OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# Replace with your OAuth 2.0 Client ID and Secret
CLIENT_SECRETS_FILE = "client_secret.json"

# Scopes for YouTube API
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def get_additional_artists2(artists):
    prompt = f"Given this list of artists '{', '.join(artists)}' can you suggest similar artists from the same genres. Please never suggest Coldplay. Please respond with only the artists names with each artist on a new line. Please do not number each artist."
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        n=1,
        stop=None,
        temperature=0.5
    )
    additional_artists = response.choices[0].message.content.strip().splitlines()
    return [artist.strip() for artist in additional_artists if artist.strip()]

def get_playlist_for_artists(artists):
    prompt = f"Given a list of artists '{artists}' List upto 5 popular songs by each artist. Please respond with only the artist and song names in the form <artist> - <song>. Please do not number each song."
    response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "user", "content": prompt}
    ],
    n=1,
    stop=None,
    temperature=0.5)
    artist_songs = response.choices[0].message.content.strip().splitlines()
    artist_songs_dict = {}
    for line in artist_songs:
        if line:
            try:
                artist, song = line.split(" - ", 1)
            except ValueError:
                print(f"Error parsing line: {line}")
                continue
            artist = artist.strip()
            song = song.strip()
            if artist not in artist_songs_dict:
                artist_songs_dict[artist] = []
            artist_songs_dict[artist].append(song)
    return artist_songs_dict


def create_playlist(artists, add_more_artists=False):
    all_artists = artists
    if add_more_artists:
       all_artists += get_additional_artists2(all_artists)

    playlist = get_playlist_for_artists(all_artists)

    return playlist, all_artists

def print_playlist(playlist):
    output = ""
    for artist, songs in playlist.items():
        output += f"{artist}:\n"
        for song in songs:
            output += f"  - {song}\n"
        output += "\n"
    return output

def load_artists():
    file_path = filedialog.askopenfilename(title="Open Artist List", filetypes=[("Text Files", "*.txt")])
    if not file_path:
        return

    with open(file_path, 'r') as file:
        artists = [line.strip() for line in file.readlines() if line.strip()]

    return artists

def addSongToYoutubePlaylist(youtube_service, video_id, playlist_id): # Adds a song to the playlist given
    max_retries = 5
    retry_count = 0
    backoff_time = 1  # In seconds

    while retry_count < max_retries:
        try:
            request = youtube_service.playlistItems().insert(
                part="snippet",
                body={
                    'snippet': {
                        'playlistId': playlist_id,
                        'resourceId': {
                            'kind': 'youtube#video',
                            'videoId': video_id
                        }
                    }
                }
            )
            print(video_id)
            response = request.execute()
            return response
        except HttpError as e:
            if e.resp.status == 409 and 'SERVICE_UNAVAILABLE' in str(e):
                retry_count += 1
                print(f"Attempt {retry_count} failed. Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
                backoff_time *= 2  # Exponential backoff
            else:
                raise
    raise Exception("Failed to add the song to the playlist after multiple retries.")

def generate_youtube_playlist(playlist):
    # Authenticate to YouTube API
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_local_server(port=0)
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

    # Create a new YouTube playlist
    request = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": "Generated Playlist",
                "description": "A playlist generated from the provided list of artists and songs.",
                "tags": ["generated", "playlist"],
                "defaultLanguage": "en"
            },
            "status": {
                "privacyStatus": "private"
            }
        }
    )
    response = request.execute()
    playlist_id = response['id']

    # Search for each song on YouTube and add it to the playlist
    for artist, songs in playlist.items():
        for song in songs:
            query = f"{artist} - {song}"
            search_response = youtube.search().list(
                part="snippet",
                maxResults=1,
                q=query,
                type="video"
            ).execute()

            if search_response["items"]:
                video_id = search_response["items"][0]["id"]["videoId"]
                addSongToYoutubePlaylist(youtube, video_id, playlist_id)

    messagebox.showinfo("YouTube Playlist Created", "Your YouTube playlist has been created successfully.")

def generate_playlist():
    artists = load_artists()
    if not artists:
        messagebox.showwarning("No Artists Loaded", "Please load a list of artists first.")
        return

    add_more_artists = add_more_var.get()
    playlist, all_artists = create_playlist(artists, add_more_artists)

    while add_more_artists:
        add_even_more = messagebox.askyesno(f"Add Even More Artists", f"There are currently {len(all_artists)} artists in your list. Do you want to add even more artists per genre?")
        if not add_even_more:
            break
        additional_artists = get_additional_artists2(all_artists)
        additional_playlist = get_playlist_for_artists(additional_artists)
        for artist, songs in additional_playlist.items():
            if artist not in playlist:
                playlist[artist] = songs
        all_artists += additional_artists

    result_text = print_playlist(playlist)
    result_box.delete(1.0, tk.END)
    result_box.insert(tk.END, result_text)

    # create_youtube_playlist = messagebox.askyesno("Create YouTube Playlist", "Do you want to create a YouTube playlist with these songs?")
    # if create_youtube_playlist:
    #     generate_youtube_playlist(playlist)


    # Specify the file path for the CSV file
    csv_file = "./playlist.csv"

    print(f"Saving the playlist with {len(playlist.keys())} artists to {csv_file}...")

    # Open the CSV file in write mode
    with open(csv_file, mode='w', newline='') as file:
        writer = csv.writer(file)

        # Write the header row
        writer.writerow(["artist", "song"])

        # Write each artist and song to the CSV file
        for artist, songs in playlist.items():
            for song in songs:
                print(f"{artist} - {song}")
                writer.writerow([artist, song])

        # Display a message to indicate that the CSV file has been created
        messagebox.showinfo("CSV File Created", f"The playlist has been saved to {csv_file}.")
            

# Create the main window
window = tk.Tk()
window.title("Playlist Generator")

# Add a checkbox for adding more artists
add_more_var = tk.BooleanVar()
add_more_var.set(True)
add_more_check = tk.Checkbutton(window, text="Add more artists per genre", variable=add_more_var)
add_more_check.pack(pady=10)

# Add a button to generate the playlist
generate_button = tk.Button(window, text="Load Artists and Generate Playlist", command=generate_playlist)
generate_button.pack(pady=10)

# Add a scrolled text box to display the playlist
result_box = scrolledtext.ScrolledText(window, wrap=tk.WORD, width=80, height=20)
result_box.pack(padx=10, pady=10)


# Run the Tkinter event loop
window.mainloop()

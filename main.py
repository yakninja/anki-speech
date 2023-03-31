import os
import json
from google.oauth2.credentials import Credentials
from google.cloud import texttospeech
from pydub import AudioSegment
from pydub.playback import play
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import re
import zipfile
import sqlite3
import hashlib
import time

# see https://cloud.google.com/text-to-speech/docs/voices

SOURCE_LANGUAGE = 'sr-RS'
#SOURCE_LANGUAGE = 'pt-PT'
VOICE_NAME = 'sr-RS-Standard-A'
#VOICE_NAME = 'pt-PT-Wavenet-A'

# Set the scope for the Text-to-Speech API
SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

# Set the path to the client ID and secret JSON file that you downloaded
CLIENT_SECRET_FILE = 'client_secret.json'

# If modifying these scopes, delete the file token.json.
creds = None

# The file token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)

# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRET_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

# set up text-to-speech client using credentials
speechClient = texttospeech.TextToSpeechClient(credentials=creds)

# set voice parameters
voice = texttospeech.VoiceSelectionParams(
    language_code=SOURCE_LANGUAGE,
    name=VOICE_NAME,
    ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
)

# set audio parameters
audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3
)


def escape_string(s):
    s = re.sub(r'\W+', '_', s).strip('_')[:255]
    return s


PACKAGE_FILE = 'package.apkg'
PACKAGE_RESULT_FILE = 'package-result.apkg'
PACKAGE_DIR = 'package'

with zipfile.ZipFile(PACKAGE_FILE, 'r') as zip_ref:
    zip_ref.extractall(PACKAGE_DIR)

# Parse the media file into a dictionary
with open(f'{PACKAGE_DIR}/media', 'r') as f:
    media_dict = json.load(f)

# Get the maximum integer key value from the media_dict
media_index = max(map(int, media_dict.keys())) + 1

# Connect to the database file
conn = sqlite3.connect(f'{PACKAGE_DIR}/collection.anki21')
conn.row_factory = sqlite3.Row

# Create a cursor object
cursor = conn.cursor()

cursor.execute('SELECT * FROM notes ORDER BY id')

# Loop through the result, convert text to audio and modify everything
for row in cursor.fetchall():
    if re.search(r'\[sound:.+?\.mp3\]', row['flds']):
        continue
    print(row['id'], dict(row))

    id_ = row['id']
    flds = row['flds'].replace('&nbsp;', ' ').strip()
    front, back = flds.split('\x1f')

    synthesis_input = texttospeech.SynthesisInput(
        ssml='<speak>' + front + '</speak>')
    response = speechClient.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    filename = escape_string(front) + '.mp3'
    media_file = f'{PACKAGE_DIR}/{media_index}'
    with open(media_file, 'wb') as out:
        out.write(response.audio_content)

    print(f'Audio content written to "{media_index}"')
    media_dict[media_index] = filename
    front = f'{front}<br>[sound:{filename}]'
    media_index += 1
    
    #sound = AudioSegment.from_file(media_file, format='mp3')
    #play(sound)

    # Create a sha1 hash of sfld
    sfld = front
    sha1 = hashlib.sha1(sfld.encode()).hexdigest()

    # Take the first 8 hex digits of the hash and convert to integer
    csum = int(sha1[:8], 16)
    print('csum', row['csum'], csum)

    # Update the row with the new values
    cursor.execute('UPDATE notes SET flds = ?, sfld = ?, csum = ?, mod = ? WHERE id = ?',
                   ('\x1f'.join([front, back]), sfld, csum, int(time.time()), id_))
    conn.commit()

    #break

# Close the database connection
conn.close()

# Write the updated media_dict to the media file
with open(f'{PACKAGE_DIR}/media', 'w') as f:
    json.dump(media_dict, f)


# Compress the package directory into a new archive
with zipfile.ZipFile(PACKAGE_RESULT_FILE, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk('package'):
        for file in files:
            zipf.write(os.path.join(root, file), os.path.relpath(
                os.path.join(root, file), 'package'))

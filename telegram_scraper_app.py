import streamlit as st
from telethon import TelegramClient, events, sync
import re
import asyncio
import csv
from datetime import datetime
import os
import tempfile
import pandas as pd
import io
import zipfile

# Session state management for authentication flow
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'client' not in st.session_state:
    st.session_state.client = None
if 'awaiting_code' not in st.session_state:
    st.session_state.awaiting_code = False
if 'messages_df' not in st.session_state:
    st.session_state.messages_df = None
if 'images' not in st.session_state:
    st.session_state.images = {}

st.title("Telegram Channel Scraper")
st.write("This app allows you to scrape data from the highscorechannel on Telegram.")

# Function to handle authentication
async def authenticate(api_id, api_hash, phone):
    try:
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.send_code_request(phone)
            st.session_state.client = client
            st.session_state.awaiting_code = True
        else:
            st.session_state.client = client
            st.session_state.authenticated = True
        
        return True
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return False

# Function to verify the code
async def verify_code(code):
    try:
        await st.session_state.client.sign_in(st.session_state.phone, code)
        st.session_state.authenticated = True
        st.session_state.awaiting_code = False
        return True
    except Exception as e:
        st.error(f"Verification error: {e}")
        return False

# Function to scrape messages
async def scrape_channel(message_limit):
    client = st.session_state.client
    channel_username = 'highscorechannel'
    
    try:
        # Get entity (channel)
        entity = await client.get_entity(channel_username)
        
        # Create temporary directory for images
        with tempfile.TemporaryDirectory() as temp_dir:
            # Define a list to store the parsed data
            betting_tips = []
            
            # Get only the specified most recent messages
            progress_text = st.empty()
            progress_bar = st.progress(0)
            
            progress_text.text(f"Fetching {message_limit} most recent messages...")
            messages = await client.get_messages(entity, limit=message_limit)
            
            for i, message in enumerate(messages):
                progress_bar.progress((i + 1) / len(messages))
                progress_text.text(f"Processing message {i+1} of {len(messages)}")
                
                try:
                    # Parse the text message
                    data = {}
                    message_id = message.id
                    data['message_id'] = message_id
                    
                    # Skip if no text
                    if not message.text:
                        continue
                        
                    # Extract league/tournament info
                    league_match = re.search(r'(\w+):\s+(.*?)(?:\s-|\n|$)', message.text, re.MULTILINE)
                    if league_match:
                        data['country'] = league_match.group(1)
                        data['league'] = league_match.group(2).strip()
                    
                    # Extract teams
                    teams = re.findall(r'(\w+\s*\w*)\s*U\d+', message.text)
                    if len(teams) >= 2:
                        data['team1'] = teams[0] + " U23"
                        data['team2'] = teams[1] + " U23"
                    
                    # Extract date and time
                    date_match = re.search(r'(\d{2}\.\d{2}\.\d{4}\s*\d{2}:\d{2}\s*[AP]M)', message.text)
                    if date_match:
                        data['datetime'] = date_match.group(1)
                    
                    # Extract tip
                    tip_match = re.search(r'Tip\s*:\s*(.*?)(?:\n|$)', message.text)
                    if tip_match:
                        data['tip'] = tip_match.group(1).strip()
                    
                    # Extract odds
                    odds_match = re.search(r'Odd\s*:\s*([\d.]+)', message.text)
                    if odds_match:
                        data['odds'] = float(odds_match.group(1))
                    
                    # Extract safety percentage
                    safety_match = re.search(r'Safety\s*:\s*(\d+)%', message.text)
                    if safety_match:
                        data['safety'] = int(safety_match.group(1))
                    
                    # Extract reactions/stats
                    reactions = re.findall(r'([\u2764\ufe0f\ud83d\udc4d\ud83d\ude4f\ud83c\udf89\ud83c\udf8a\ud83e\udd70\ud83d\udca6\ud83d\udc51])\s*(\d+)', message.text)
                    for emoji, count in reactions:
                        emoji_name = {
                            '❤️': 'heart',
                            '👍': 'thumbs_up',
                            '🙏': 'prayer',
                            '🎉': 'celebration',
                            '🎊': 'confetti',
                            '😍': 'heart_eyes',
                            '💦': 'sweat',
                            '👑': 'crown'
                        }.get(emoji, emoji)
                        
                        data[f'reaction_{emoji_name}'] = int(count)
                    
                    # Add message date from Telegram
                    data['message_date'] = message.date.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Add message views if available
                    if hasattr(message, 'views') and message.views:
                        data['views'] = message.views
                    
                    # Check if the message has a photo
                    if message.photo:
                        # Generate a unique filename
                        image_filename = f"{message_id}_{data.get('team1', 'unknown')}_{data.get('team2', 'unknown')}".replace(' ', '_')
                        image_path = os.path.join(temp_dir, f"{image_filename}.jpg")
                        
                        # Download the photo
                        await message.download_media(image_path)
                        
                        # Read image and store in session state
                        with open(image_path, 'rb') as img_file:
                            st.session_state.images[message_id] = img_file.read()
                            
                        data['has_image'] = True
                    else:
                        data['has_image'] = False
                    
                    # Append to our list if we have meaningful data
                    betting_tips.append(data)
                    
                except Exception as e:
                    st.warning(f"Error parsing message {i}: {e}")
            
            progress_bar.empty()
            progress_text.empty()
            
            if betting_tips:
                # Convert to DataFrame for display
                df = pd.DataFrame(betting_tips)
                st.session_state.messages_df = df
                return df
            else:
                st.warning("No data was parsed successfully")
                return None
                
    except Exception as e:
        st.error(f"Error scraping channel: {e}")
        return None

# StringSession class to handle session string
class StringSession:
    def __init__(self, string=None):
        self.string = string

    def save(self):
        return self.string

    def load(self, string):
        self.string = string

# Create a function to download data as CSV
def get_csv_download_link(df):
    csv = df.to_csv(index=False)
    csv_bytes = csv.encode()
    b64 = base64.b64encode(csv_bytes).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="telegram_data.csv">Download CSV</a>'
    return href

# Create a function to download images as a zip file
def get_images_download_link(images):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        for msg_id, img_data in images.items():
            zip_file.writestr(f"{msg_id}.jpg", img_data)
    
    zip_buffer.seek(0)
    b64 = base64.b64encode(zip_buffer.getvalue()).decode()
    href = f'<a href="data:application/zip;base64,{b64}" download="telegram_images.zip">Download Images</a>'
    return href

# Main app flow
import base64

# Authentication section
if not st.session_state.authenticated:
    if not st.session_state.awaiting_code:
        with st.form("auth_form"):
            api_id = st.text_input("API ID", type="password")
            api_hash = st.text_input("API Hash", type="password")
            phone = st.text_input("Phone Number (with country code)", placeholder="+1234567890")
            submit_button = st.form_submit_button("Send Authentication Code")
            
            if submit_button:
                st.session_state.api_id = api_id
                st.session_state.api_hash = api_hash
                st.session_state.phone = phone
                
                asyncio.run(authenticate(api_id, api_hash, phone))
                st.rerun()
    else:
        with st.form("code_form"):
            code = st.text_input("Enter the code received on Telegram", max_chars=6)
            verify_button = st.form_submit_button("Verify Code")
            
            if verify_button:
                if asyncio.run(verify_code(code)):
                    st.success("Authentication successful!")
                    st.rerun()
else:
    # Scraping section
    st.write("You are authenticated! Now you can scrape messages from the channel.")
    
    with st.form("scraping_form"):
        message_limit = st.number_input("Number of recent messages to scrape", min_value=1, max_value=100, value=10)
        scrape_button = st.form_submit_button("Scrape Messages")
        
        if scrape_button:
            with st.spinner("Scraping messages..."):
                df = asyncio.run(scrape_channel(message_limit))
                if df is not None:
                    st.success(f"Successfully scraped {len(df)} messages!")
    
    # Display results if available
    if st.session_state.messages_df is not None:
        st.subheader("Scraped Data")
        st.dataframe(st.session_state.messages_df)
        
        # Download buttons
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(get_csv_download_link(st.session_state.messages_df), unsafe_allow_html=True)
        
        if st.session_state.images:
            with col2:
                st.markdown(get_images_download_link(st.session_state.images), unsafe_allow_html=True)
        
        # Display images
        if st.session_state.images:
            st.subheader("Images")
            image_cols = st.columns(3)
            
            for i, (msg_id, img_data) in enumerate(st.session_state.images.items()):
                col_idx = i % 3
                with image_cols[col_idx]:
                    st.image(img_data, caption=f"Message ID: {msg_id}", use_column_width=True)
    
    # Logout button
    if st.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
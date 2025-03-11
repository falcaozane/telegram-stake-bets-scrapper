from telethon import TelegramClient, events, sync
from telethon.tl.functions.messages import GetHistoryRequest
import re
import asyncio
import csv
from datetime import datetime
import os
import shutil

# You need to get these from https://my.telegram.org/
api_id = ''
api_hash = ''
phone = ''  # Your phone number with country code
channel_username = 'highscorechannel'  # The channel you want to scrape

async def scrape_channel():
    # Create the client and connect
    client = TelegramClient('session_name', api_id, api_hash)
    await client.start(phone)
    print("Client Created")
    
    # Get entity (channel)
    entity = await client.get_entity(channel_username)
    
    # Define a list to store the parsed data
    betting_tips = []
    
    # Create directory for images
    images_dir = "telegram_images"
    os.makedirs(images_dir, exist_ok=True)
    
    # Get messages
    # Adjust limit as needed
    messages = await client.get_messages(entity, limit=100)
    
    for i, message in enumerate(messages):
        try:
            # Parse the text message
            data = {}
            message_id = message.id
            data['message_id'] = message_id
            
            # Skip if no text
            if not message.text:
                continue
                
            # Extract league/tournament info
            league_match = re.search(r'PORTUGAL: (.*?)$', message.text, re.MULTILINE)
            if league_match:
                data['league'] = league_match.group(1).strip()
            
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
            tip_match = re.search(r'Tip\s*:\s*(.*?)$', message.text, re.MULTILINE)
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
            likes = re.search(r'❤️\s*(\d+)', message.text)
            if likes:
                data['likes'] = int(likes.group(1))
                
            prayers = re.search(r'🙏\s*(\d+)', message.text)
            if prayers:
                data['prayers'] = int(prayers.group(1))
            
            thumbs_up = re.search(r'👍\s*(\d+)', message.text)
            if thumbs_up:
                data['thumbs_up'] = int(thumbs_up.group(1))
            
            # Add message date from Telegram
            data['message_date'] = message.date.strftime('%Y-%m-%d %H:%M:%S')
            
            # Add message views if available
            if hasattr(message, 'views') and message.views:
                data['views'] = message.views
            
            # Check if the message has a photo
            if message.photo:
                # Generate a unique filename
                image_filename = f"{message_id}_{data.get('team1', 'unknown')}_{data.get('team2', 'unknown')}".replace(' ', '_')
                image_path = os.path.join(images_dir, f"{image_filename}.jpg")
                
                # Download the photo
                await message.download_media(image_path)
                data['image_path'] = image_path
                print(f"Downloaded image: {image_path}")
            
            # Append to our list if we have meaningful data
            if 'tip' in data and 'team1' in data:
                betting_tips.append(data)
                print(f"Parsed message {message_id}: {data['team1']} vs {data['team2']} - {data['tip']}")
            
        except Exception as e:
            print(f"Error parsing message {i}: {e}")
    
    # Save to CSV
    if betting_tips:
        filename = f"telegram_betting_tips_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = set()
            for tip in betting_tips:
                fieldnames.update(tip.keys())
            
            writer = csv.DictWriter(csvfile, fieldnames=list(fieldnames))
            writer.writeheader()
            writer.writerows(betting_tips)
        
        print(f"Data saved to {filename}")
        print(f"Images saved to {images_dir}/")
    else:
        print("No data was parsed successfully")
    
    await client.disconnect()

# Run the async function
asyncio.run(scrape_channel())
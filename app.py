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
phone = ''
channel_username = 'highscorechannel'
message_limit = 10

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
    
    # Get only the 10 most recent messages
    messages = await client.get_messages(entity, limit=message_limit)
    
    print(f"Fetching {message_limit} most recent messages...")
    
    for i, message in enumerate(messages):
        try:
            # Parse the text message
            data = {}
            message_id = message.id
            data['message_id'] = message_id
            
            # Skip if no text
            if not message.text:
                continue

            # Extract country/league info
            country_league_match = re.search(r'([A-Z]+):\s*(.*?)(?:\s*-\s*|\s+ROUND|\s+CLAUSURA)', message.text, re.MULTILINE)
            if country_league_match:
                data['country'] = country_league_match.group(1).strip()
                data['league'] = country_league_match.group(2).strip()
            
            # Try to extract match teams
            team_match = re.search(r'([\w\.\s]+)\s*U23\s*(?:vs|\-)\s*([\w\.\s]+)\s*U23', message.text, re.IGNORECASE)
            if team_match:
                data['team1'] = team_match.group(1).strip()
                data['team2'] = team_match.group(2).strip()
            else:
                # Try alternate team format (from the image)
                team_match = re.search(r'([\w\.\s]+?)\s*U23[\s\n]+([\w\.\s]+?)\s*U23', message.text, re.IGNORECASE)
                if team_match:
                    data['team1'] = team_match.group(1).strip()
                    data['team2'] = team_match.group(2).strip()
                else:
                    # Try without U23 suffix
                    team_match = re.search(r'([\w\.\s]+?)\s+(?:vs|\-)\s+([\w\.\s]+?)(?:\s+|$)', message.text)
                    if team_match:
                        data['team1'] = team_match.group(1).strip()
                        data['team2'] = team_match.group(2).strip()
            
            # Extract match score if available
            score_match = re.search(r'(\d+)\s*-\s*(\d+)', message.text)
            if score_match:
                data['score'] = f"{score_match.group(1)}-{score_match.group(2)}"
                data['team1_score'] = int(score_match.group(1))
                data['team2_score'] = int(score_match.group(2))
            
            # Extract date and time (adjusted for multiple formats)
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4}\s*\d{2}:\d{2}\s*(?:AM|PM))', message.text)
            if date_match:
                data['match_datetime'] = date_match.group(1)
            
            # Extract tip
            tip_match = re.search(r'Tip\s*:\s*([^\n]+)', message.text)
            if tip_match:
                data['tip'] = tip_match.group(1).strip()
            
            # Extract odds
            odds_match = re.search(r'Odd\s*:\s*([\d\.]+)', message.text)
            if odds_match:
                data['odds'] = float(odds_match.group(1))
            
            # Extract safety percentage
            safety_match = re.search(r'Safety\s*:\s*(\d+)%', message.text)
            if safety_match:
                data['safety'] = int(safety_match.group(1))
            
            # Extract promotional text
            promo_texts = []
            promo_matches = re.finditer(r'(We are the biggest channel|Congratulations Everyone|Tell me if you\'re ready|Prepare For The Last Dance|I need you guys to put all)[^\n]+', message.text)
            for match in promo_matches:
                promo_texts.append(match.group(0))
            if promo_texts:
                data['promo_text'] = " | ".join(promo_texts)
            
            # Extract various reaction emojis
            reactions = {
                'star': r'⭐\s*(\d+)',
                'heart': r'❤️\s*(\d+)',
                'thumbs_up': r'👍\s*(\d+)', 
                'clap': r'👏\s*(\d+)',
                'fire': r'🔥\s*(\d+)',
                'trophy': r'🏆\s*(\d+)',
                'hundred': r'💯\s*(\d+)',
                'prayer': r'🙏\s*(\d+)',
                'eyes': r'👀\s*(\d+)',
                'tada': r'🎉\s*(\d+)',
                'money': r'💰\s*(\d+)',
                'lightning': r'⚡\s*(\d+)',
                'bell': r'🔔\s*(\d+)',
                'red_circle': r'🔴\s*(\d+)'
            }
            
            for reaction_name, pattern in reactions.items():
                # Find all occurrences and add up their values
                matches = re.finditer(pattern, message.text)
                total = 0
                for match in matches:
                    total += int(match.group(1))
                if total > 0:
                    data[reaction_name] = total
            
            # Extract view count
            view_matches = re.finditer(r'(\d+(?:\.\d+)?[KM]?)\s*(?:👁)', message.text)
            for match in view_matches:
                view_text = match.group(1)
                multiplier = 1
                
                if 'K' in view_text:
                    multiplier = 1000
                    view_text = view_text.replace('K', '')
                elif 'M' in view_text:
                    multiplier = 1000000
                    view_text = view_text.replace('M', '')
                
                try:
                    data['views'] = float(view_text) * multiplier
                except ValueError:
                    pass
            
            # Extract timestamp from message
            timestamp_match = re.search(r'(\d{2}:\d{2}\s*(?:AM|PM))\s*$', message.text, re.MULTILINE)
            if timestamp_match:
                data['post_time'] = timestamp_match.group(1)
            
            # Add message date from Telegram
            data['message_date'] = message.date.strftime('%Y-%m-%d %H:%M:%S')
            
            # Add message views if available from Telegram API
            if hasattr(message, 'views') and message.views:
                data['telegram_views'] = message.views
            
            # Check if the message has a photo
            if message.photo:
                # Generate a unique filename
                team_str = f"{data.get('team1', '')}_{data.get('team2', '')}"
                if not team_str.strip('_'):
                    team_str = 'unknown_teams'
                
                team_str = ''.join(e for e in team_str if e.isalnum() or e == '_')
                image_filename = f"{message_id}_{team_str}"
                image_path = os.path.join(images_dir, f"{image_filename}.jpg")
                
                # Download the photo
                await message.download_media(image_path)
                data['image_path'] = image_path
                print(f"Downloaded image: {image_path}")
            
            # Print the extracted data for debugging
            print(f"\nExtracted data for message {message_id}:")
            for key, value in data.items():
                print(f"  {key}: {value}")
            
            # Append to our list (we'll save all messages with any data)
            betting_tips.append(data)
            
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
        
        print(f"\nData saved to {filename} with {len(betting_tips)} records")
        print(f"Images saved to {images_dir}/")
    else:
        print("No data was parsed successfully")
    
    await client.disconnect()

# Run the async function
asyncio.run(scrape_channel())
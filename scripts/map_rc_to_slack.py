#!/usr/bin/env python3
"""
Rocket.Chat to Slack Data Migration Script

This script converts Rocket.Chat MongoDB data to Slack export format.
It processes users, channels, and messages from a Rocket.Chat database
and creates a Slack-compatible export structure.

Usage:
    python scripts/map_rc_to_slack.py --mongo mongodb://localhost:27017 --db rocketchat --out ./examples/slack_export --csv ./examples/messages_export.csv --json-dir ./examples/slack_export_msgs

Requirements:
    - MongoDB connection to Rocket.Chat database
    - CSV export of messages (if available)
    - Python dependencies: pymongo, pandas
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import logging

# Configure logging for better debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import pymongo
    from pymongo import MongoClient
except ImportError:
    logger.error("pymongo is required. Install with: pip install pymongo")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    logger.error("pandas is required. Install with: pip install pandas")
    sys.exit(1)

# Initialize global statistics for tracking export progress
stats = {
    "users": 0,
    "channels": {
        "public": 0,
        "private": 0,
        "dm": 0,
        "group_dm": 0
    },
    "messages": {
        "mongodb": 0,
        "json_files": 0
    }
}

# ---------- Helper Functions ----------
def slug(name):
    """Convert Rocket.Chat name to a Slack-safe channel name"""
    return re.sub(r'[^a-z0-9_-]', '-', name.lower())[:80]

def make_user_entry(rc_user, uid):
    """
    Convert a Rocket.Chat user document to Slack user format.
    
    Args:
        rc_user: User document from Rocket.Chat MongoDB
        uid: Unique identifier for the user
        
    Returns:
        dict: User entry in Slack import format
    """
    # Try to extract email with different possible structures
    email = ""
    if "emails" in rc_user:
        emails = rc_user.get("emails")
        if isinstance(emails, list) and len(emails) > 0 and "address" in emails[0]:
            email = emails[0]["address"]
        elif isinstance(emails, dict) and "0" in emails and "address" in emails["0"]:
            email = emails["0"]["address"]
    
    return {
        "id": f"U{uid:07d}",             # placeholder; Slack will re-ID
        "name": rc_user["username"],
        "deleted": not rc_user.get("active", True),
        "profile": {
            "real_name": rc_user.get("name", rc_user["username"]),
            "email": email
        }
    }

def make_room_entry(rc_room, is_private):
    """
    Convert a Rocket.Chat room document to Slack channel format.
    
    Args:
        rc_room: Room document from Rocket.Chat MongoDB
        is_private: Boolean indicating if the room is private
        
    Returns:
        dict: Room entry in Slack import format
    """
    # For direct messages that don't have names
    if "name" not in rc_room:
        # Use usernames if available
        if "usernames" in rc_room:
            room_name = "-".join(sorted(rc_room["usernames"]))
        # Otherwise use the room ID
        else:
            room_name = f"dm-{rc_room['_id']}"
    else:
        room_name = rc_room["name"]
        
    return {
        "id": f"C{rc_room['_id']}",      # placeholder
        "name": slug(room_name),
        "created": int(rc_room["ts"].timestamp()),
        "is_archived": bool(rc_room.get("archived")),
        "is_private": is_private,
        # Slack ignores members on import, but include for completeness
    }

# Add CSV message formatting functions
def escape_for_csv(text):
    """
    Properly escape text for CSV format according to Slack import requirements:
    - Double quotes need to be escaped with another double quote
    - Preserve backslashes for proper escaping
    - Preserve newlines within quoted text
    - Handle @mentions properly
    """
    if text is None:
        return ""
        
    # First, handle double quotes by replacing with two double quotes
    # This is the CSV standard for escaping quotes
    escaped_text = text.replace('"', '""')
    
    # Keep backslashes as is - they'll be treated as escape characters in Slack
    # No special handling needed as we're already escaping double quotes with double quotes
    
    # @mentions are passed through as is (they're handled by Slack importer)
    
    return escaped_text

def prepare_message_for_csv(text, max_length=4000):
    """
    Prepare message text for CSV export with proper formatting.
    
    This function:
    1. Escapes text for CSV format according to Slack import requirements
    2. Splits long messages into parts if they exceed max_length characters
    
    Args:
        text: The message text to process
        max_length: Maximum length per message part (default: 4000)
        
    Returns:
        list: A list of processed message parts ready for CSV export
    """
    if not text:
        return [""]
        
    # Escape double quotes for CSV
    escaped_text = text.replace('"', '""')
    
    # If text fits within limit, return as single part
    if len(escaped_text) <= max_length:
        return [escaped_text]
    
    # Otherwise, split into parts
    parts = []
    total_length = len(escaped_text)
    num_parts = (total_length + max_length - 1) // max_length  # Ceiling division
    
    for i in range(num_parts):
        start = i * max_length
        end = min(start + max_length, total_length)
        
        # Extract this segment and add part indicator
        segment = escaped_text[start:end]
        
        # Add part indicator at beginning so it doesn't get cut off
        part_with_indicator = f"[Part {i+1}/{num_parts}] {segment}"
        
        parts.append(part_with_indicator)
    
    return parts

def process_message_content(msg):
    """
    Process and extract comprehensive message content from Rocket.Chat message.
    
    This function handles:
    - Basic message text
    - User mentions
    - File attachments
    - Message reactions
    - Embedded content
    
    Args:
        msg: Message document from Rocket.Chat MongoDB
        
    Returns:
        str: Processed message content ready for export
    """
    content = msg.get('msg', '')
    
    # Handle mentions already in the message
    if 'mentions' in msg and msg['mentions']:
        # This is just for tracking - the mentions are already in the text
        # as @username format, we just need to preserve them
        pass
    
    # Handle attachments
    if 'attachments' in msg and msg['attachments']:
        for attachment in msg['attachments']:
            # Add attachment description if available
            if 'description' in attachment and attachment['description']:
                if content:
                    content += "\n"
                # If description contains mention markdown, preserve it
                desc = attachment.get('description', '')
                if 'descriptionMd' in attachment:
                    for md_item in attachment['descriptionMd']:
                        if md_item.get('type') == 'MENTION_USER':
                            # Replace placeholder with proper @mention format
                            user_value = md_item.get('value', {}).get('value', '')
                            desc = desc.replace(f"@{user_value}", f"@{user_value}")
                
                content += f"[Attachment: {desc}]"
            elif 'title' in attachment:
                if content:
                    content += "\n"
                content += f"[Attachment: {attachment.get('title', '')}]"
    
    # Handle files
    if 'file' in msg and msg['file']:
        file_info = msg['file']
        if content:
            content += "\n"
        content += f"[File: {file_info.get('name', '')}]"
    elif 'files' in msg and msg['files']:
        for file_info in msg['files']:
            if 'thumb-' not in file_info.get('name', ''):  # Skip thumbnails
                if content:
                    content += "\n"
                content += f"[File: {file_info.get('name', '')}]"
    
    # Handle reactions
    if 'reactions' in msg and msg['reactions']:
        reactions_text = []
        for emoji, data in msg['reactions'].items():
            if 'usernames' in data:
                usernames = data['usernames']
                reactions_text.append(f"{emoji} ({', '.join(usernames)})")
        
        if reactions_text:
            if content:
                content += "\n"
            content += f"[Reactions: {' | '.join(reactions_text)}]"
    
    return content

# ---------- Main Script ----------
# Parse command line arguments
ap = argparse.ArgumentParser(description="Convert Rocket.Chat data to Slack import format")
ap.add_argument("--mongo", default="mongodb://localhost:27017",
                help="MongoDB connection URI (default: mongodb://localhost:27017)")
ap.add_argument("--db", default="rocketchat",
                help="Database name containing Rocket.Chat collections (default: rocketchat)")
ap.add_argument("--out", default="./slack_export_core",
                help="Output directory for Slack import JSON files (default: ./slack_export_core)")
ap.add_argument("--csv", default="./messages_export.csv",
                help="Output CSV file for messages (default: ./messages_export.csv)")
ap.add_argument("--json-dir", default=None,
                help="Output directory for JSON message files (optional)")
args = ap.parse_args()

# Initialize output directories and database connection
out_dir = Path(args.out).expanduser()
out_dir.mkdir(parents=True, exist_ok=True)

client = MongoClient(args.mongo)
db = client[args.db]

# Display diagnostic information about the database
print(f"Connected to database: {args.mongo}/{args.db}")
print(f"Available collections: {', '.join(db.list_collection_names())}")
print(f"Total users: {db.users.count_documents({})}")
print(f"Total rooms: {db.rocketchat_room.count_documents({})}")
print(f"Total messages: {db.rocketchat_message.count_documents({})}")

# Export Phase 1: Users to Slack format
print("\\nPhase 1: Exporting users to Slack format...")
slack_users = []
for idx, u in enumerate(tqdm(db.users.find().sort("username", ASCENDING)), 1):
    slack_users.append(make_user_entry(u, idx))
    stats["users"] += 1
    
# Create user ID mapping for message processing
(uid_map := {}).update({u["_id"]: slack_users[i]["id"]
                        for i, u in enumerate(db.users.find().sort("username", ASCENDING))})
(out_dir / "users.json").write_text(json.dumps(slack_users, indent=2))

# Export Phase 2: Rooms/Channels to Slack format
print("\\nPhase 2: Exporting rooms and channels...")
# Categorize rooms by type for Slack import
rooms_by_type = {
    "channels.json": [],  # Public channels
    "groups.json": [],    # Private groups  
    "dms.json": [],       # Direct messages
    "mpims.json": []      # Multi-party instant messages
}

# Process each room and categorize by type
for r in tqdm(db.rocketchat_room.find()):
    if r["t"] == "c":                     # public channel
        rooms_by_type["channels.json"].append(make_room_entry(r, False))
        stats["channels"]["public"] += 1
    elif r["t"] == "p":                   # private group
        rooms_by_type["groups.json"].append(make_room_entry(r, True))
        stats["channels"]["private"] += 1
    elif r["t"] == "d":                   # direct message
        rooms_by_type["dms.json"].append(make_room_entry(r, True))
        stats["channels"]["dm"] += 1
    elif r["t"] == "l":                   # group DM (livechat/mpim)
        rooms_by_type["mpims.json"].append(make_room_entry(r, True))
        stats["channels"]["group_dm"] += 1

# Write room data to separate JSON files
for filename, data in rooms_by_type.items():
    if data:
        (out_dir / filename).write_text(json.dumps(data, indent=2))

# Export Phase 3: Messages to CSV format
print("\\nPhase 3: Exporting messages to CSV format...")

# Create mapping tables for efficient message processing

# Map room IDs to channel names for message organization
room_map = {}
for r in db.rocketchat_room.find():
    # For rooms with names
    if 'name' in r:
        room_map[r['_id']] = slug(r['name'])
    # For direct messages without names
    elif 'usernames' in r:
        room_map[r['_id']] = slug("-".join(sorted(r['usernames'])))
    # Fallback to ID
    else:
        room_map[r['_id']] = f"dm-{r['_id']}"

# Create user mapping tables for message attribution
username_map = {}  # Maps user IDs to usernames
email_map = {}     # Maps user IDs to email addresses

for u in db.users.find():
    # Store username for message attribution
    username_map[u['_id']] = u['username']
    
    # Extract email using Rocket.Chat's email storage structure
    # Format: {emails: {0: {address: email}}} or list format
    if 'emails' in u and u['emails'] is not None:
        if isinstance(u['emails'], dict) and '0' in u['emails']:
            if 'address' in u['emails']['0']:
                email_map[u['_id']] = u['emails']['0']['address']
        # Also try the list format as a fallback
        elif isinstance(u['emails'], list) and len(u['emails']) > 0:
            if 'address' in u['emails'][0]:
                email_map[u['_id']] = u['emails'][0]['address']

# Configuration for CSV file organization
ROWS_PER_FILE = 2000  # Maximum rows per CSV file
csv_base_path = Path(args.csv)
csv_base_name = csv_base_path.stem
csv_extension = csv_base_path.suffix
csv_dir = csv_base_path.parent

# Process and sort all messages by timestamp for chronological export
print("Retrieving and sorting messages by timestamp...")
all_messages = list(db.rocketchat_message.find())
messages = sorted(all_messages, key=lambda x: x.get('ts') if 'ts' in x else datetime.datetime.min)

# Initialize CSV export variables
message_count = 0
csv_files_created = []
channel_files = {}  # Dictionary to manage open file handles by channel

print("Writing messages to channel-specific CSV files...")
for msg in tqdm(messages):
    if 'rid' not in msg or 'u' not in msg or 'ts' not in msg:
        continue  # Skip incomplete messages
        
    # Get timestamp as Unix timestamp
    timestamp = int(msg['ts'].timestamp())
    
    # Get channel name from room map
    channel = room_map.get(msg['rid'], f"unknown-{msg['rid']}")
    
    # Get username only
    user_id = msg['u'].get('_id')
    user_identifier = username_map.get(user_id, msg['u'].get('username', 'unknown-user'))
    
    # Process complete message content
    text = process_message_content(msg)
    
    # Prepare text for CSV - may return multiple parts
    text_parts = prepare_message_for_csv(text)
    
    # Check if we already have a file open for this channel
    if channel not in channel_files:
        # Create a new file for this channel
        channel_file_path = csv_dir / f"{csv_base_name}_{channel}{csv_extension}"
        channel_files[channel] = {
            'file': open(channel_file_path, 'w', newline='', encoding='utf-8'),
            'writer': None,
            'path': channel_file_path
        }
        channel_files[channel]['writer'] = csv.writer(channel_files[channel]['file'], quoting=csv.QUOTE_MINIMAL)
        channel_files[channel]['writer'].writerow(['timestamp', 'channel', 'username', 'text'])
        csv_files_created.append(channel_file_path)
    
    # Write all message parts to the channel's CSV file
    for part in text_parts:
        channel_files[channel]['writer'].writerow([timestamp, channel, user_identifier, part])
        message_count += 1
        stats["messages"]["mongodb"] += 1

# Close all open CSV files
for channel_info in channel_files.values():
    channel_info['file'].close()

print(f"Wrote {message_count} message rows across {len(csv_files_created)} CSV files:")
for f in csv_files_created:
    print(f"  - {f}")

# Export Phase 4: Messages to JSON format
print("\\nPhase 4: Exporting messages to JSON format...")

# Configuration for JSON export processing
CHUNK_SIZE = 1000  # Process messages in batches for memory efficiency

# Get total message count for progress tracking
total_messages = db.rocketchat_message.count_documents({})
processed_messages = 0

# Set up JSON output directory
json_out_dir = Path(args.json_dir).expanduser()
json_out_dir.mkdir(parents=True, exist_ok=True)

# Process messages in chunks to manage memory usage
for chunk_start in tqdm(range(0, total_messages, CHUNK_SIZE)):
    # Retrieve a batch of messages sorted by timestamp
    message_chunk = list(db.rocketchat_message.find().sort("ts", ASCENDING).skip(chunk_start).limit(CHUNK_SIZE))
    
    # Convert messages to JSON format
    json_lines = []
    for msg in message_chunk:
        if 'rid' not in msg or 'u' not in msg or 'ts' not in msg:
            continue  # Skip incomplete messages
        
        # Map room ID to channel name
        channel = room_map.get(msg['rid'], f"unknown-{msg['rid']}")
        
        # Get user identifier (prefer email, fallback to username)
        user_id = msg['u'].get('_id')
        user_identifier = email_map.get(user_id) if user_id in email_map else username_map.get(user_id, msg['u'].get('username', 'unknown-user'))
        
        # Process complete message content (text, attachments, reactions, etc.)
        text = process_message_content(msg)
        
        # Create JSON object for this message
        json_obj = {
            "timestamp": int(msg['ts'].timestamp()),
            "channel": channel,
            "username": user_identifier,
            "text": text
        }
        
        json_lines.append(json.dumps(json_obj))
    
    # Write this batch to a numbered JSON file
    json_chunk_file = json_out_dir / f"messages_{chunk_start // CHUNK_SIZE + 1}.json"
    with open(json_chunk_file, 'w', encoding='utf-8') as f:
        f.write("\\n".join(json_lines) + "\\n")
    
    processed_messages += len(message_chunk)

print(f"\\nExport completed successfully!")
print(f"Messages exported to JSON: {processed_messages}")
print(f"JSON files created: {len(list(json_out_dir.glob('messages_*.json')))}")

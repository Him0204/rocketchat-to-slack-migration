# Rocket.Chat to Slack Message Migration

![GitHub repo size](https://img.shields.io/github/repo-size/Him0204/rocketchat-to-slack-migration?style=flat-square)
![GitHub issues](https://img.shields.io/github/issues/Him0204/rocketchat-to-slack-migration?style=flat-square)
![GitHub stars](https://img.shields.io/github/stars/Him0204/rocketchat-to-slack-migration?style=social)
![GitHub forks](https://img.shields.io/github/forks/Him0204/rocketchat-to-slack-migration?style=social)
![License](https://img.shields.io/github/license/Him0204/rocketchat-to-slack-migration?style=flat-square)
![Last Commit](https://img.shields.io/github/last-commit/Him0204/rocketchat-to-slack-migration?style=flat-square)

![Migration Tool](https://img.shields.io/badge/Rocket.Chat%E2%86%92Slack-Migration-blueviolet?style=for-the-badge)

## Overview

This repository provides a step-by-step guide and scripts to help you migrate messages from Rocket.Chat to Slack. Since there is no official direct migration tool, this process relies on exporting a Rocket.Chat MongoDB database dump, restoring it locally, and running a conversion script to reformat data for Slack’s import tool.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Getting the Rocket.Chat Database Dump](#2-getting-the-rocketchat-database-dump)
3. [Extracting and Preparing the Dump](#3-extracting-and-preparing-the-dump)
4. [Setting Up MongoDB and Docker](#4-setting-up-mongodb-and-docker)
5. [Restoring the Database](#5-restoring-the-database)
6. [Exporting Messages](#6-exporting-messages)
7. [Converting to Slack Format](#7-converting-to-slack-format)
8. [Importing to Slack](#8-importing-to-slack)
9. [Limitations & Important Observations](#9-limitations--important-observations)
10. [Troubleshooting](#10-troubleshooting)
11. [FAQ](#11-faq)
12. [Contributing](#12-contributing)

---

## 1. Prerequisites

* Access to your Rocket.Chat database dump (see below)
* Admin access to your Slack workspace
* A system with Docker, Python (3.7+), and MongoDB installed
* Basic knowledge of command line tools

---

## 2. Getting the Rocket.Chat Database Dump

* **Self-hosted:** Use [`mongodump`](https://www.mongodb.com/docs/database-tools/mongodump/) to export your database.
* **Rocket.Chat Cloud:** Contact Rocket.Chat support and request a full MongoDB database dump. They may provide it in multiple parts (e.g., files.tar.gz.part1, files.tar.gz.part2, etc.).

---

## 3. Extracting and Preparing the Dump

After downloading all dump parts:

```bash
cat files.tar.gz.part{1..N} > files.tar.gz      # Combine all parts (adjust N as needed)
tar -xzvf files.tar.gz                          # Extract dump
mkdir dump
mv database dump/
mv files dump/
```

---

## 4. Setting Up MongoDB and Docker

Install MongoDB and Docker on your system. For Ubuntu:

```bash
wget -qO - https://pgp.mongodb.com/server-7.0.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg
echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update
sudo apt install -y mongodb-org
docker --version                                # Check if Docker is installed
sudo apt-get install -y docker.io               # Install Docker if not present
sudo systemctl start docker                     # Start Docker service
```

---

## 5. Restoring the Database

Run MongoDB in Docker and restore your dump:

```bash
sudo docker run -d --name mongodb -p 27017:27017 -v "$(pwd)/dump":/dump mongo:6
sudo docker exec -it mongodb mongorestore --db rocketchat /dump/database/<your-dump-folder>
docker exec -it mongodb mongosh --eval "db.getSiblingDB('rocketchat').getCollectionNames()"
```

* Replace `<your-dump-folder>` with the actual folder name inside `/dump/database/`.

If you see your collections (like `users`, `messages`, `rooms`), the restore was successful.

---

## 6. Exporting Messages

Clone this repo and run the provided script to export messages:

```bash
python scripts/map_rc_to_slack.py --mongo mongodb://localhost:27017 --db rocketchat --out ./examples/slack_new_export_core --csv ./examples/messages_export.csv --json-dir ./examples/slack_export_msgs
```

* This script extracts channels, groups, and direct messages from Rocket.Chat and saves them in CSV and JSON formats compatible with Slack import.
* Modify the script arguments as needed for your setup.

---

## 7. Converting to Slack Format

* The generated files (in `/examples/messages_export.csv` and `/examples/slack_export_msgs/`) are formatted for Slack.
* **Review** the output to make sure:

  * Channel names match your expectations
  * Usernames and timestamps look correct
  * DMs and private groups are exported as expected

---

## 8. Importing to Slack

1. Go to your Slack workspace admin settings → Import/Export Data (Doc: [Slack Import Guide](https://slack.com/help/articles/204897248-Import-data-from-other-workspaces))
2. Select "CSV/text file" as the source.
3. Upload the converted export files (CSV as generated).
4. Follow Slack's steps to map users, channels, etc.
5. Start the import and monitor for errors.

---

## 9. Limitations & Important Observations

* **Slack CSV Import Only Supports Channels:**
  The Slack import tool using CSV format can only import messages as public channels. This means that all Rocket.Chat channels, group chats, and DMs will be imported as channels in Slack (not as private groups or direct messages).

* **Matching Existing Channels:**
  If you want to import messages into an existing channel, that channel **must be public** during the import process.

  * If a channel is private or does not exist in Slack, the import will create a **new channel**.
  * If you want your original private channels preserved, you can make them public during the import and switch them back to private afterward.

---

## 10. Troubleshooting

* If you get errors about unsupported file format, double-check the CSV structure against [Slack's Import Documentation](https://slack.com/help/articles/201748703-Import-and-export-data).
* If some messages are missing:

  * Verify all parts of the Rocket.Chat dump were combined and restored
  * Ensure the script processed all collections
* For permission issues, try running Docker and scripts with `sudo`.

For more, see [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

---

## 11. FAQ

### How do I get a Rocket.Chat dump if I’m on cloud?

Contact Rocket.Chat support and request a database dump. Specify that you want the MongoDB dump for migration purposes.

### What if my dump comes in multiple parts?

Use the `cat files.tar.gz.part{1..N} > files.tar.gz` command (replace N with the total number of parts).

### Why do I need Docker and MongoDB?

You need to restore the Rocket.Chat dump into a local MongoDB instance to extract and convert the data.

### Can I migrate files or just messages?

Slack's CSV import currently supports only text messages. Files and attachments cannot be imported using this method.

---

## 12. Contributing

Pull requests and issue reports are welcome! If you improve the script or find a better way to format for Slack, please contribute.

---

## Repository Structure

```
rocketchat-to-slack-migration/
├── README.md                  # Main instructions (this file)
├── scripts/
│   └── map_rc_to_slack.py     # Main conversion script
├── docs/
│   ├── TROUBLESHOOTING.md     # Troubleshooting guide
│   └── FAQ.md                 # Frequently asked questions
└── LICENSE
```

---

## Credits

* [Rocket.Chat Documentation](https://docs.rocket.chat/)
* [Slack Import & Export Help](https://slack.com/help/articles/204897248-Import-data-from-other-workspaces)

---

## Upcoming Updates

**Next Release Features:**

- **Import Format Checker & Fixer**: A new script will be included to automatically check and fix CSV format issues when imports fail, ensuring data compatibility and reducing manual intervention.

- **CSV Combiner Script**: A utility script to merge multiple CSV files into a single file for more efficient bulk imports, improving performance and simplifying data management workflows.

These enhancements will streamline the data import process and provide better error handling for CSV operations.

---

<br>

**Good luck with your migration! If you have suggestions, open an issue or PR.**

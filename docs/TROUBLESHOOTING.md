# Troubleshooting

This document lists common issues you may encounter when migrating Rocket.Chat data to Slack and ways to resolve them.

---

## Import Fails with "Unsupported File Format"

- **Cause:** Slack expects a specific CSV structure for imports.
- **Fix:** Double-check the format of your exported files. Review Slack’s [import documentation](https://slack.com/help/articles/201748703-Import-and-export-data) and make sure all required fields are present.

---

## Some Messages Are Missing After Import

- **Cause:** Not all dump parts were combined, or the export script did not process every collection.
- **Fix:** 
  - Make sure you concatenated all `.tar.gz.part*` files before extracting.
  - Confirm that the Rocket.Chat dump restore was successful and contains all collections.
  - Rerun the export script and check for errors.

---

## Channels Are Missing or Duplicated

- **Cause:** The import tool only matches **public** channels. Private channels or unmatched names create new public channels.
- **Fix:**
  - Make sure any existing Slack channels are made public during import.
  - Rename channels in your export to match the exact channel name in Slack if you want to merge histories.

---

## Permission Errors with Docker or MongoDB

- **Cause:** Your user account may not have the necessary permissions.
- **Fix:** 
  - Use `sudo` when running Docker and MongoDB commands.
  - Ensure your user is in the `docker` group.

---

## Export Script Fails to Connect to MongoDB

- **Cause:** The MongoDB container may not be running or accessible.
- **Fix:**
  - Check Docker status: `sudo docker ps`
  - Make sure the port `27017` is open and not blocked.
  - Check logs with `sudo docker logs mongodb`.

---

## Need More Help?

- Search open and closed issues in this repo.
- Open a new issue with logs and details of your setup.

---

# Frequently Asked Questions (FAQ)

---

## Can I migrate private groups or DMs from Rocket.Chat to Slack?

Slack’s import allows you to create new private channels from Rocket.Chat private groups or DMs. However, importing messages into an existing private channel is not supported—you must convert the channel to public before importing, and you can change it back to private after the import is complete.

---

## Can I migrate attachments or files?

Slack's CSV import currently supports only text messages. Files and attachments cannot be imported using this method.

---

## Do I have to make channels public during import?

Yes. To import messages into an existing channel, it must be public during the import. You can make it private again after the import is finished.

---

## What should I do if my Rocket.Chat dump is split into several files?

Use this command to concatenate them before extraction:

```bash
cat files.tar.gz.part{1..N} > files.tar.gz
tar -xzvf files.tar.gz
```

Replace `N` with the highest numbered part.

---

## Can I run the export script on Windows?

The script is designed for Linux environments. Running on Windows may require WSL (Windows Subsystem for Linux) or adapting file paths.

---

## Who can I contact for support?

* Open an issue in this repository.
* Check the [Rocket.Chat documentation](https://docs.rocket.chat/) and [Slack import help](https://slack.com/help/articles/204897248-Import-data-from-other-workspaces).

---

## What if I need to migrate a large workspace?

You may need to break the migration into batches or increase your system’s resources (memory, disk space). Monitor the process for timeouts or crashes.

---

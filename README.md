# RIDNESS Telegram Bot

This repository contains a Telegram bot built with **aiogram**.
The bot lets members of the RIDNESS Club browse a catalog, place preorders,
and get contact information. Most commands are available only to club members.

## Running the bot

1. Create a `.env` file with `TG_TOKEN`, `ADMIN_ID` and `GROUP_ID` variables.
2. Install the requirements:
   ```bash
   pip install aiogram python-dotenv
   ```
3. Run the bot:
   ```bash
   python bot.py
   ```

Club members are stored in `club_members.json` and preorders are sent to the
admin and group chat specified in `.env`.

import logging
import os
from difflib import get_close_matches

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from geocoder import geocode_destination
from report_assembler import assemble_report, run_all_fetchers
from route_buffer import build_route_corridor
from session import (
    clear_session,
    load_session,
    refresh_session,
    save_session,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "This bot provides best-effort information from public sources. "
    "It is <b>not</b> a substitute for checking official sources, telling someone your trip plan, "
    "carrying communication and navigation, or knowing the area. "
    "Conditions change fast in the BC backcountry. Always verify before you go."
)

_WELCOME = (
    "🌲 <b>BC Backcountry Scout</b>\n\n"
    "I pull road conditions, weather, wildfires, and wildlife advisories "
    "for your BC backcountry destination — in one message.\n\n"
    "<b>Commands</b>\n"
    "/scout &lt;destination&gt; — Full pre-trip report\n"
    "/from &lt;location&gt; — Set your starting point\n"
    "/whereami — Show current session\n"
    "/clear — Reset session\n"
    "/help — Show this list\n\n"
    "⚠️ <b>Safety notice</b>\n"
    + _DISCLAIMER
)

_HELP = (
    "<b>BC Backcountry Scout — Commands</b>\n\n"
    "/scout &lt;destination&gt; — Full pre-trip report\n"
    "/from &lt;location&gt; — Set your starting point\n"
    "/whereami — Show current session state\n"
    "/clear — Reset session\n"
    "/help — Show this list"
)

_KNOWN_COMMANDS = ["/scout", "/from", "/whereami", "/clear", "/help", "/start"]


class BotHandler:
    def __init__(self, token: str):
        self.app = ApplicationBuilder().token(token).build()
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("scout", self._cmd_scout))
        self.app.add_handler(CommandHandler("from", self._cmd_from))
        self.app.add_handler(CommandHandler("whereami", self._cmd_whereami))
        self.app.add_handler(CommandHandler("clear", self._cmd_clear))
        # Catch unknown /commands and suggest the closest match
        self.app.add_handler(MessageHandler(filters.COMMAND, self._cmd_unknown))

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(_WELCOME, parse_mode="HTML")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(_HELP, parse_mode="HTML")

    async def _cmd_scout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        query = " ".join(context.args).strip() if context.args else ""
        if not query:
            await update.message.reply_text("Usage: /scout <destination>")
            return

        await update.message.reply_text("Searching…")

        matches = geocode_destination(query)
        if not matches:
            await update.message.reply_text("Couldn't find that in BC. Try adding a region (e.g. 'Alice Lake Squamish') or check spelling.")
            return

        destination = matches[0]
        dest_point = (destination.lat, destination.lon)

        session = load_session(user_id) or {}
        start = session.get("starting_point")
        if start:
            start_point = (start["lat"], start["lon"])
            start_name = start["name"]
        else:
            start_point = (49.7016, -123.1558)
            start_name = "Squamish, BC"

        corridor = build_route_corridor(start_point, dest_point)

        await update.message.reply_text("Fetching conditions…")

        data = await run_all_fetchers(corridor, start_point, dest_point, destination.name)

        report = assemble_report(
            destination_name=destination.name,
            start_name=start_name,
            road_events=data["road_events"],
            weather=data["weather"],
            fires=data["fires"],
            advisories=data["advisories"],
        )

        save_session(user_id, {
            **session,
            "last_destination": {"name": destination.name, "lat": destination.lat, "lon": destination.lon},
        })
        refresh_session(user_id)

        await update.message.reply_text(report, parse_mode="MarkdownV2")

    async def _cmd_from(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        query = " ".join(context.args).strip() if context.args else ""
        if not query:
            await update.message.reply_text("Usage: /from <location>")
            return

        matches = geocode_destination(query)
        if not matches:
            await update.message.reply_text("Couldn't find that location in BC.")
            return

        loc = matches[0]
        session = load_session(user_id) or {}
        save_session(user_id, {
            **session,
            "starting_point": {"name": loc.name, "lat": loc.lat, "lon": loc.lon, "source": "manual"},
        })
        await update.message.reply_text(f"Starting point set to: {loc.name}")

    async def _cmd_whereami(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        session = load_session(user_id)
        if not session:
            await update.message.reply_text("No active session. Use /from to set a starting point.")
            return
        start = session.get("starting_point")
        dest = session.get("last_destination")
        lines = []
        if start:
            lines.append(f"Start: {start['name']}")
        if dest:
            lines.append(f"Last destination: {dest['name']}")
        if not lines:
            lines.append("Session active but no locations set yet.")
        await update.message.reply_text("\n".join(lines))

    async def _cmd_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        clear_session(update.effective_user.id)
        await update.message.reply_text("Session cleared.")

    async def _cmd_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text or ""
        typed_cmd = text.split()[0].lower()  # e.g. "/scount"
        # Strip bot username suffix if present (e.g. /scout@BotName)
        typed_cmd = typed_cmd.split("@")[0]
        matches = get_close_matches(typed_cmd, _KNOWN_COMMANDS, n=1, cutoff=0.6)
        if matches:
            suggestion = matches[0]
            rest = text[len(typed_cmd):].strip()
            example = f"{suggestion} {rest}".strip() if rest else suggestion
            await update.message.reply_text(
                f"Unknown command <b>{typed_cmd}</b>.\n"
                f"Did you mean <b>{suggestion}</b>?\n\n"
                f"Try: <code>{example}</code>\n\n"
                "Use /help to see all commands.",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                f"Unknown command <b>{typed_cmd}</b>. Use /help to see all commands.",
                parse_mode="HTML",
            )

    def run(self):
        logger.info("Starting BC Backcountry Scout (long-poll)")
        self.app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")
    BotHandler(token).run()

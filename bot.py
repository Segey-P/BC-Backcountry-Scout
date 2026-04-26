import html
import logging
import os
from datetime import date
from difflib import get_close_matches

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from geocoder import geocode_destination
from report_assembler import assemble_report, run_all_fetchers
from route_buffer import build_route_corridor
from session import clear_session, load_session, refresh_session, save_session

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


def _build_confirmation_text(pending: dict) -> str:
    today = date.today().strftime("%b %d, %Y")
    return (
        f"🗺️ <b>Trip confirmation</b>\n\n"
        f"📍 <b>Start:</b> {html.escape(pending['start_name'])}\n"
        f"🏁 <b>Destination:</b> {html.escape(pending['dest_name'])}\n"
        f"📅 <b>Date:</b> Today ({today})\n\n"
        "Tap <b>Scout it</b> to fetch conditions, or change your starting point."
    )


def _build_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Scout it", callback_data="scout_confirm"),
        InlineKeyboardButton("📍 Change start", callback_data="scout_change_start"),
    ]])


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
        self.app.add_handler(CallbackQueryHandler(self._on_confirm_button, pattern="^scout_"))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text_message))
        # Catch unknown /commands last so specific handlers take priority
        self.app.add_handler(MessageHandler(filters.COMMAND, self._cmd_unknown))

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(_WELCOME, parse_mode="HTML")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(_HELP, parse_mode="HTML")

    async def _cmd_scout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        query = " ".join(context.args).strip() if context.args else ""
        if not query:
            await update.message.reply_text("Usage: /scout &lt;destination&gt;", parse_mode="HTML")
            return

        status_msg = await update.message.reply_text("Searching…")

        matches = geocode_destination(query)
        if not matches:
            await status_msg.edit_text(
                "Couldn't find that in BC. Try adding a region (e.g. 'Alice Lake Squamish') or check spelling."
            )
            return

        destination = matches[0]
        session = load_session(user_id) or {}
        start = session.get("starting_point")

        pending = {
            "dest_name": destination.name,
            "dest_lat": destination.lat,
            "dest_lon": destination.lon,
            "start_name": start["name"] if start else "Squamish, BC",
            "start_lat": start["lat"] if start else 49.7016,
            "start_lon": start["lon"] if start else -123.1558,
            "confirmation_message_id": status_msg.message_id,
        }

        await status_msg.edit_text(
            _build_confirmation_text(pending),
            reply_markup=_build_confirmation_keyboard(),
            parse_mode="HTML",
        )

        session["pending_trip"] = pending
        session.pop("waiting_for", None)
        save_session(user_id, session)

    async def _on_confirm_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        await query.answer()

        session = load_session(user_id) or {}
        pending = session.get("pending_trip")

        if query.data == "scout_confirm":
            if not pending:
                await query.edit_message_text("Session expired. Please run /scout again.")
                return

            await query.edit_message_text(
                "Fetching conditions…",
                reply_markup=InlineKeyboardMarkup([]),
            )

            dest_point = (pending["dest_lat"], pending["dest_lon"])
            start_point = (pending["start_lat"], pending["start_lon"])
            corridor = build_route_corridor(start_point, dest_point)
            data = await run_all_fetchers(corridor, start_point, dest_point, pending["dest_name"])

            report = assemble_report(
                destination_name=pending["dest_name"],
                start_name=pending["start_name"],
                road_events=data["road_events"],
                weather=data["weather"],
                fires=data["fires"],
                advisories=data["advisories"],
            )
            await query.edit_message_text(report, parse_mode="HTML")

            session["last_destination"] = {
                "name": pending["dest_name"],
                "lat": pending["dest_lat"],
                "lon": pending["dest_lon"],
            }
            session.pop("pending_trip", None)
            save_session(user_id, session)
            refresh_session(user_id)

        elif query.data == "scout_change_start":
            await query.edit_message_text(
                "📍 <b>What's your starting point?</b>\n\nType and send your city or location in BC.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([]),
            )
            session["waiting_for"] = "start_update"
            save_session(user_id, session)

    async def _on_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        session = load_session(user_id) or {}

        if session.get("waiting_for") != "start_update":
            return

        text = update.message.text.strip()
        matches = geocode_destination(text)

        if not matches:
            await update.message.reply_text(
                f"Couldn't find <b>{html.escape(text)}</b> in BC. Try again:",
                parse_mode="HTML",
            )
            return

        loc = matches[0]
        pending = session.get("pending_trip", {})
        pending["start_name"] = loc.name
        pending["start_lat"] = loc.lat
        pending["start_lon"] = loc.lon
        session["pending_trip"] = pending
        session.pop("waiting_for", None)
        save_session(user_id, session)

        conf_text = _build_confirmation_text(pending)
        keyboard = _build_confirmation_keyboard()
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=pending["confirmation_message_id"],
                text=conf_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        except Exception:
            # Original confirmation message gone — send a fresh one
            conf_msg = await update.message.reply_text(conf_text, reply_markup=keyboard, parse_mode="HTML")
            pending["confirmation_message_id"] = conf_msg.message_id
            session["pending_trip"] = pending
            save_session(user_id, session)

    async def _cmd_from(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        query = " ".join(context.args).strip() if context.args else ""
        if not query:
            await update.message.reply_text("Usage: /from &lt;location&gt;", parse_mode="HTML")
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
        await update.message.reply_text(f"Starting point set to: {html.escape(loc.name)}", parse_mode="HTML")

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
            lines.append(f"Start: {html.escape(start['name'])}")
        if dest:
            lines.append(f"Last destination: {html.escape(dest['name'])}")
        if not lines:
            lines.append("Session active but no locations set yet.")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    async def _cmd_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        clear_session(update.effective_user.id)
        await update.message.reply_text("Session cleared.")

    async def _cmd_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text or ""
        typed_cmd = text.split()[0].lower()
        typed_cmd = typed_cmd.split("@")[0]  # strip bot username suffix
        matches = get_close_matches(typed_cmd, _KNOWN_COMMANDS, n=1, cutoff=0.6)
        if matches:
            suggestion = matches[0]
            rest = text[len(typed_cmd):].strip()
            example = f"{suggestion} {rest}".strip() if rest else suggestion
            await update.message.reply_text(
                f"Unknown command <b>{html.escape(typed_cmd)}</b>.\n"
                f"Did you mean <b>{suggestion}</b>?\n\n"
                f"Try: <code>{html.escape(example)}</code>\n\n"
                "Use /help to see all commands.",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                f"Unknown command <b>{html.escape(typed_cmd)}</b>. Use /help to see all commands.",
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

import asyncio
import html
import logging
import os
from datetime import date, datetime, timezone
from difflib import get_close_matches

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from fetchers.avalanche import fetch_avalanche
from fetchers.weather import fetch_weather_3day
from geocoder import geocode_destination
from report_assembler import (
    assemble_3day_report,
    assemble_avalanche_report,
    assemble_report,
    run_all_fetchers,
)
from route_buffer import build_route_corridor
from intent_router import Intent, nlp_enabled, parse_intent
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
    "/scout — Full pre-trip report\n"
    "/from &lt;location&gt; — Set your starting point\n"
    "/watch — Subscribe to condition alerts for current destination\n"
    "/unwatch — Stop condition alerts\n"
    "/clear — Reset session\n"
    "/help — Show this list\n\n"
    "💡 <b>Tip:</b> Share your GPS location to set your starting point automatically.\n\n"
    "⚠️ <b>Safety notice</b>\n"
    + _DISCLAIMER
)

_HELP = (
    "<b>BC Backcountry Scout — Commands</b>\n\n"
    "/scout — Full pre-trip report\n"
    "/from &lt;location&gt; — Set your starting point\n"
    "/watch — Subscribe to condition alerts\n"
    "/unwatch — Stop condition alerts\n"
    "/clear — Reset session\n"
    "/help — Show this list\n\n"
    "💡 Share your GPS location to update your starting point."
)

_KNOWN_COMMANDS = ["/scout", "/from", "/watch", "/unwatch", "/clear", "/help", "/start"]

_BOT_COMMANDS = [
    BotCommand("scout", "Full pre-trip report for a BC destination"),
    BotCommand("from", "Set your starting point"),
    BotCommand("watch", "Subscribe to condition alerts for current destination"),
    BotCommand("unwatch", "Stop condition alerts"),
    BotCommand("clear", "Reset session"),
    BotCommand("help", "Show all commands"),
]

_SQUAMISH_DEFAULT = (49.7016, -123.1558)


def _build_confirmation_text(pending: dict) -> str:
    from datetime import timedelta
    trip_date = pending.get("trip_date")
    today = date.today()
    if trip_date == "tomorrow":
        label_date = (today + timedelta(days=1)).strftime("%b %d, %Y")
        date_label = f"Tomorrow ({label_date})"
    elif trip_date and trip_date not in ("today", None):
        try:
            d = date.fromisoformat(trip_date)
            date_label = d.strftime("%b %d, %Y")
        except ValueError:
            date_label = f"Today ({today.strftime('%b %d, %Y')})"
    else:
        date_label = f"Today ({today.strftime('%b %d, %Y')})"
    return (
        f"🗺️ <b>Trip confirmation</b>\n\n"
        f"📍 <b>Start:</b> {html.escape(pending['start_name'])}\n"
        f"🏁 <b>Destination:</b> {html.escape(pending['dest_name'])}\n"
        f"📅 <b>Date:</b> {date_label}\n\n"
        "Tap <b>Scout it</b> to fetch conditions, or change your starting point."
    )


def _build_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Scout it", callback_data="scout_confirm"),
        InlineKeyboardButton("📍 Change start", callback_data="scout_change_start"),
    ]])


def _build_post_report_keyboard(is_alpine: bool) -> InlineKeyboardMarkup:
    row1 = [InlineKeyboardButton("📅 3-day forecast", callback_data="ext_3day")]
    if is_alpine:
        row1.append(InlineKeyboardButton("🏔️ Avalanche", callback_data="ext_avalanche"))
    row2 = [InlineKeyboardButton("🔄 Scout new destination", callback_data="ext_new")]
    return InlineKeyboardMarkup([row1, row2])


class BotHandler:
    def __init__(self, token: str):
        self.app = (
            ApplicationBuilder()
            .token(token)
            .post_init(self._post_init)
            .build()
        )
        self._register_handlers()

    async def _post_init(self, app):
        await app.bot.set_my_commands(_BOT_COMMANDS)
        if app.job_queue:
            app.job_queue.run_repeating(self._check_alerts_job, interval=1800, first=120)
            logger.info("Proactive alert job registered (30-min interval)")

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("scout", self._cmd_scout))
        self.app.add_handler(CommandHandler("from", self._cmd_from))
        self.app.add_handler(CommandHandler("watch", self._cmd_watch))
        self.app.add_handler(CommandHandler("unwatch", self._cmd_unwatch))
        self.app.add_handler(CommandHandler("clear", self._cmd_clear))
        self.app.add_handler(CallbackQueryHandler(self._on_confirm_button, pattern="^scout_"))
        self.app.add_handler(CallbackQueryHandler(self._on_post_report_button, pattern="^ext_"))
        self.app.add_handler(CallbackQueryHandler(self._on_quick_button, pattern="^quick_"))
        self.app.add_handler(MessageHandler(filters.LOCATION, self._on_location_message))
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
            session = load_session(user_id) or {}
            session["waiting_for"] = "scout_destination"
            save_session(user_id, session)
            last_dest = session.get("last_destination")
            if last_dest:
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        f"🔁 {last_dest['name']}", callback_data="quick_rescout"
                    )
                ]])
                await update.message.reply_text(
                    "🔍 <b>Where would you like to go?</b>\n\n"
                    "Type a BC destination, or tap below to re-scout your last trip:",
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            else:
                await update.message.reply_text(
                    "🔍 <b>Where would you like to go?</b>\n\nType a BC destination:",
                    parse_mode="HTML",
                )
            return
        await self._run_scout_flow(update.message, query, user_id)

    async def _run_scout_flow(self, message, query_text: str, user_id: int, trip_date: str | None = None):
        """Geocode a destination and send the trip confirmation card."""
        status_msg = await message.reply_text("Searching…")

        matches = geocode_destination(query_text)
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
            "trip_date": trip_date,
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

            is_alpine = data["weather"].is_alpine if data["weather"] else False

            report = assemble_report(
                destination_name=pending["dest_name"],
                start_name=pending["start_name"],
                road_events=data["road_events"],
                weather=data["weather"],
                fires=data["fires"],
                advisories=data["advisories"],
                eta=data.get("eta"),
                avalanche=data.get("avalanche"),
            )
            await query.edit_message_text(
                report,
                parse_mode="HTML",
                reply_markup=_build_post_report_keyboard(is_alpine),
            )

            session["last_destination"] = {
                "name": pending["dest_name"],
                "lat": pending["dest_lat"],
                "lon": pending["dest_lon"],
                "is_alpine": is_alpine,
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

    async def _on_post_report_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        await query.answer()

        session = load_session(user_id) or {}
        last_dest = session.get("last_destination")

        if query.data == "ext_new":
            await query.message.reply_text(
                "🔍 <b>Scout where?</b>\n\nType your BC destination:",
                parse_mode="HTML",
            )
            session["waiting_for"] = "scout_destination"
            save_session(user_id, session)
            return

        if not last_dest:
            await query.message.reply_text("Session expired. Use /scout to start a new search.")
            return

        lat, lon = last_dest["lat"], last_dest["lon"]
        name = last_dest["name"]

        if query.data == "ext_3day":
            status = await query.message.reply_text("Fetching 3-day forecast…")
            try:
                forecasts = await asyncio.wait_for(
                    asyncio.to_thread(fetch_weather_3day, lat, lon), timeout=8
                )
            except (asyncio.TimeoutError, Exception):
                forecasts = []
            report = assemble_3day_report(name, forecasts)
            await status.edit_text(report, parse_mode="HTML")

        elif query.data == "ext_avalanche":
            status = await query.message.reply_text("Fetching avalanche forecast…")
            try:
                avx = await asyncio.wait_for(
                    asyncio.to_thread(fetch_avalanche, lat, lon), timeout=8
                )
            except (asyncio.TimeoutError, Exception):
                avx = None
            report = assemble_avalanche_report(name, avx)
            await status.edit_text(report, parse_mode="HTML", disable_web_page_preview=True)

    async def _on_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        session = load_session(user_id) or {}
        waiting = session.get("waiting_for")

        if waiting == "start_update":
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
                conf_msg = await update.message.reply_text(conf_text, reply_markup=keyboard, parse_mode="HTML")
                pending["confirmation_message_id"] = conf_msg.message_id
                session["pending_trip"] = pending
                save_session(user_id, session)

        elif waiting == "scout_destination":
            text = update.message.text.strip()
            session.pop("waiting_for", None)
            save_session(user_id, session)
            await self._run_scout_flow(update.message, text, user_id)

        elif nlp_enabled():
            text = update.message.text.strip()
            thinking = await update.message.reply_text("⏳")
            try:
                intent = await asyncio.wait_for(
                    asyncio.to_thread(parse_intent, text),
                    timeout=20.0,
                )
            except asyncio.TimeoutError:
                logger.warning("intent_router: Gemini timed out for %r", text)
                intent = Intent(skill="unknown", reason="timeout")
            await thinking.delete()
            await self._dispatch_intent(intent, update, context)

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

    async def _cmd_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        clear_session(update.effective_user.id)
        await update.message.reply_text("Session cleared.")

    async def _cmd_watch(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        session = load_session(user_id) or {}
        last_dest = session.get("last_destination")
        if not last_dest:
            await update.message.reply_text(
                "No active destination. Use /scout first, then /watch to subscribe to alerts.",
                parse_mode="HTML",
            )
            return
        start = session.get("starting_point")
        session["watch"] = {
            "dest_name": last_dest["name"],
            "dest_lat": last_dest["lat"],
            "dest_lon": last_dest["lon"],
            "start_lat": start["lat"] if start else _SQUAMISH_DEFAULT[0],
            "start_lon": start["lon"] if start else _SQUAMISH_DEFAULT[1],
            "last_state": {},
            "last_check": None,
        }
        save_session(user_id, session)
        await update.message.reply_text(
            f"🔔 <b>Watching {html.escape(last_dest['name'])}</b>\n\n"
            "I'll notify you when road conditions, fires, or advisories change.\n\n"
            "Use /unwatch to stop.",
            parse_mode="HTML",
        )

    async def _cmd_unwatch(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        session = load_session(user_id) or {}
        if "watch" not in session:
            await update.message.reply_text("No active watch. Use /watch after a /scout to subscribe.")
            return
        dest_name = session["watch"].get("dest_name", "destination")
        session.pop("watch", None)
        save_session(user_id, session)
        await update.message.reply_text(f"🔕 Stopped watching {html.escape(dest_name)}.")

    async def _on_location_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        loc = update.message.location
        lat, lon = loc.latitude, loc.longitude
        session = load_session(user_id) or {}
        session["starting_point"] = {
            "name": f"Your location ({lat:.4f}, {lon:.4f})",
            "lat": lat,
            "lon": lon,
            "source": "gps",
        }
        session.pop("waiting_for", None)
        save_session(user_id, session)
        pending = session.get("pending_trip")
        if pending:
            pending["start_name"] = session["starting_point"]["name"]
            pending["start_lat"] = lat
            pending["start_lon"] = lon
            session["pending_trip"] = pending
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
                await update.message.reply_text(conf_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await update.message.reply_text(
                f"📍 Starting point set to your GPS location. Use /scout to search for a destination.",
                parse_mode="HTML",
            )

    async def _on_quick_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        await query.answer()
        if query.data == "quick_rescout":
            session = load_session(user_id) or {}
            last_dest = session.get("last_destination")
            if not last_dest:
                await query.edit_message_text("No recent destination. Please type a destination.")
                return
            session.pop("waiting_for", None)
            save_session(user_id, session)
            await query.edit_message_reply_markup(InlineKeyboardMarkup([]))
            await self._run_scout_flow(query.message, last_dest["name"], user_id)

    async def _check_alerts_job(self, context: ContextTypes.DEFAULT_TYPE):
        from session import SESSION_FILE
        from session import _read_all  # noqa: PLC0415 — private access needed to iterate all users
        all_sessions = _read_all(SESSION_FILE)
        for uid_str, session in all_sessions.items():
            watch = session.get("watch")
            if not watch:
                continue
            try:
                await self._process_watch(context, int(uid_str), watch)
            except Exception as exc:
                logger.warning("Alert check failed for user %s: %s", uid_str, exc)

    async def _process_watch(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, watch: dict):
        dest_point = (watch["dest_lat"], watch["dest_lon"])
        start_point = (watch["start_lat"], watch["start_lon"])
        corridor = build_route_corridor(start_point, dest_point)
        try:
            fetched = await asyncio.wait_for(
                run_all_fetchers(corridor, start_point, dest_point, watch["dest_name"]),
                timeout=30,
            )
        except Exception:
            return

        road_ids = {ev.headline for ev in fetched["road_events"]}
        fire_names = {f.name for f in fetched["fires"]}
        last = watch.get("last_state", {})
        new_roads = road_ids - set(last.get("road_event_ids", []))
        new_fires = fire_names - set(last.get("fire_names", []))

        if new_roads or new_fires:
            lines = [f"🔔 <b>Conditions changed: {html.escape(watch['dest_name'])}</b>\n"]
            for r in sorted(new_roads):
                lines.append(f"⚠️ New road event: {html.escape(r)}")
            for f in sorted(new_fires):
                lines.append(f"🔥 New fire nearby: {html.escape(f)}")
            lines.append("\nUse /scout to get the full report.")
            try:
                await context.bot.send_message(user_id, "\n".join(lines), parse_mode="HTML")
            except Exception as exc:
                logger.warning("Alert send failed for %s: %s", user_id, exc)

        fresh = load_session(user_id) or {}
        fresh_watch = fresh.get("watch", watch)
        fresh_watch["last_state"] = {
            "road_event_ids": list(road_ids),
            "fire_names": list(fire_names),
        }
        fresh_watch["last_check"] = datetime.now(timezone.utc).isoformat()
        fresh["watch"] = fresh_watch
        save_session(user_id, fresh)

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

    async def _dispatch_intent(self, intent: Intent, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if intent.skill == "scout":
            if not intent.destination:
                await update.message.reply_text(
                    "🔍 Where would you like to go?", parse_mode="HTML"
                )
                return
            if intent.start:
                matches = geocode_destination(intent.start)
                if matches:
                    loc = matches[0]
                    session = load_session(user_id) or {}
                    save_session(user_id, {
                        **session,
                        "starting_point": {"name": loc.name, "lat": loc.lat, "lon": loc.lon, "source": "nlp"},
                    })
            await self._run_scout_flow(update.message, intent.destination, user_id, trip_date=intent.trip_date)

        elif intent.skill == "set_start":
            if not intent.location:
                await update.message.reply_text("Where are you starting from?")
                return
            matches = geocode_destination(intent.location)
            if not matches:
                await update.message.reply_text("Couldn't find that location in BC.")
                return
            loc = matches[0]
            session = load_session(user_id) or {}
            save_session(user_id, {
                **session,
                "starting_point": {"name": loc.name, "lat": loc.lat, "lon": loc.lon, "source": "nlp"},
            })
            await update.message.reply_text(
                f"📍 Starting point set to: <b>{html.escape(loc.name)}</b>", parse_mode="HTML"
            )

        elif intent.skill == "help":
            await update.message.reply_text(_HELP, parse_mode="HTML")

        elif intent.skill == "clear":
            clear_session(user_id)
            await update.message.reply_text("Session cleared.")

        else:
            await update.message.reply_text(
                "I can help with BC backcountry conditions. "
                "Try: <i>conditions at Alice Lake</i> or use /scout.",
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

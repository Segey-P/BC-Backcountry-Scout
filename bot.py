import logging
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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


class BotHandler:
    def __init__(self, token: str):
        self.app = ApplicationBuilder().token(token).build()
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("scout", self._cmd_stub))
        self.app.add_handler(CommandHandler("from", self._cmd_stub))
        self.app.add_handler(CommandHandler("whereami", self._cmd_stub))
        self.app.add_handler(CommandHandler("clear", self._cmd_stub))

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(_WELCOME, parse_mode="HTML")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(_HELP, parse_mode="HTML")

    async def _cmd_stub(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Coming soon.")

    def run(self):
        logger.info("Starting BC Backcountry Scout (long-poll)")
        self.app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")
    BotHandler(token).run()

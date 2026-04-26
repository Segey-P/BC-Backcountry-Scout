# Open Questions for Phase 1 Refinement

These are decisions to finalize before implementation starts. None block the build, but answering them now prevents mid-build scope creep.

---

## 1. Phase 2 priorities

After MVP is stable (you + 2–3 friends using it for a few weeks), which feature matters most?

- **A. Proactive alerts** — Subscribe to a destination; get pinged when conditions change (new road closure, fire, bear sighting)
- **B. Avalanche integration** — Avalanche Canada API for terrain-specific snowmobile planning
- **C. Trail busy-ness estimate** — Heuristic based on permit/parking, Strava heatmap, or scraped trip reports

| Option | Effort (weeks) | Demand | Notes |
|---|---|---|---|
| A | 2–3 | High | Biggest user value for hunting/climbing trips; requires persistent storage |
| B | 1–2 | Medium | Snowmobile-specific; helps winter trips |
| C | 1–2 | Medium | Nice-to-have; data quality varies |

**User preference:** A / B / C / Defer decision until MVP is live?

---

## 2. Severe weather alerts — push without request?

Should the bot proactively send a severe weather / avalanche warning even if the user hasn't asked for a report?

- **No (MVP):** User asks for a report, bot includes current alerts. Phase 2 feature.
- **Yes (risky):** Bot pushes a message if Env Canada issues a warning in Squamish area. Risk: alert fatigue if thresholds are wrong.

**Recommendation:** No for MVP. Adds complexity and risk for a first build. Phase 2 can revisit.

**User decision:** Yes / No (recommended: No)?

---

## 3. Invite-only allowlist — storage & management

The bot checks `user_id` against an allowlist. How should it be managed?

- **A. Hardcoded list** — `ALLOWED_USERS = [123456, ...]` in code. Simple for small group. Need to redeploy to add friends.
- **B. JSON file** — `allowlist.json` in the repo. Easy to edit; could be updated without code restart via admin commands.
- **C. Admin command** — `/admin_add_user <user_id>` available only to you. Allows adding friends on-the-fly.

**Recommendation:** Start with B (JSON file), because it's simple and you can manage it via the repo. If friends keep requesting access, add C later.

**User preference:** A / B / C?

---

## 4. Data retention — how long to keep session.json?

Sessions expire after 24h of inactivity. But should very old sessions ever be purged from the file to keep it clean?

- **A. Never purge** — Accumulate all users ever, but only active sessions are used
- **B. Purge monthly** — Remove any session not active in the last 30 days
- **C. Purge on startup** — When the bot starts, delete any session older than 30 days

**Recommendation:** B (purge monthly) for a long-running bot. Keeps the file lean and privacy-friendly.

**User preference:** A / B / C?

---

## 5. News source scraping — which outlets to prioritize?

The spec lists Squamish Chief + WildSafeBC. Are there other local sources you want monitored?

Examples:
- **Sea-to-Sky Gondola alerts** (if hiking Whistler area)
- **Whistler Blackcomb alerts** (closures, avalanche)
- **Local hiking group Facebook/Discord** (scrape or manual?)
- **Squamish Fire Department** (any closure/fire alerts)

**User input:** Any sources beyond Squamish Chief + WildSafeBC?

---

## 6. Geocoding bias point — where to assume users are?

The spec says "distance-biased" results. What point should be the center of bias?

- **A. Squamish downtown** (49.7016, -123.1558) — closest to most Squamish outdoor trailheads
- **B. User's last starting point** — if available, bias towards familiar areas
- **C. User's live GPS** — if they've shared it, bias towards their current location

**Recommendation:** B (last starting point) if available, else A. Avoids disclosing home location bias.

**User preference:** A / B / C?

---

## 7. Report language & tone

The spec sample uses emojis + short phrasing. Any tone adjustments?

Examples:
- Keep it as-is (concise, emoji-friendly)
- More formal / professional tone (less emoji)
- More casual / conversational
- Adjust report length (< 1500 chars today, could be longer/shorter?)

**User preference:** As-is / More formal / More casual / Adjust length?

---

## 8. Multi-language support?

Should the bot respond in French as well as English, given BC's bilingual context?

- **No (MVP):** English only. Phase 2 if demand exists.
- **Yes:** Bot detects user language or offers a `/lang` command.

**Recommendation:** No for MVP. Adds translation work and maintenance burden.

**User decision:** Yes / No (recommended: No)?

---

## 9. Timeline expectations

Do you have a hard deadline for MVP being live (you + friends using it), or is "whenever it's ready" fine?

- Soft deadline (no rush)
- Need it by [specific date]

**User input:** Timeline?

---

## Summary

Once you answer 1–9, I'll:
1. Update `spec-scout-requirements.md` with your decisions
2. Create a `context-` file for build prompts (by module)
3. Update `TODO.md` with concrete first-module action
4. Ready to hand off to Claude Code for implementation

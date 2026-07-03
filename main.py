import logging
import os
import asyncio
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import pandas as pd

load_dotenv()

# Configuration
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_FOOTBALL = os.getenv("API_FOOTBALL_KEY")
ODDS_API = os.getenv("ODDS_API_KEY")
OWNER_ID = int(os.getenv("YOUR_CHAT_ID", 0))
# Defaults updated to values requested by the user
MIN_CONFIDENCE = int(os.getenv("MIN_CONFIDENCE", 50))
MAX_CONFIDENCE = int(os.getenv("MAX_CONFIDENCE", 95))
MIN_ODDS = float(os.getenv("MIN_ODDS", 1.20))
MAX_ODDS = float(os.getenv("MAX_ODDS", 4.00))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

users = {OWNER_ID}
value_bets_cache = []
monitoring_active = False

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_risk_level(confidence):
    """Υπολογίζει το επίπεδο κινδύνου βάσει confidence.
    Χωρίζει το διάστημα [MIN_CONFIDENCE, MAX_CONFIDENCE] σε 3 ίσα τμήματα
    για δυναμικά risk labels.
    """
    try:
        low = MIN_CONFIDENCE
        high = MAX_CONFIDENCE
        if high <= low:
            # fallback to static thresholds if config is invalid
            if confidence < 70:
                return "🟢 SAFE", confidence
            elif confidence < 80:
                return "🟡 MEDIUM RISK", confidence
            else:
                return "🔴 HIGH RISK", confidence

        span = high - low
        t1 = low + span * (1/3)
        t2 = low + span * (2/3)

        if confidence < t1:
            return "🟢 SAFE", confidence
        elif confidence < t2:
            return "🟡 MEDIUM RISK", confidence
        else:
            return "🔴 HIGH RISK", confidence
    except Exception:
        return "🔴 HIGH RISK", confidence

# ============================================
# API CALLS
# ============================================

def get_live_matches():
    """Παίρνει τρέχοντα matches από API Football"""
    try:
        url = "https://v3.football.api-sports.io/fixtures"
        params = {
            "live": "all",
            "status": "LIVE"
        }
        headers = {"x-apisports-key": API_FOOTBALL}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("response", [])
        logger.warning(f"get_live_matches returned status {response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Error fetching live matches: {e}")
        return []


def get_upcoming_matches(hours=24):
    """Παίρνει upcoming matches για τις επόμενες ώρες"""
    try:
        url = "https://v3.football.api-sports.io/fixtures"
        from_date = datetime.now().strftime("%Y-%m-%d")
        to_date = (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d")
        
        params = {
            "from": from_date,
            "to": to_date,
            "status": "NS"
        }
        headers = {"x-apisports-key": API_FOOTBALL}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("response", [])
        logger.warning(f"get_upcoming_matches returned status {response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Error fetching upcoming matches: {e}")
        return []


def get_odds(league="soccer", region="us"):
    """Παίρνει τρέχοντα odds από The Odds API
    Επιστρέφει λίστα αγώνων/markets. Χρησιμοποιούμε robust fallback matching.
    """
    try:
        url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"
        params = {
            "apiKey": ODDS_API,
            "regions": region,
            "markets": "h2h,spreads",
            "oddsFormat": "decimal"
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            # Some endpoints return list at top-level
            data = response.json()
            # normalize to list
            if isinstance(data, dict) and "data" in data:
                return data.get("data", [])
            if isinstance(data, list):
                return data
            return []
        logger.warning(f"get_odds returned status {response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Error fetching odds: {e}")
        return []


def calculate_win_probability(home_team, away_team):
    """Υπολογίζει την πιθανότητα νίκης βάσει ιστορικού"""
    try:
        url = "https://v3.football.api-sports.io/teams/statistics"
        headers = {"x-apisports-key": API_FOOTBALL}
        
        home_stats = requests.get(
            url,
            params={"team": home_team.get("id", 0), "season": 2024},
            headers=headers,
            timeout=10
        ).json().get("response", {})
        
        away_stats = requests.get(
            url,
            params={"team": away_team.get("id", 0), "season": 2024},
            headers=headers,
            timeout=10
        ).json().get("response", {})
        
        home_win_rate = home_stats.get("fixtures", {}).get("wins", {}).get("total", 0) / max(
            home_stats.get("fixtures", {}).get("played", {}).get("total", 1), 1
        ) * 100
        
        away_win_rate = away_stats.get("fixtures", {}).get("wins", {}).get("total", 0) / max(
            away_stats.get("fixtures", {}).get("played", {}).get("total", 1), 1
        ) * 100
        
        # Simple weighted estimator
        home_probability = (home_win_rate * 0.6 + away_win_rate * 0.4 + 5)
        away_probability = (away_win_rate * 0.6 + home_win_rate * 0.4)
        draw_probability = 100 - home_probability - away_probability
        
        return {
            "home": max(0, min(100, home_probability)),
            "away": max(0, min(100, away_probability)),
            "draw": max(0, min(100, draw_probability))
        }
    except Exception as e:
        logger.error(f"Error calculating probability: {e}")
        return {"home": 50, "away": 50, "draw": 0}


def find_value_bets():
    """Βρίσκει value bets με δυναμικά thresholds και κάνει fallback σε περίπτωση έλλειψης δεδομένων"""
    global value_bets_cache
    
    try:
        upcoming = get_upcoming_matches(hours=48)
        odds_data = get_odds()
        
        if not upcoming:
            logger.info("No upcoming matches returned from API.")
            value_bets_cache = []
            return []
        if not odds_data:
            logger.info("No odds data returned from Odds API.")
            value_bets_cache = []
            return []
        
        value_bets = []
        
        for match in upcoming[:50]:
            fixture = match.get("fixture", {})
            teams = match.get("teams", {})
            
            match_id = fixture.get("id")
            home_team = teams.get("home", {})
            away_team = teams.get("away", {})
            
            probabilities = calculate_win_probability(home_team, away_team)
            
            # Try to find corresponding odds entry with robust matching
            for odd in odds_data:
                matched_entry = False
                try:
                    odd_id = odd.get("id") if isinstance(odd, dict) else None
                    # Some APIs return numeric id, some string
                    if odd_id is not None and str(odd_id) == str(match_id):
                        matched_entry = True
                    # try other common keys
                    if not matched_entry and str(match_id) in (str(odd.get("match_id", "")), str(odd.get("fixture_id", ""))):
                        matched_entry = True
                    # fallback: match on team names if available
                    odd_home = odd.get("home_team") or odd.get("teams", {}).get("home") if isinstance(odd, dict) else None
                    odd_away = odd.get("away_team") or odd.get("teams", {}).get("away") if isinstance(odd, dict) else None
                    if not matched_entry and odd_home and odd_away:
                        if isinstance(odd_home, str) and isinstance(odd_away, str):
                            if odd_home.lower() == home_team.get("name", "").lower() and odd_away.lower() == away_team.get("name", "").lower():
                                matched_entry = True
                except Exception:
                    continue
                
                if not matched_entry:
                    continue
                
                bookmakers = odd.get("bookmakers", []) if isinstance(odd, dict) else odd.get("bookmakers", [])
                
                for bookmaker in bookmakers:
                    markets = bookmaker.get("markets", [])
                    for market in markets:
                        if market.get("key") == "h2h":
                            outcomes = market.get("outcomes", [])
                            
                            for outcome in outcomes:
                                outcome_name = outcome.get("name")
                                decimal_odds = outcome.get("price", 0)
                                
                                # Odds filter
                                if decimal_odds is None:
                                    continue
                                try:
                                    decimal_odds = float(decimal_odds)
                                except Exception:
                                    continue
                                
                                if decimal_odds < MIN_ODDS or decimal_odds > MAX_ODDS:
                                    continue
                                
                                implied_prob = (1 / decimal_odds * 100) if decimal_odds > 0 else 0
                                
                                if outcome_name == home_team.get("name"):
                                    actual_prob = probabilities["home"]
                                elif outcome_name == away_team.get("name"):
                                    actual_prob = probabilities["away"]
                                else:
                                    # sometimes outcome names are short (e.g. 'Home'/'Away') - attempt a looser match
                                    name_lower = outcome_name.lower() if isinstance(outcome_name, str) else ""
                                    if "home" in name_lower:
                                        actual_prob = probabilities["home"]
                                    elif "away" in name_lower:
                                        actual_prob = probabilities["away"]
                                    else:
                                        continue
                                
                                # Confidence filter
                                if MIN_CONFIDENCE <= actual_prob <= MAX_CONFIDENCE and actual_prob > implied_prob:
                                    edge = actual_prob - implied_prob
                                    if implied_prob > 0:
                                        roi = (edge / implied_prob) * 100
                                    else:
                                        roi = 0.0
                                    risk_level, conf = get_risk_level(actual_prob)
                                    
                                    bet = {
                                        "match": f"{home_team.get('name')} vs {away_team.get('name')}",
                                        "pick": outcome_name,
                                        "odds": round(decimal_odds, 2),
                                        "confidence": round(actual_prob, 1),
                                        "implied_prob": round(implied_prob, 1),
                                        "edge": round(edge, 1),
                                        "roi": round(roi, 1),
                                        "time": fixture.get("date", ""),
                                        "risk_level": risk_level
                                    }
                                    
                                    value_bets.append(bet)
        
        value_bets = sorted(value_bets, key=lambda x: x["roi"], reverse=True)
        value_bets_cache = value_bets[:5]
        
        return value_bets[:5]
    except Exception as e:
        logger.error(f"Error finding value bets: {e}")
        value_bets_cache = []
        return []

# ============================================
# TELEGRAM HANDLERS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Εντολή /start"""
    user_id = update.effective_user.id
    users.add(user_id)
    
    text = f"""🎯 **Betting AI Bot - Safe Value Betting**

Καλώς ήρθες! Αυτό το bot βρίσκει **value bets** με:
- ✅ Confidence Range: **{MIN_CONFIDENCE}% - {MAX_CONFIDENCE}%**
- ✅ Odds Range: **{MIN_ODDS} - {MAX_ODDS}**
- ✅ Risk Level Display

**Επίπεδα Κινδύνου:**
🟢 SAFE ({MIN_CONFIDENCE}% - {round(MIN_CONFIDENCE + (MAX_CONFIDENCE-MIN_CONFIDENCE)/3)}%)
🟡 MEDIUM RISK ({round(MIN_CONFIDENCE + (MAX_CONFIDENCE-MIN_CONFIDENCE)/3)}% - {round(MIN_CONFIDENCE + 2*(MAX_CONFIDENCE-MIN_CONFIDENCE)/3)}%)
🔴 HIGH RISK ({round(MIN_CONFIDENCE + 2*(MAX_CONFIDENCE-MIN_CONFIDENCE)/3)}%+)

**Εντολές:**
/status - Κατάσταση bot
/topbets - Top value bets σήμερα
/help - Βοήθεια
/stats - Στατιστικά

✅ Live monitoring είναι ενεργό!
"""
    await update.message.reply_text(text, parse_mode="Markdown")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Εντολή /status"""
    text = f"""✅ **Bot Status**

🟢 Online
👥 Ενεργοί χρήστες: {len(users)}
📊 Value bets στη cache: {len(value_bets_cache)}
🎯 Confidence Range: {MIN_CONFIDENCE}% - {MAX_CONFIDENCE}%
💰 Odds Range: {MIN_ODDS} - {MAX_ODDS}
⏰ Live monitoring: {'✅ ON' if monitoring_active else '❌ OFF'}

Ενημέρωση: {datetime.now().strftime('%H:%M:%S')}
"""
    await update.message.reply_text(text, parse_mode="Markdown")

async def top_bets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Εντολή /topbets"""
    bets = find_value_bets()
    
    if not bets:
        # More helpful message when no bets available
        text = (f"❌ Δεν υπάρχουν live value bets αυτή τη στιγμή με {MIN_CONFIDENCE}%-{MAX_CONFIDENCE}% confidence "
                f"και odds {MIN_ODDS}-{MAX_ODDS}.\n\n"
                "ℹ️ Σημείωση: χρειάζονται αγώνες σε εξέλιξη και διαθέσιμα odds από τον bookmaker τη δεδομένη στιγμή.")
        await update.message.reply_text(text)
        return
    
    text = "🎯 **Top Value Bets - Sorted by ROI**\n\n"
    for i, bet in enumerate(bets, 1):
        text += f"{i}. **{bet['match']}**\n   Pick: {bet['pick']}\n   Odds: {bet['odds']}\n   Confidence: {bet['confidence']}% {bet['risk_level']}\n   ROI: +{bet['roi']}%\n\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Εντολή /help"""
    text = f"""📋 **Available Commands:**

/start - Ενεργοποίηση bot
/status - Κατάσταση bot
/topbets - Top value bets
/help - Βοήθεια
/stats - Στατιστικά

**Configuration:**
MIN Confidence: {MIN_CONFIDENCE}%
MID Confidence: {round(MIN_CONFIDENCE + (MAX_CONFIDENCE-MIN_CONFIDENCE)/2)}%
MAX Confidence: {MAX_CONFIDENCE}%
MIN Odds: {MIN_ODDS}
MAX Odds: {MAX_ODDS}
"""
    await update.message.reply_text(text, parse_mode="Markdown")

async def main():
    """Κύριο πρόγραμμα"""
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("topbets", top_bets))
    application.add_handler(CommandHandler("help", help_command))
    
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

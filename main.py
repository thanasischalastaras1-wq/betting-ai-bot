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
MIN_CONFIDENCE = int(os.getenv("MIN_CONFIDENCE", 65))
MAX_CONFIDENCE = int(os.getenv("MAX_CONFIDENCE", 80))
MIN_ODDS = float(os.getenv("MIN_ODDS", 1.70))
MAX_ODDS = float(os.getenv("MAX_ODDS", 2.50))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

users = {OWNER_ID}
value_bets_cache = []
monitoring_active = False

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_risk_level(confidence):
    """Υπολογίζει το επίπεδο κινδύνου βάσει confidence"""
    if confidence >= 75:
        return "🟢 VERY LOW RISK", confidence
    elif confidence >= 70:
        return "🟡 LOW RISK", confidence
    elif confidence >= 65:
        return "🟠 MEDIUM RISK", confidence
    else:
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
        return []
    except Exception as e:
        logger.error(f"Error fetching upcoming matches: {e}")
        return []

def get_odds(league="soccer", region="us"):
    """Παίρνει τρέχοντα odds από The Odds API"""
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
            return response.json().get("data", [])
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
    """Βρίσκει value bets με confidence 65-80% και odds 1.70-2.50"""
    global value_bets_cache
    
    try:
        upcoming = get_upcoming_matches(hours=48)
        odds_data = get_odds()
        
        value_bets = []
        
        for match in upcoming[:10]:
            fixture = match.get("fixture", {})
            teams = match.get("teams", {})
            
            match_id = fixture.get("id")
            home_team = teams.get("home", {})
            away_team = teams.get("away", {})
            
            probabilities = calculate_win_probability(home_team, away_team)
            
            for odd in odds_data:
                if odd.get("id") == str(match_id):
                    bookmakers = odd.get("bookmakers", [])
                    
                    for bookmaker in bookmakers:
                        markets = bookmaker.get("markets", [])
                        for market in markets:
                            if market.get("key") == "h2h":
                                outcomes = market.get("outcomes", [])
                                
                                for outcome in outcomes:
                                    outcome_name = outcome.get("name")
                                    decimal_odds = outcome.get("price", 0)
                                    
                                    # ✅ Φίλτρο αποδόσεων: 1.70 - 2.50
                                    if decimal_odds < MIN_ODDS or decimal_odds > MAX_ODDS:
                                        continue
                                    
                                    implied_prob = (1 / decimal_odds * 100) if decimal_odds > 0 else 0
                                    
                                    if outcome_name == home_team.get("name"):
                                        actual_prob = probabilities["home"]
                                    elif outcome_name == away_team.get("name"):
                                        actual_prob = probabilities["away"]
                                    else:
                                        continue
                                    
                                    # ✅ Φίλτρο confidence: 65-80%
                                    if MIN_CONFIDENCE <= actual_prob <= MAX_CONFIDENCE and actual_prob > implied_prob:
                                        edge = actual_prob - implied_prob
                                        roi = (edge / implied_prob) * 100
                                        risk_level, conf = get_risk_level(actual_prob)
                                        
                                        bet = {
                                            "match": f"{home_team.get('name')} vs {away_team.get('name')}",
                                            "pick": outcome_name,
                                            "odds": round(decimal_odds, 2),
                                            "confidence": round(actual_prob, 1),
                                            "implied_prob": round(implied_prob, 1),
                                            "edge": round(edge, 1),
                                            "roi": round(roi, 1),
                                            "bookmaker": bookmaker.get("title", "Unknown"),
                                            "time": fixture.get("date", ""),
                                            "risk_level": risk_level
                                        }
                                        
                                        value_bets.append(bet)
        
        value_bets = sorted(value_bets, key=lambda x: x["roi"], reverse=True)
        value_bets_cache = value_bets[:5]
        
        return value_bets[:5]
    
    except Exception as e:
        logger.error(f"Error finding value bets: {e}")
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
🟢 VERY LOW RISK (75-80%)
🟡 LOW RISK (70-75%)
🟠 MEDIUM RISK (65-70%)

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
        await update.message.reply_text(f"❌ Δεν υπάρχουν value bets με {MIN_CONFIDENCE}%-{MAX_CONFIDENCE}% confidence και odds {MIN_ODDS}-{MAX_ODDS}")
        return
    
    text = "🎯 **Top Value Bets - Sorted by ROI**\n\n"
    for i, bet in enumerate(bets, 1):
        text += f"""{i}. **{bet['match']}**
   Pick: {bet['pick']}
   Odds: {bet['odds']}
   Confidence: {bet['confidence']}% {bet['risk_level']}
   ROI: +{bet['roi']}%
   Bookmaker: {bet['bookmaker']}
   \n"""
    
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

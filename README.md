# 🎯 Betting AI Bot - Value Betting with 65%+ Confidence

Τηλεγραφικό bot που βρίσκει **value bets** με ελάχιστη σιγουριά **65%**.

## 🚀 Features

✅ **Value Betting Logic** - Συγκρίνει αποδόσεις με στατιστικές πιθανότητες
✅ **65%+ Confidence Filter** - Μόνο σίγουρα bets
✅ **Live Monitoring** - Αυτόματες ενημερώσεις
✅ **ROI Calculation** - Expected return per bet
✅ **Multi-Bookmaker Comparison** - Καλύτερες αποδόσεις
✅ **Telegram Integration** - Easy access & notifications

## 📋 Setup

### 1. Clone Repository
```bash
git clone https://github.com/thanasischalastaras1-wq/betting-ai-bot.git
cd betting-ai-bot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure .env
```bash
cp .env.example .env
```

Επίλεξε τις τιμές σου:
```env
TELEGRAM_TOKEN=your_token_here
API_FOOTBALL_KEY=your_key_here
ODDS_API_KEY=your_key_here
YOUR_CHAT_ID=your_chat_id_here
MIN_CONFIDENCE=65
```

### 4. Run Bot
```bash
python main.py
```

## 🎮 Commands

```
/start      - Ενεργοποίηση bot
/status     - Κατάσταση bot
/topbets    - Top value bets
/help       - Βοήθεια
/stats      - Στατιστικά
```

## 📊 How It Works

1. **Fetch Matches** - Παίρνει τρέχοντα/upcoming matches
2. **Calculate Probability** - Υπολογίζει πιθανότητες νίκης
3. **Get Odds** - Παίρνει τις καλύτερες αποδόσεις
4. **Find Value** - Εντοπίζει όπου actual prob > implied prob
5. **Filter 65%+** - Κρατάει μόνο high-confidence bets
6. **Alert User** - Στέλνει ειδοποίηση στο Telegram

## 🔗 APIs Used

- **API Football** (v3.football.api-sports.io) - Match data & stats
- **The Odds API** (the-odds-api.com) - Live odds
- **Telegram Bot API** - Notifications

## ⚙️ Configuration

**MIN_CONFIDENCE** (default: 65%)
- Όλα τα bets πρέπει να έχουν τουλάχιστον 65% confidence
- Αλλάξτε στο `.env` για διαφορετικό threshold

## 📈 Expected ROI

- **65-70% confidence**: +10-15% ROI
- **70-80% confidence**: +15-25% ROI
- **80%+ confidence**: +25%+ ROI

## ⚠️ Disclaimer

Αυτό το bot είναι **για εκπαιδευτικούς σκοπούς**. Το betting ενέχει κίνδυνο απώλειας χρημάτων. Χρησιμοποιήστε υπεύθυνα!

## 📞 Support

Αν έχετε προβλήματα, δημιουργήστε ένα **Issue** στο repo.

---

**Made with ❤️ for value bettors**

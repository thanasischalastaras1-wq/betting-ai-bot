# Replit setup for Betting AI Bot

Αυτό το αρχείο περιγράφει τα βήματα για να τρέξεις το project στο Replit.

Αρχεία που προστέθηκαν ειδικά για Replit:
- `.replit` — ορίζει την εντολή εκκίνησης του repl.
- `requirements.txt` — εξαρτήσεις Python που θα εγκατασταθούν αυτόματα.

Βήματα (GUI - προτεινόμενος τρόπος)
1. Σύνδεση / Import
   - Σύνδεση στο https://replit.com και κάνε "New repl" → "Import from GitHub".
   - Επικόλλησε το URL του repo: `https://github.com/thanasischalastaras1-wq/betting-ai-bot` και κάνε Import.

2. Environment variables (Secrets)
   - Στην αριστερή μπάρα πάτα το εικονίδιο "Secrets" (λουκέτο).
   - Πρόσθεσε τα παρακάτω keys (τουλάχιστον):
     - `TELEGRAM_TOKEN` = <το token του bot>
     - `API_FOOTBALL_KEY` = <api football key>
     - `ODDS_API_KEY` = <odds api key>
     - `MIN_CONFIDENCE` = 50
     - `MAX_CONFIDENCE` = 95
     - `MIN_ODDS` = 1.20
     - `MAX_ODDS` = 4.00

3. Εκτέλεση
   - Πάτα "Run". Το Replit θα εκτελέσει την εντολή που βρίσκεται στο `.replit`:
     `pip install -r requirements.txt && uvicorn webhook_app:app --host 0.0.0.0 --port $PORT`
   - Αυτό θα εγκαταστήσει τις εξαρτήσεις και θα ξεκινήσει τον Uvicorn server που τρέχει την `webhook_app`.

4. Ρύθμιση Webhook στο Telegram
   - Πάρε το public URL του Repl (Open in new tab) — π.χ. `https://project-username.repl.co`.
   - Στο Shell του Replit τρέξε (ή τοπικά):
     ```bash
     curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook" -d "url=https://<your-repl-url>/webhook/$TELEGRAM_TOKEN"
     ```
   - Αν όλα πάνε καλά, το Telegram θα επιστρέψει `{"ok":true,...}`.

5. Δοκιμή
   - Στείλε `/status` ή `/topbets` στο bot στο Telegram — θα πρέπει να απαντήσει.

Σημειώσεις / Προειδοποιήσεις
- Τα δωρεάν Replit repls συνήθως "κοιμούνται" μετά από αδράνεια, οπότε δεν εγγυώνται 24/7 uptime. Για συνεχή λειτουργία χρειάζεται το Replit "Always On" (πληρωμένο) ή deploy σε άλλο πάροχο (π.χ. Deta, Railway).
- Μην αποθηκεύετε μυστικά API keys στο repo. Χρησιμοποίησε τα Secrets του Replit.
- Αν το bot δεν απαντάει, έλεγξε τα logs (console) για errors και βεβαιώσου ότι το webhook έχει ρυθμιστεί σωστά.

Troubleshooting (συχνά προβλήματα)
- Error κατά το `git pull` στο Shell: Μην συνδυάζεις πολλαπλές εντολές σε μία γραμμή χωρίς `&&`.
- Όταν αλλάξεις κώδικα στο GitHub, κάνε Pull στο Replit μέσω Shell ή επαν-Import.
- Αν δεις timeout στον webhook, ίσως χρειάζεται να μεταφέρεις βαριά δουλειά σε background task ή να κάνεις caching των κλήσεων στο API.

Αν θέλεις, μπορώ να προσαρμόσω επιπλέον ένα μικρό αρχείο `server.py` ή `Procfile` αν το Replit θέλει διαφορετικό entrypoint.

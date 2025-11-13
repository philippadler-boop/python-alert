# 📉 SPX Dip Alert — Automated Drawdown Email Notifications

This project monitors the **S&P 500 index (^GSPC)** and automatically sends email alerts whenever the market hits predefined **drawdown (“dip”) levels**.  
It works both **locally** and fully **automated in GitHub Actions**, meaning alerts continue even when your PC is off.

Alerts include:

- Drawdown % from the most recent high  
- Current SPX price  
- Recent high + date  
- Bucket triggered (–5%, –10%, –20%)  
- Your dip-buying plan instructions  
- Attached SPX chart  
- CSV logging of all alerts  

---

## 🚨 Dip Trigger Levels

| Drawdown Range | Bucket | Action |
|----------------|--------|--------|
| –5% to –8%     | B10    | Deploy **10%** of cash bucket |
| –10% to –15%   | B20    | Deploy **20%** |
| –20% or more   | B70    | Deploy remaining **70%** in weekly tranches |

---

## 📦 Features

### ✔️ Drawdown Detection
- Fetches daily data via `yfinance`
- Computes drawdown from the latest rolling high

### ✔️ Email Alerts (Gmail SMTP)
- Sends a formatted alert email  
- Includes a PNG price chart  
- Uses Gmail App Password (secure OAuth alternative)

### ✔️ Logging
- CSV log of all alerts  
- Automatic cleanup of logs & plots older than 30 days

### ✔️ GitHub Actions Automation
- Runs automatically **Monday–Friday** at **16:30 Berlin time**  
- Continues running even when your PC is off  
- Supports manual test runs using `--test-bucket`

---

# 🚀 GitHub Actions Automation

The workflow file lives at:

```

.github/workflows/alert.yml

````

It runs:

- **Scheduled**: Every weekday at **16:30 Europe/Berlin**  
- **Manual**: Via the *Run workflow* button (Actions → Run workflow)

---

## 🔐 Required GitHub Secrets

Add these in:

**Repo → Settings → Secrets and variables → Actions**

| Secret Name   | Value |
|---------------|-------|
| `FROM_EMAIL`  | Your Gmail address |
| `TO_EMAIL`    | Where alerts are sent |
| `APP_PASSWORD`| Gmail App Password (16 characters) |

---

# 🖥️ Running Locally

## 1️⃣ Install dependencies

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
````

## 2️⃣ Add `.env` file (not committed — ignored by git)

Create a `.env` file:

```
FROM_EMAIL=your@gmail.com
TO_EMAIL=your@gmail.com
APP_PASSWORD=your_app_password

LOCAL_TZ=Europe/Berlin
SAVE_PLOTS=1
INLINE_IMAGE=0
RETENTION_DAYS=30
```

## 3️⃣ Run the script normally

```bash
python spx_dip_alert_mail.py
```

## 4️⃣ Run a test alert

```bash
python spx_dip_alert_mail.py --test-bucket B10
```

This generates:

* A test email
* A plot saved under `plots/`
* A CSV log entry

---

# 🧪 Testing via GitHub Actions

To test without waiting for a real dip:

1. Go to **Actions**
2. Select **SPX Dip Alert (Daily)**
3. Click **Run workflow**

Depending on configuration, this can run:

* Normal mode
* Test-bucket mode (if implemented)

Artifacts (plots + CSV) appear when generated.

---

# 📊 Outputs

## 📈 Plot

Each alert includes a plot showing:

* Recent SPX close prices
* Rolling high
* Current price marker
* Clean formatting for email readability

Plots are saved under:

```
plots/
```

## 🗂️ CSV Log

`spx_dip_alert_log.csv` tracks:

* Timestamp
* Bucket (B10/B20/B70)
* Drawdown %
* Close
* Peak
* Peak date
* Note / plan
* Ticker
* Test vs real flag
* Plot path

## 🧹 Automatic Cleanup

The script automatically deletes old data:

* Plot PNGs older than `RETENTION_DAYS`
* CSV log rows older than `RETENTION_DAYS`

(Default retention: **30 days**)

---

# 🏗️ Project Structure

```
python-alert/
│
├── spx_dip_alert_mail.py
├── requirements.txt
├── .gitignore
├── README.md
├── spx_alert_state.json
├── plots/
├── spx_dip_alert_log.csv
└── .github/
    └── workflows/
        └── alert.yml
```

---

# 🔒 Security

* `.env` is ignored via `.gitignore`
* Gmail **App Password** is used (safer than your main password)
* GitHub Secrets are encrypted
* Repo is private
* SMTP uses TLS for encryption

---

# 🧠 Troubleshooting

### “No artifacts appear”

Artifacts appear only if:

* A dip alert fired, OR
* You ran a test bucket alert

### “Email not sending”

Verify:

* Gmail App Password is correct
* All GitHub Secrets are set
* `FROM_EMAIL` matches the Gmail account used for the app password

### “Cron time seems wrong”

GitHub cron uses **UTC**.

You are using:

```
30 15 * * 1-5
```

This is:

* 15:30 UTC
* → **16:30 Berlin** (CET)
* → **17:30 Berlin** (CEST)

---

# 🎉 Summary

You now have a **fully automated cloud-powered SPX dip alert system**, featuring:

* SPX dip detection
* Email alerts
* Plot attachments
* Local + GitHub logging
* Auto-cleanup
* Weekday scheduling
* Manual test mode
* Secure secrets handling

If you want enhancements, I can add:

* Weekly summary emails
* Discord/Slack/Telegram alerts
* HTML email templates
* Support for additional indices

Just ask!

```

---

If you want the README to also include **shields.io badges** (build passing, last run, license, Python version, etc.), I can generate them too.
```

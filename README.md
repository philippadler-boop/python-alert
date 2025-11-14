
# 📉📈 SPX Alert — Dip Alerts + Trend Entry Alerts

A fully automated alerting tool for:

- **Dip-buying signals** (based on drawdowns from recent highs)
- **Trend-entry signals** (price crossing above MA200 & holding for N days)
- **Email notifications** (plain text + optional HTML with plots)
- **Plot generation** (dip plots + MA200 trend plots)
- **Daily GitHub Actions automation**
- **Test modes** for both dip and trend alerts

Supports any ticker.  
Preconfigured for:

- **SPX** (S&P 500)
- **NDX** (Nasdaq 100)
- **SOX** (Semiconductors — PHLX)
- **SRVR** (Data Center & Digital Infrastructure ETF)
- **SRUUF** (Sprott Uranium Miners ETF — *replacing URA*)
- **REMX** (Rare Earth & Strategic Metals ETF)

## 🔄 Why SRUUF Instead of URA?

You chose to switch from **URA** to **SRUUF**.  
This change makes sense because:

### ✅ SRUUF Advantages
- Pure-play uranium miners exposure  
- Heavier weight in **Cameco, NexGen, Denison, Uranium Energy Corp**, etc.  
- Better representation of the **uranium mining cycle**  
- More sensitive to spot-price uptrends (your trend-entry logic benefits from this)

### ✔️ What Changed in the Tool
- The index list now uses **SRUUF** instead of URA.
- The *trend-entry checklist* references uranium miners & macro indicators.
- All alert output and GitHub workflows reflect the new ticker.

---

(Your full README structure continues here…)

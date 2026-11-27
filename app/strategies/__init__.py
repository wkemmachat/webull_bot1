"""Strategy registry: types come from the modules in this folder, instances (with their parameters,
colour, money controls and LINE switch) are rows in the `strategies` table."""
from __future__ import annotations

import importlib
import json
import pkgutil
import time

from .. import db
from .base import TYPES, StrategyBase, register  # noqa: F401

_loaded = False

_QLD_BASE = {"signal": "QQQ", "trade": "QLD", "cash_symbol": "", "gold_share_pct": 50.0, "gold_symbol": "GLD"}
QLD_2C_LEGS = [
    {"name": "QLD-A · EMA100 trend + dips", "type": "trend_gate",
     "params": {**_QLD_BASE, "ma_type": "EMA", "ma_days": 100, "vol_gate_q": 80.0, "vol_days": 20, "vol_lookback": 252, "rsi_buy": 5.0,
                "rsi_len": 2, "exit_ma": 5, "dip_ibs_max": 0.15, "dip_ibs_symbol": "QLD", "jumpy_ibs_max": 0.0, "target_vol_pct": 0.0}},
    {"name": "QLD-B · IBD or SMA200, vol 60%", "type": "ibd_gate",
     "params": {**_QLD_BASE, "trend_mode": "SMA|IBD", "ma_days": 200, "ibd_dist": 6, "ibd_expire_pct": 5.0, "target_vol_pct": 60.0,
                "dip_vol_cap_pct": 0.0}},
    {"name": "QLD-C · IBD, vol 40%", "type": "ibd_gate",
     "params": {**_QLD_BASE, "trend_mode": "IBD", "ibd_dist": 6, "ibd_expire_pct": 5.0, "target_vol_pct": 40.0, "dip_vol_cap_pct": 40.0}},
]
_ROM_TODAY = {"signal": "IYW", "trade": "ROM", "cash_symbol": "", "gold_share_pct": 0.0, "ma_type": "EMA", "ma_days": 150,
              "vol_gate_q": 90.0, "vol_days": 20, "vol_lookback": 252, "rsi_buy": 5.0, "rsi_len": 2, "exit_ma": 5, "dip_ibs_max": 0.15,
              "dip_ibs_symbol": "ROM", "jumpy_ibs_max": 0.0, "target_vol_pct": 0.0}
ROM_2C_LEGS = [
    {"name": "ROM · Trend + Vol + RSI & IBS dips", "type": "trend_gate", "weight": 67, "params": dict(_ROM_TODAY)},
    {"name": "ROC252 + credit + 3-down & IBS dips", "type": "trend_gate", "weight": 33,
     "params": {"signal": "IYW", "trade": "ROM", "cash_symbol": "", "gold_share_pct": 50.0, "gold_symbol": "GLD", "ma_type": "ROC",
                "ma_days": 252, "vol_gate_q": 0.0, "credit_ma": 100, "credit_a": "LQD", "credit_b": "IEF", "dip_entry": "3DOWN",
                "rsi_buy": 0.0, "exit_ma": 5, "dip_ibs_max": 0.2, "dip_ibs_symbol": "ROM", "jumpy_ibs_max": 0.0, "target_vol_pct": 0.0}},
]
DEFAULTS = [
    ("gold_sta", "supertrend", "Gold #1 · Supertrend + ADX", "#F2C14E",
     {"symbol": "GC", "atr": 30, "mult": 2.5, "adx_min": 20, "adx_len": 14, "etf": "UGL", "cash_etf": ""}, {}),
    ("gold_st30", "supertrend", "Gold #2 · Supertrend 30/2.5", "#B9852C",
     {"symbol": "GC", "atr": 30, "mult": 2.5, "adx_min": 0, "etf": "UGL", "cash_etf": ""}, {}),
    ("silver_dc", "donchian", "Silver #1 · Donchian 30/15", "#D5DBE3",
     {"symbol": "SI", "entry": 30, "exit": 15, "etf": "AGQ", "cash_etf": ""}, {}),
    ("silver_st", "supertrend", "Silver #2 · Supertrend 10/3", "#8592A3",
     {"symbol": "SI", "atr": 10, "mult": 3.0, "adx_min": 0, "etf": "AGQ", "cash_etf": ""}, {}),
    ("qld_regime", "regime", "QLD regime", "#5B8DEF",
     {"signal": "QQQ", "trade": "QLD", "off_symbol": "GLD", "cash_symbol": "", "vol_gate_pct": 30}, {}),
    ("semis_regime", "regime", "2x Semis regime", "#B084F5",
     {"signal": "SMH", "trade": "USD", "off_symbol": "GLD", "cash_symbol": "", "vol_gate_pct": 40}, {}),
    ("qld_tbd", "trend_dip", "QLD + Trend + bear-dip", "#3DC9C0",
     {"signal": "QQQ", "trade": "QLD", "cash_symbol": "", "ma_days": 200, "rsi_len": 2, "rsi_buy": 5.0, "exit_ma": 5}, {}),
    ("c27_mom", "momentum_basket", "C2-7 Momentum 1x", "#E8875A", {"leverage": "1x"}, {}),
    ("c27_mom2x", "momentum_basket", "C2-7 Momentum 2x", "#9BCB4E", {"leverage": "2x"}, {}),
    ("qld_ibs", "ibs_dip", "QLD Trend + IBS-dip", "#E46AA8",
     {"trade": "QLD", "vol_symbol": "QQQ", "gold_etf": "GLD", "cash_symbol": "BIL", "ibs_max": 0.15, "adx_min": 20, "target_vol_pct": 50,
      "tbill_cash": True}, {}),
    ("usd_ibs", "ibs_dip", "USD Trend + IBS-dip", "#4FC3F7",
     {"trade": "USD", "vol_symbol": "USD", "compare_symbol": "SMH", "gold_etf": "GLD", "cash_symbol": "BIL", "st_atr": 20, "st_mult": 4.5,
      "ma_days": 200, "ibs_max": 0.15, "adx_min": 0, "target_vol_pct": 40, "leverage": 1, "vol_days": 20, "dip_full_size": True,
      "size_band_pct": 20, "tbill_cash": True}, {}),
    ("rom_tbd", "trend_dip", "ROM Trend + RSI(2)", "#20C997",
     {"signal": "IYW", "trade": "ROM", "cash_symbol": "", "ma_days": 150, "rsi_len": 2, "rsi_buy": 5.0, "exit_ma": 10}, {}),
    ("qld_tbdv", "trend_dip", "QLD Trend + bear-dip + Vol", "#7FDBCA",
     {"signal": "QQQ", "trade": "QLD", "cash_symbol": "", "ma_days": 200, "rsi_len": 2, "rsi_buy": 5.0, "exit_ma": 5,
      "vol_gate_q": 80.0, "vol_days": 20, "gold_share_pct": 50.0, "gold_symbol": "GLD"}, {}),
    # 2 Nov 2026 challengers ("2x ETF Strategy Challengers" + stress tests): added with no money; move money from
    # USD Trend + IBS-dip and ROM Trend + RSI(2) yourself when you want them to trade.
    ("usd_smh_ibs", "trend_gate", "USD · SMH trend + SMH IBS-dip", "#2E86DE",
     {"signal": "SMH", "trade": "USD", "cash_symbol": "", "gold_share_pct": 0.0, "ma_type": "SMA", "ma_days": 125,
      "vol_gate_q": 80.0, "vol_days": 20, "vol_lookback": 504, "rsi_buy": 0.0, "dip_ibs_max": 0.25, "dip_ibs_symbol": "SMH",
      "jumpy_ibs_max": 0.15, "jumpy_ibs_symbol": "USD", "target_vol_pct": 40.0, "size_vol_days": 20, "size_band_pct": 20.0}, {}),
    ("rom_vol_ibs", "trend_gate", "ROM · Trend + Vol + RSI & IBS dips", "#12B886",
     {"signal": "IYW", "trade": "ROM", "cash_symbol": "", "gold_share_pct": 0.0, "ma_type": "EMA", "ma_days": 150,
      "vol_gate_q": 90.0, "vol_days": 20, "vol_lookback": 252, "rsi_buy": 5.0, "rsi_len": 2, "exit_ma": 5, "dip_ibs_max": 0.15,
      "dip_ibs_symbol": "ROM", "jumpy_ibs_max": 0.0, "target_vol_pct": 0.0}, {}),
    # 3 Nov 2026 gold challenger G1 ("Gold & Silver Challengers" + full stress test): added with no money; move the money
    # from Gold #1 and Gold #2 yourself when you want it to trade.
    ("gold_trend_calm", "metal_trend_calm", "Gold · Slow trend + calm + RSI dips", "#D4A017",
     {"symbol": "GC", "atr": 150, "mult": 4.0, "daily_ma": 50, "vol_q": 80.0, "vol_days": 20, "vol_lookback": 252,
      "rsi_len": 2, "rsi_buy": 5.0, "dip_ma": 200, "exit_ma": 5, "etf": "UGL", "cash_etf": ""}, {}),
    # 3 Nov 2026 silver challengers S1 and S3 (same research, full stress test): added with no money; split the silver money
    # between them yourself when you want them to trade.
    ("silver_gold_ok", "metal_trend_sized", "Silver · Trend with gold's OK + vol size", "#A9B8C9",
     {"symbol": "SI", "atr": 40, "mult": 2.5, "gold_confirm": True, "gold_atr": 30, "gold_mult": 2.5, "daily_ma": 0, "gsr_ma": 0,
      "one_x_etf": "", "target_vol_pct": 70.0, "size_vol_days": 40, "size_band_pct": 10.0, "etf": "AGQ", "cash_etf": ""}, {}),
    ("silver_lead_1x", "metal_trend_sized", "Silver · Trend + silver leading, else 1x", "#6E7F94",
     {"symbol": "SI", "atr": 180, "mult": 4.0, "gold_confirm": False, "daily_ma": 100, "gsr_ma": 100, "one_x_etf": "SLV",
      "target_vol_pct": 40.0, "size_vol_days": 20, "size_band_pct": 10.0, "etf": "AGQ", "cash_etf": ""}, {}),
    # 10 Nov 2026 "DDM · RXL · SSO: 1x signals and a better rule": hold the 2x ETF while its 1x market ETF is calm (DDM, SSO: or
    # above SMA100) and under 25% volatility; IBS dips otherwise. Added with no money.
    ("rxl_calm_guard", "calm_guard", "RXL · Calm guard + dips", "#FF6B6B",
     {"trade": "RXL", "market": "XLV", "cash_symbol": "", "gold_share_pct": 0.0, "calm_pct": 80, "vol_days": 20, "vol_lookback": 252,
      "uptrend_ma_days": 0, "vol_cap_pct": 25.0, "dip_ibs_max": 0.15, "dip_max_days": 5, "dip_vol_cap_pct": 40.0}, {}),
    ("ddm_calm_guard", "calm_guard", "DDM · Calm guard + dips", "#C77DFF",
     {"trade": "DDM", "market": "DIA", "cash_symbol": "", "gold_share_pct": 0.0, "calm_pct": 80, "vol_days": 20, "vol_lookback": 252,
      "uptrend_ma_days": 100, "vol_cap_pct": 25.0, "dip_ibs_max": 0.15, "dip_max_days": 5, "dip_vol_cap_pct": 40.0}, {}),
    ("sso_calm_guard", "calm_guard", "SSO · Calm guard + dips", "#7986CB",
     {"trade": "SSO", "market": "SPY", "cash_symbol": "", "gold_share_pct": 0.0, "calm_pct": 80, "vol_days": 20, "vol_lookback": 252,
      "uptrend_ma_days": 100, "vol_cap_pct": 25.0, "dip_ibs_max": 0.15, "dip_max_days": 5, "dip_vol_cap_pct": 40.0}, {}),
    # 15 Nov 2026 "Strategy research and stress tests", round 3 USD split C: a third each in SMA150 / ROC126 / EMA150 on SMH with
    # calm and credit (LQD ÷ IEF) gates and one-day SMH IBS dips, rebalanced once a year. Added with no money.
    ("usd_trend_split", "trend_split", "USD · Trend split (3 rules + credit check)", "#1C7ED6",
     {"signal": "SMH", "trade": "USD", "cash_symbol": "", "leg1_kind": "SMA", "leg1_days": 150, "leg1_calm_q": 90.0,
      "leg2_kind": "ROC", "leg2_days": 126, "leg2_calm_q": 90.0, "leg3_kind": "EMA", "leg3_days": 150, "leg3_calm_q": 80.0,
      "vol_days": 20, "vol_lookback": 252, "credit_a": "LQD", "credit_b": "IEF", "credit_ma": 100, "dip_ibs_max": 0.3,
      "dip_ibs_symbol": "SMH", "rebalance_legs": "yearly"}, {}),
    # 15 Nov 2026 "Strategy research and stress tests", round 2 QLD split C: a third each in QLD-A (EMA100 trend + calm + dips),
    # QLD-B (IBD or SMA200 trend + calm, vol 60%) and QLD-C (IBD trend + calm, vol 40%), rebalanced once a year. Added with no money.
    ("qld_split_2c", "split_mix", "QLD · Split 2C (3 strategies, a third each)", "#2F9E44",
     {"signal": "QQQ", "trade": "QLD", "rebalance_legs": "yearly", "legs": json.dumps(QLD_2C_LEGS)}, {}),
    # 15 Nov 2026 "Strategy research and stress tests", round 2 ROM split C: 67% in ROM · Trend + Vol + RSI & IBS dips (the same
    # rules as rom_vol_ibs) and 33% in a new rule (IYW ROC252 + credit check, 3-down and ROM IBS dips, half GLD when out),
    # rebalanced once a year. Added with no money.
    ("rom_split_2c", "split_mix", "ROM · Split 2C (today's best 67% + ROC252 & credit 33%)", "#0CA678",
     {"signal": "IYW", "trade": "ROM", "rebalance_legs": "yearly", "legs": json.dumps(ROM_2C_LEGS)}, {}),
    # 15 Nov 2026 "Strategy research and stress tests", round 1 SSO-A: SSO while SPY's EMA60 is above its EMA130 (a slow MACD
    # above zero) and calm; below it, dip trades after SPY IBS < 0.20 (sold above SMA5) and one-day buys after RSI(2) < 10.
    # Added with no money.
    ("sso_macd_calm", "trend_gate", "SSO · Slow MACD + calm + dips", "#5C7CFA",
     {"signal": "SPY", "trade": "SSO", "cash_symbol": "", "gold_share_pct": 0.0, "ma_type": "XEMA", "fast_days": 60, "ma_days": 130,
      "vol_gate_q": 90.0, "vol_days": 20, "vol_lookback": 252, "dip_entry": "IBS", "entry_ibs_max": 0.2, "exit_ma": 5, "rsi_buy": 0.0,
      "rsi_len": 2, "rsi_1d_buy": 10.0, "dip_ibs_max": 0.0, "jumpy_ibs_max": 0.0, "target_vol_pct": 0.0}, {}),
    # 15 Nov 2026 "Strategy research and stress tests", round 1 RXL-A: RXL while XLV's Ichimoku cloud trend (18/48/96) is on,
    # XLV is calm and SPY is above its SMA200, sized 60% ÷ RXL volatility; below the cloud, dip trades after XLV IBS < 0.25 (sold
    # above the previous high or after 5 days) and one-day buys after RSI(2) < 5; half GLD when out. Added with no money.
    ("rxl_ichi_calm", "trend_gate", "RXL · Ichimoku cloud + calm + S&P check + dips", "#F06595",
     {"signal": "XLV", "trade": "RXL", "cash_symbol": "", "gold_share_pct": 50.0, "gold_symbol": "GLD", "ma_type": "ICHI",
      "ichi_tenkan": 18, "ichi_kijun": 48, "ma_days": 96, "ichi_shift": 48, "vol_gate_q": 80.0, "vol_days": 20, "vol_lookback": 252,
      "mkt_symbol": "SPY", "mkt_ma_days": 200, "dip_entry": "IBS", "entry_ibs_max": 0.25, "dip_exit": "PREVHIGH", "dip_max_days": 5,
      "rsi_buy": 0.0, "rsi_len": 2, "rsi_1d_buy": 5.0, "dip_ibs_max": 0.0, "jumpy_ibs_max": 0.0, "target_vol_pct": 60.0,
      "size_vol_days": 20, "size_band_pct": 20.0}, {}),
    # 26 Nov 2026 "CWEB (2x China internet): best buy/sell rules", Pick 4+: KWEB breakout + FXI above SMA200 (size 30% ÷ CWEB
    # volatility, 15% trailing stop), 100% at the US open after a Hang Seng close of −3% or worse (take-profit 4% at the next
    # open, else sold two days later) and a one-day 40% limit buy after a −1.75% to −3% close. Added with no money.
    ("cweb_trend_crash", "hk_crash", "CWEB · Trend + Hang Seng crash buys", "#E03131",
     {"trade": "CWEB", "signal": "KWEB", "gate": "FXI", "hk_index": "^HSI", "don_entry": 20, "don_exit": 15, "gate_ma": 200,
      "target_vol_pct": 30.0, "vol_days": 20, "size_band_pct": 20.0, "trail_pct": 15.0, "big_drop_pct": 3.0, "tp_pct": 4.0,
      "small_drop_pct": 1.75, "small_size_pct": 40.0, "small_limit_pct": 1.0, "cash_buffer_pct": 1.0, "rebalance_band_pct": 5.0}, {}),
    # 26 Nov 2026 "QPUX: two best strategies per window", round 3 Safe: 0.4 × one-day dip after a weak close of the quantum-stock
    # basket + 0.5 × trend (QPUX > SMA50, QQQ > SMA200, size 60% ÷ volatility) + 0.25 × RSI(2) bounce, every leg only while
    # Bitcoin is above its 100-day average. Added with no money.
    ("qpux_safe", "quantum_mix", "QPUX · Dip + trend + RSI, Bitcoin check (Safe)", "#7950F2",
     {"trade": "QPUX", "basket": "QUBT:2021-10-01,IONQ:2021-10-01,RGTI:2022-03-02,QBTS:2022-08-08", "market": "QQQ", "btc": "BTC-USD",
      "dip_weight": 0.4, "dip_ibs_max": 0.2, "dip_ma": 200, "trend_weight": 0.5, "trend_ma": 50, "market_ma": 200, "target_vol_pct": 60.0,
      "vol_days": 20, "size_band_pct": 5.0, "rsi_weight": 0.25, "rsi_len": 2, "rsi_buy": 10.0, "rsi_exit_ma": 5, "btc_ma": 100,
      "btc_all": True, "model_cost_pct": 21.3, "cash_buffer_pct": 1.0, "rebalance_band_pct": 5.0}, {}),
    # 26 Nov 2026 "RAM (2x memory ETF): two best strategies", rule A (kept after round 2): hold RAM while MU and SMH are above
    # their close of 126 days ago, MU above its close of 20 days ago and SMH calm (20-day volatility at or below its 90th
    # percentile of 504 days); otherwise one-day buys after RAM closes near its low (IBS < 0.10). Added with no money.
    ("ram_mom_calm", "momentum_calm", "RAM · Momentum + calm + one-day dips", "#F76707",
     {"trade": "RAM", "mom_symbols": "MU,SMH", "mom_days": 126, "fast_symbol": "MU", "fast_days": 20, "calm_symbol": "SMH", "vol_days": 20,
      "vol_lookback": 504, "calm_pct": 90.0, "dip_ibs_max": 0.10, "model_basket": "MU:70,STX:15,WDC:15", "model_cost_pct": 18.5,
      "cash_buffer_pct": 1.0, "rebalance_band_pct": 20.0}, {}),
    # 27 Nov 2026 UWM research rounds 2–3: rule A3 (IWM > EMA100, LQD credit, SPY > SMA200, vol < 35%, 99%) and rule R3
    # (IWM > EMA150, HYG credit, SPY, vol < 30%, XLY/XLP risk-on, 75%), each with calm IBS dips, half each in one position.
    # Added with no money.
    ("uwm_a3_r3", "two_rule_mix", "UWM · Trend + credit + calm dips (A3 + R3)", "#1098AD",
     {"trade": "UWM", "signal": "IWM", "spy": "SPY", "weight_a": 0.5, "weight_r": 0.5, "a_ema": 100, "a_vol_cap": 35.0, "a_size_pct": 99.0,
      "r_ema": 150, "r_vol_cap": 30.0, "r_size_pct": 75.0, "risk_ma": 100, "credit_ma": 100, "spy_ma": 200, "dip_ibs_max": 0.15,
      "dip_days": 5, "vol_days": 20, "calm_lookback": 252, "calm_pct": 90.0, "cash_buffer_pct": 1.0, "rebalance_band_pct": 10.0}, {}),
    # 27 Nov 2026 TSXU research Strategy 2+ (unbeaten after four rounds): hold TSXU while SMH > EMA200 (1% band), SMH calm and
    # LQD/IEF > SMA100; otherwise one-day buys after SMH IBS < 0.25 (75% when SMH is stormy). Added with no money.
    ("tsxu_2plus", "trend_credit_dip", "TSXU · Trend + calm + credit + dips (2+)", "#E8590C",
     {"trade": "TSXU", "signal": "SMH", "ema_days": 200, "band_pct": 1.0, "vol_days": 20, "vol_lookback": 252, "calm_q": 90.0,
      "credit_ma": 100, "dip_ibs_max": 0.25, "dip_size_pct": 100.0, "storm_q": 95.0, "storm_size_pct": 75.0, "model_basket": "SMH:100",
      "model_cost_pct": 5.0, "cash_buffer_pct": 1.0, "rebalance_band_pct": 20.0}, {}),
    # 27 Nov 2026 CHAU research S4 (kept after round 4): half on ASHR Supertrend 10/2 + FXI > SMA200, half on CHAU IBS < 0.2 dips
    # (CHAU > SMA100, LQD/IEF > SMA100), both only while USD/CNY is below its SMA50. Added with no money.
    ("chau_s4", "half_trend_dip", "CHAU · Half trend + half dip, yuan filter (S4)", "#C92A2A",
     {"trade": "CHAU", "trend_symbol": "ASHR", "gate_symbol": "FXI", "dip_symbol": "CHAU", "yuan": "CNY=X", "trend_pct": 50.0,
      "st_atr": 10, "st_mult": 2.0, "fxi_ma": 200, "dip_pct": 50.0, "dip_ibs_max": 0.2, "dip_ma": 100, "credit_ma": 100,
      "exit_ibs": 0.8, "dip_days": 5, "yuan_ma": 50, "yuan_lag": 0, "cash_buffer_pct": 1.0, "rebalance_band_pct": 10.0}, {}),
]
# Earlier defaults: a strategy still on exactly these settings is moved to the new ones once (lower-cost versions, 26 Oct 2026:
# IBS-dip T-bill half as cash + QLD IBS < 0.15; metals flat in cash instead of SGOV).
# Settings you changed yourself are left alone.
UPGRADES = [
    ("lowcost_ibs_2026_10", "qld_ibs",
     {"trade": "QLD", "vol_symbol": "QQQ", "gold_etf": "GLD", "cash_symbol": "BIL", "ibs_max": 0.2, "adx_min": 20, "target_vol_pct": 50}),
    ("lowcost_ibs_2026_10", "usd_ibs",
     {"trade": "USD", "vol_symbol": "USD", "compare_symbol": "SMH", "gold_etf": "GLD", "cash_symbol": "BIL", "st_atr": 20, "st_mult": 4.5,
      "ma_days": 200, "ibs_max": 0.15, "adx_min": 0, "target_vol_pct": 40, "leverage": 1, "vol_days": 20, "dip_full_size": True,
      "size_band_pct": 20}),
    ("lowcost_metals_2026_10", "gold_sta", {"symbol": "GC", "atr": 30, "mult": 2.5, "adx_min": 20, "adx_len": 14, "etf": "UGL", "cash_etf": "SGOV"}),
    ("lowcost_metals_2026_10", "gold_st30", {"symbol": "GC", "atr": 30, "mult": 2.5, "adx_min": 0, "etf": "UGL", "cash_etf": "SGOV"}),
    ("lowcost_metals_2026_10", "silver_dc", {"symbol": "SI", "entry": 30, "exit": 15, "etf": "AGQ", "cash_etf": "SGOV"}),
    ("lowcost_metals_2026_10", "silver_st", {"symbol": "SI", "atr": 10, "mult": 3.0, "adx_min": 0, "etf": "AGQ", "cash_etf": "SGOV"}),
    # 31 Oct 2026: park in cash instead of BIL (each BIL round trip costs 0.22% in fees; plain cash won in every period of the
    # bot's backtest), and QLD Trend + bear-dip + Vol parks half in gold.
    ("cash_parking_2026_10", "qld_regime", {"signal": "QQQ", "trade": "QLD", "off_symbol": "GLD", "cash_symbol": "BIL", "vol_gate_pct": 30}),
    ("cash_parking_2026_10", "semis_regime", {"signal": "SMH", "trade": "USD", "off_symbol": "GLD", "cash_symbol": "BIL", "vol_gate_pct": 40}),
    ("cash_parking_2026_10", "qld_tbd",
     {"signal": "QQQ", "trade": "QLD", "cash_symbol": "BIL", "ma_days": 200, "rsi_len": 2, "rsi_buy": 5.0, "exit_ma": 5}),
    ("cash_parking_2026_10", "qld_tbdv",
     {"signal": "QQQ", "trade": "QLD", "cash_symbol": "BIL", "ma_days": 200, "rsi_len": 2, "rsi_buy": 5.0, "exit_ma": 5,
      "vol_gate_q": 80.0, "vol_days": 20}),
]
UPGRADE_WHY = {"cash_parking_2026_10": "Parks in cash instead of BIL (each BIL round trip cost 0.22% in fees)"}
# Added with LINE alerts off: they hold no money until you move some to them (turn LINE on in the strategy when you do).
QUIET_DEFAULTS = {"usd_smh_ibs", "rom_vol_ibs", "gold_trend_calm", "silver_gold_ok", "silver_lead_1x", "ddm_calm_guard",
                  "sso_calm_guard", "rxl_calm_guard", "usd_trend_split", "qld_split_2c",
                  "rom_split_2c", "sso_macd_calm", "rxl_ichi_calm", "cweb_trend_crash", "qpux_safe", "ram_mom_calm", "uwm_a3_r3", "tsxu_2plus", "chau_s4"}
PALETTE = ["#3DC9C0", "#E8875A", "#E46AA8", "#9BCB4E", "#F2C14E", "#5B8DEF", "#B084F5"]


def load_plugins():
    global _loaded
    if _loaded:
        return
    for m in pkgutil.iter_modules(__path__):
        if m.name not in ("base",):
            importlib.import_module(f"{__name__}.{m.name}")
    _loaded = True


def seed() -> list:
    """Create the research strategies. On the first start all of them; later, a default strategy added in a new
    version is created once (one you archived is never brought back). Returns the ids created now."""
    fresh = not db.one("SELECT id FROM strategies LIMIT 1")
    done = set(db.get_state("seeded_defaults") or ([] if fresh else [d[0] for d in DEFAULTS[:6]]))
    now = int(time.time())
    added = []
    with db.tx() as c:
        n = c.execute("SELECT COUNT(*) FROM strategies").fetchone()[0]
        for k, (sid, typ, name, color, params, ex) in enumerate(DEFAULTS):
            if sid in done or c.execute("SELECT 1 FROM strategies WHERE id=?", (sid,)).fetchone():
                continue
            c.execute("INSERT INTO strategies(id,type,name,color,params,exec,control,line_on,archived,sort,created_at,updated_at) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (sid, typ, name, color, json.dumps(params), json.dumps(ex), "active", 0 if sid in QUIET_DEFAULTS else 1, 0,
                       max(k, n), now, now))
            added.append(sid)
    db.set_state("seeded_defaults", sorted(done | {d[0] for d in DEFAULTS}))
    upgrade_defaults()
    return [] if fresh else added


def upgrade_defaults() -> list:
    """Move strategies that still use an earlier default to the new default (once per upgrade). Returns the ids moved."""
    load_plugins()
    seen = set(db.get_state("upgrades_done") or [])
    moved = []
    for key, sid, old in UPGRADES:
        tag = f"{key}:{sid}"
        if tag in seen:
            continue
        seen.add(tag)
        r = row(sid)
        new = next((d for d in DEFAULTS if d[0] == sid), None)
        cls = TYPES.get(r["type"]) if r else None
        if not r or not new or not cls or r["type"] != new[1]:
            continue
        if cls.merge_params(r["params"]) != cls.merge_params(old):
            continue                                    # changed by you: left alone
        db.run("UPDATE strategies SET params=?, updated_at=? WHERE id=?", (json.dumps(new[4]), int(time.time()), sid))
        changes = {k: v for k, v in cls.merge_params(new[4]).items() if cls.merge_params(old).get(k) != v}
        db.add_event("info", "strategy", f"{r['name']}: settings updated to the new default",
                     UPGRADE_WHY.get(key, "Lower-cost version (Webull fee 0.107% per trade)") + ": " + ", ".join(f"{k} → {v if v != '' else 'cash'}" for k, v in changes.items()),
                     strategy=sid)
        moved.append(sid)
    db.set_state("upgrades_done", sorted(seen))
    return moved


def rows(include_archived=False):
    q = "SELECT * FROM strategies" + ("" if include_archived else " WHERE archived=0") + " ORDER BY sort, created_at"
    out = []
    for r in db.rows(q):
        r["params"] = json.loads(r["params"] or "{}")
        r["exec"] = json.loads(r["exec"] or "{}")
        out.append(r)
    return out


def row(sid):
    r = db.one("SELECT * FROM strategies WHERE id=?", (sid,))
    if not r:
        return None
    r["params"] = json.loads(r["params"] or "{}")
    r["exec"] = json.loads(r["exec"] or "{}")
    return r


def instance(r) -> StrategyBase:
    load_plugins()
    cls = TYPES.get(r["type"])
    if not cls:
        raise KeyError(f"Unknown strategy type '{r['type']}' (missing module in app/strategies/?)")
    return cls(r)


def all_instances(include_archived=False):
    out = []
    for r in rows(include_archived):
        try:
            out.append(instance(r))
        except Exception as e:  # a broken plugin must not stop the others
            db.add_event("error", "strategy", f"Cannot load {r['id']}", str(e), strategy=r["id"])
    return out


def get(sid) -> StrategyBase | None:
    r = row(sid)
    return instance(r) if r else None


def types_public():
    load_plugins()
    return [{"type": t, "label": c.label, "family": c.family, "timeframe": c.timeframe, "description": c.description,
             "params": c.PARAMS, "exec_defaults": c.EXEC_DEFAULTS} for t, c in TYPES.items()]


def new_id(name: str) -> str:
    base = "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_")[:24] or "strategy"
    sid, k = base, 2
    while db.one("SELECT id FROM strategies WHERE id=?", (sid,)):
        sid, k = f"{base}_{k}", k + 1
    return sid


def create(typ: str, name: str, color: str | None, params: dict, exec_: dict | None = None) -> str:
    load_plugins()
    cls = TYPES.get(typ)
    if not cls:
        raise ValueError("Unknown strategy type")
    if not name.strip():
        raise ValueError("Give the strategy a name")
    clean = cls.merge_params(params)
    sid = new_id(name)
    n = db.one("SELECT COUNT(*) n FROM strategies")["n"]
    now = int(time.time())
    db.run("INSERT INTO strategies(id,type,name,color,params,exec,control,line_on,archived,sort,created_at,updated_at) "
           "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
           (sid, typ, name.strip(), color or PALETTE[n % len(PALETTE)], json.dumps(clean), json.dumps(exec_ or {}), "active", 1, 0, n,
            now, now))
    return sid


def update(sid: str, **kw):
    r = row(sid)
    if not r:
        raise KeyError(sid)
    sets, args = [], []
    for k in ("name", "color", "control", "line_on", "archived", "sort"):
        if k in kw and kw[k] is not None:
            sets.append(f"{k}=?")
            args.append(kw[k])
    if kw.get("params") is not None:
        cls = TYPES[r["type"]]
        sets.append("params=?")
        args.append(json.dumps(cls.merge_params({**r["params"], **kw["params"]})))
    if kw.get("exec") is not None:
        sets.append("exec=?")
        args.append(json.dumps(kw["exec"]))
    if not sets:
        return
    sets.append("updated_at=?")
    args.append(int(time.time()))
    db.run(f"UPDATE strategies SET {', '.join(sets)} WHERE id=?", (*args, sid))

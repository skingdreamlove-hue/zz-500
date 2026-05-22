from flask import Flask, jsonify, send_from_directory, abort, request
from flask_cors import CORS
import requests
import re
import time
import os
import csv
import datetime
import subprocess
import json as _json
import shutil
import sys

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

TENCENT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://gu.qq.com/',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
}

SINA_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://finance.sina.com.cn/',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
}

EASTMONEY_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://data.eastmoney.com/',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
}

EASTMONEY_QUOTE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://quote.eastmoney.com/',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _is_trading_hours():
    now = datetime.datetime.now()
    weekday = now.weekday()
    if weekday >= 5:
        return False
    t = now.time()
    morning = datetime.time(9, 30) <= t <= datetime.time(11, 30)
    afternoon = datetime.time(13, 0) <= t <= datetime.time(15, 0)
    return morning or afternoon

def _is_market_closed_today():
    now = datetime.datetime.now()
    weekday = now.weekday()
    if weekday >= 5:
        return True
    t = now.time()
    return t >= datetime.time(15, 5)

_FETCH_LOG_PATH = os.path.join(BASE_DIR, 'data_fetch_log.json')

def _load_fetch_log():
    if os.path.exists(_FETCH_LOG_PATH):
        try:
            with open(_FETCH_LOG_PATH, encoding='utf-8') as f:
                return _json.load(f)
        except Exception:
            return {}
    return {}

def _save_fetch_log(log):
    try:
        with open(_FETCH_LOG_PATH, 'w', encoding='utf-8') as f:
            _json.dump(log, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[FETCH_LOG] save error: {e}")

def _was_fetched_during_trading(fetch_log, date_str):
    ts = fetch_log.get(date_str, '')
    if not ts:
        return True
    try:
        dt = datetime.datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
        if dt.strftime('%Y-%m-%d') != date_str:
            return False
        t = dt.time()
        return (t >= datetime.time(9, 30) and t <= datetime.time(11, 30)) or \
               (t >= datetime.time(13, 0) and t <= datetime.time(15, 0))
    except ValueError:
        return True

def _backfill_csv_from_eastmoney():
    csv_path = os.path.join(BASE_DIR, 'zz500_full_data.csv')
    if not os.path.exists(csv_path):
        print("[BACKFILL] zz500_full_data.csv not found, creating from EastMoney...")
        try:
            url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
            params = {
                'secid': '1.000905',
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                'klt': '101',
                'fqt': '1',
                'end': '20500101',
                'lmt': '300'
            }
            resp = requests.get(url, headers=EASTMONEY_HEADERS, params=params, timeout=10)
            data = resp.json()
            if not data.get('data') or not data['data'].get('klines'):
                print("[BACKFILL] EastMoney API no data, cannot create CSV")
                return
            klines = data['data']['klines']
            fieldnames = ['date','open','close','high','low','volume','amount']
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for k in klines:
                    parts = k.split(',')
                    writer.writerow({'date': parts[0], 'open': parts[1], 'close': parts[2], 'high': parts[3], 'low': parts[4], 'volume': parts[5], 'amount': parts[6]})
            print(f"[BACKFILL] created zz500_full_data.csv with {len(klines)} rows")
        except Exception as e:
            print(f"[BACKFILL] create error: {e}")
            return

    fetch_log = _load_fetch_log()
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with open(csv_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        existing_rows = {}
        for row in reader:
            d = row.get('date', '').strip()
            if d:
                existing_rows[d] = row

    try:
        url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
        params = {
            'secid': '1.000905',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101',
            'fqt': '1',
            'end': '20500101',
            'lmt': '300'
        }
        resp = requests.get(url, headers=EASTMONEY_HEADERS, params=params, timeout=5)
        data = resp.json()
        if not data.get('data') or not data['data'].get('klines'):
            print("[BACKFILL] eastmoney API no data")
            return

        klines = data['data']['klines']
        new_count = 0
        updated_count = 0
        for k in klines:
            parts = k.split(',')
            date_str = parts[0]
            if date_str not in existing_rows:
                new_row = {fn: '' for fn in fieldnames}
                new_row['date'] = date_str
                new_row['open'] = parts[1]
                new_row['close'] = parts[2]
                new_row['high'] = parts[3]
                new_row['low'] = parts[4]
                new_row['volume'] = parts[5]
                new_row['amount'] = parts[6]
                existing_rows[date_str] = new_row
                fetch_log[date_str] = now_str
                new_count += 1
            else:
                old = existing_rows[date_str]
                old_close = old.get('close', '').strip()
                need_update = False
                if not old_close or not old.get('open', '').strip():
                    need_update = True
                elif _was_fetched_during_trading(fetch_log, date_str):
                    need_update = True
                if not need_update:
                    continue
                old['open'] = parts[1]
                old['close'] = parts[2]
                old['high'] = parts[3]
                old['low'] = parts[4]
                old['volume'] = parts[5]
                old['amount'] = parts[6]
                fetch_log[date_str] = now_str
                updated_count += 1

        if new_count == 0 and updated_count == 0:
            print("[BACKFILL] CSV already up-to-date")
            _save_fetch_log(fetch_log)
            return

        sorted_dates = sorted(existing_rows.keys())
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for d in sorted_dates:
                writer.writerow(existing_rows[d])

        _save_fetch_log(fetch_log)
        print(f"[BACKFILL] merged {new_count} new, updated {updated_count} intraday rows, total {len(sorted_dates)} rows")
    except Exception as e:
        print(f"[BACKFILL] error: {e}")

def _regenerate_factors_csv():
    full_path = os.path.join(BASE_DIR, 'zz500_full_data.csv')
    factors_path = os.path.join(BASE_DIR, 'zz500_factors.csv')
    if not os.path.exists(full_path):
        print("[REGEN] zz500_full_data.csv not found, skip")
        return

    with open(full_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if len(rows) < 60:
        print("[REGEN] not enough data rows")
        return

    closes = []
    volumes = []
    for row in rows:
        try:
            c = float(row.get('close', ''))
            closes.append(c)
        except (ValueError, TypeError):
            closes.append(None)
        try:
            v = float(row.get('volume', ''))
            volumes.append(v)
        except (ValueError, TypeError):
            volumes.append(None)

    hs300_closes = []
    try:
        url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
        params = {
            'secid': '1.000300',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101', 'fqt': '1', 'end': '20500101', 'lmt': '3000'
        }
        resp = requests.get(url, headers=EASTMONEY_QUOTE_HEADERS, params=params, timeout=5)
        data = resp.json()
        if data.get('data') and data['data'].get('klines'):
            for k in data['data']['klines']:
                hs300_closes.append(float(k.split(',')[2]))
            print(f"[REGEN] fetched {len(hs300_closes)} hs300 klines")
    except Exception as e:
        print(f"[REGEN] hs300 fetch error: {e}")

    hs300_date_map = {}
    try:
        url2 = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
        params2 = {
            'secid': '1.000300',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101', 'fqt': '1', 'end': '20500101', 'lmt': '3000'
        }
        resp2 = requests.get(url2, headers=EASTMONEY_QUOTE_HEADERS, params=params2, timeout=5)
        data2 = resp2.json()
        if data2.get('data') and data2['data'].get('klines'):
            for k in data2['data']['klines']:
                parts = k.split(',')
                hs300_date_map[parts[0]] = float(parts[2])
    except Exception as e:
        print(f"[REGEN] hs300 date map error: {e}")

    if not hs300_date_map:
        print("[REGEN] eastmoney hs300 failed, trying tencent API...")
        try:
            t_url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
            t_params = {'param': 'sh000300,day,,,2000,qfq'}
            t_resp = requests.get(t_url, headers=TENCENT_HEADERS, params=t_params, timeout=15)
            t_data = t_resp.json()
            t_data_val = t_data.get('data', {})
            if isinstance(t_data_val, dict):
                t_sh300 = t_data_val.get('sh000300', {})
                if isinstance(t_sh300, dict):
                    klines = t_sh300.get('day', []) or t_sh300.get('qfqday', [])
                    for k in klines:
                        hs300_date_map[k[0]] = float(k[2])
            print(f"[REGEN] tencent hs300 fetched {len(hs300_date_map)} entries")
        except Exception as e2:
            print(f"[REGEN] tencent hs300 also failed: {e2}")

    fieldnames = ['date','open','close','high','low','volume','hs300_close',
                  'zz500_MA20','vol_MA5','vol_MA60','is_volume_surge',
                  'hs300_MA20','is_hs300_strong','ATR_14','ATR_percentile']

    is_intraday = _is_trading_hours()
    output_rows = []

    for i, row in enumerate(rows):
        date_str = row.get('date', '').strip()
        if not date_str:
            continue

        c = closes[i]
        if c is None:
            continue

        out = {fn: '' for fn in fieldnames}
        out['date'] = date_str
        out['open'] = row.get('open', '')
        out['close'] = str(c)
        out['high'] = row.get('high', '')
        out['low'] = row.get('low', '')
        out['volume'] = row.get('volume', '')

        if is_intraday and i == len(rows) - 1:
            out['open'] = ''
            out['close'] = ''
            out['high'] = ''
            out['low'] = ''
            out['volume'] = ''

        if date_str in hs300_date_map:
            out['hs300_close'] = str(hs300_date_map[date_str])

        if i >= 19 and all(closes[i-j] is not None for j in range(20)):
            ma20 = sum(closes[i-19:i+1]) / 20
            out['zz500_MA20'] = str(round(ma20, 4))

        valid_vols = [v for v in volumes[max(0,i-4):i+1] if v is not None]
        if len(valid_vols) >= 3:
            out['vol_MA5'] = str(round(sum(valid_vols) / len(valid_vols), 1))

        valid_vols60 = [v for v in volumes[max(0,i-59):i+1] if v is not None]
        if len(valid_vols60) >= 30:
            vol_ma60 = sum(valid_vols60) / len(valid_vols60)
            out['vol_MA60'] = str(round(vol_ma60, 1))
            if len(valid_vols) >= 3 and vol_ma60 > 0:
                vol_ma5 = sum(valid_vols) / len(valid_vols)
                out['is_volume_surge'] = str(vol_ma5 > vol_ma60 * 1.5)

        if i >= 19 and date_str in hs300_date_map:
            hs300_vals = []
            for j in range(20):
                d_prev = rows[i-j].get('date', '').strip()
                if d_prev in hs300_date_map:
                    hs300_vals.append(hs300_date_map[d_prev])
            if len(hs300_vals) >= 15:
                hs300_ma20 = sum(hs300_vals) / len(hs300_vals)
                out['hs300_MA20'] = str(round(hs300_ma20, 4))
                out['is_hs300_strong'] = str(hs300_date_map[date_str] > hs300_ma20)

        if i >= 13 and all(closes[i-j] is not None for j in range(14)):
            trs = []
            for j in range(1, 14):
                h = closes[i-j] if rows[i-j].get('high') else closes[i-j]
                l_val = closes[i-j] if not rows[i-j].get('low') else closes[i-j]
                try:
                    hi = float(rows[i-j].get('high', '')) if rows[i-j].get('high', '').strip() else closes[i-j]
                    lo = float(rows[i-j].get('low', '')) if rows[i-j].get('low', '').strip() else closes[i-j]
                    pc = closes[i-j-1] if closes[i-j-1] is not None else closes[i-j]
                    tr = max(hi, pc) - min(lo, pc)
                    trs.append(tr)
                except (ValueError, TypeError):
                    continue
            if trs:
                atr14 = sum(trs) / len(trs)
                out['ATR_14'] = str(round(atr14, 4))
                if c > 0:
                    atr_pct = atr14 / c * 100
                    all_atr_pcts = []
                    for k in range(14, min(i+1, 252)):
                        try:
                            if all(closes[k-m] is not None for m in range(15)):
                                inner_trs = []
                                for m in range(1, 14):
                                    hi2 = float(rows[k-m].get('high','')) if rows[k-m].get('high','').strip() else closes[k-m]
                                    lo2 = float(rows[k-m].get('low','')) if rows[k-m].get('low','').strip() else closes[k-m]
                                    pc2 = closes[k-m-1] if closes[k-m-1] is not None else closes[k-m]
                                    inner_trs.append(max(hi2, pc2) - min(lo2, pc2))
                                if inner_trs:
                                    a2 = sum(inner_trs) / len(inner_trs)
                                    if closes[k] > 0:
                                        all_atr_pcts.append(a2 / closes[k] * 100)
                        except (ValueError, TypeError):
                            continue
                    if all_atr_pcts:
                        rank = sum(1 for p in all_atr_pcts if p < atr_pct)
                        out['ATR_percentile'] = str(round(rank / len(all_atr_pcts) * 100, 2))

        output_rows.append(out)

    with open(factors_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"[REGEN] regenerated zz500_factors.csv with {len(output_rows)} rows, latest={output_rows[-1]['date'] if output_rows else 'N/A'}")

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    if '..' in filename or filename.startswith('/'):
        abort(404)
    blocked_exts = ('.py', '.vbs', '.bat', '.env', '.json', '.log')
    blocked_files = ('.server_port', 'vibe-trading.env', 'package.json', 'package-lock.json')
    ext = os.path.splitext(filename)[1].lower()
    if ext in blocked_exts or filename.lower() in blocked_files:
        abort(404)
    return send_from_directory(BASE_DIR, filename)

def _get_zz500_price_and_turnover():
    try:
        url = 'https://qt.gtimg.cn/q=sh000905'
        resp = requests.get(url, headers=TENCENT_HEADERS, timeout=10)
        resp.encoding = 'gbk'
        match = re.search(r'"([^"]+)"', resp.text)
        if match:
            parts = match.group(1).split('~')
            price = float(parts[3]) if len(parts) >= 4 else None
            turnover = float(parts[38]) if len(parts) > 38 and parts[38] else 0
            return price, turnover
    except Exception as e:
        print(f"[ZZ500] {e}")
    return None, 0

def _get_hs300():
    if not _is_eastmoney_available():
        return {'success': False}
    try:
        url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
        params = {
            'secid': '1.000300',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101',
            'fqt': '1',
            'end': '20500101',
            'lmt': '60'
        }
        resp = requests.get(url, headers=EASTMONEY_QUOTE_HEADERS, params=params, timeout=5)
        data = resp.json()
        if data and data.get('data') and data['data'].get('klines'):
            klines = data['data']['klines']
            closes = [float(k.split(',')[2]) for k in klines]
            current_price = closes[-1]

            is_intraday = _is_trading_hours()
            indicator_closes = closes[:-1] if is_intraday and len(closes) > 20 else closes

            ma20 = sum(indicator_closes[-20:]) / min(20, len(indicator_closes)) if len(indicator_closes) >= 20 else sum(indicator_closes) / len(indicator_closes)
            macro_strong = current_price > ma20
            return {
                'success': True,
                'current_price': round(current_price, 2),
                'ma20': round(ma20, 2),
                'macro_strong': macro_strong,
                'is_intraday': is_intraday
            }
        return {'success': False}
    except Exception as e:
        print(f"[HS300] {e}")
        _mark_eastmoney_failed()
        return {'success': False}


_EASTMONEY_FAIL_UNTIL = 0

def _is_eastmoney_available():
    return time.time() > _EASTMONEY_FAIL_UNTIL

def _mark_eastmoney_failed():
    global _EASTMONEY_FAIL_UNTIL
    _EASTMONEY_FAIL_UNTIL = time.time() + 300

def _get_kline_from_eastmoney():
    if not _is_eastmoney_available():
        return None, None
    try:
        url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
        params = {
            'secid': '1.000905',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101',
            'fqt': '1',
            'lmt': '300',
            'end': '20500101'
        }
        resp = requests.get(url, headers=EASTMONEY_HEADERS, params=params, timeout=5)
        print(f"[KLINE_EM] status={resp.status_code} len={len(resp.text)}", flush=True)
        data = resp.json()
        if data.get('data') and data['data'].get('klines'):
            klines = data['data']['klines']
            closes = [float(k.split(',')[2]) for k in klines]
            volumes = [float(k.split(',')[5]) for k in klines]
            print(f"[KLINE_EM] 获取{len(closes)}条K线, 最新价={closes[-1]}", flush=True)
            return closes, volumes
        else:
            print(f"[KLINE_EM] 无数据: rc={data.get('rc')} total={data.get('data',{}).get('total') if data.get('data') else 'N/A'}", flush=True)
    except Exception as e:
        print(f"[KLINE_EM] 异常: {e}", flush=True)
        _mark_eastmoney_failed()
    return None, None

def _get_kline_data(current_price):
    try:
        em_closes, em_volumes = _get_kline_from_eastmoney()
        print(f"[KLINE_DATA] em_closes={'YES' if em_closes else 'NO'} len={len(em_closes) if em_closes else 0}", file=sys.stderr, flush=True)
        if em_closes and len(em_closes) >= 250:
            closes = list(em_closes)
            volumes = list(em_volumes)
        else:
            csv_path = os.path.join(BASE_DIR, 'zz500_full_data.csv')
            if not os.path.exists(csv_path):
                csv_path = os.path.join(BASE_DIR, 'zz500_hist.csv')
            closes = []
            volumes = []
            with open(csv_path, encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        c = float(row['close'])
                        closes.append(c)
                        if row.get('volume'):
                            volumes.append(float(row['volume']))
                    except (ValueError, KeyError):
                        continue
            print(f"[KLINE_CSV] 从{os.path.basename(csv_path)}加载{len(closes)}条, 最新价={closes[-1] if closes else 0}")

        if len(closes) < 250:
            return None

        is_intraday = _is_trading_hours()
        indicator_closes = closes[:-1] if is_intraday else closes
        indicator_volumes = volumes[:-1] if is_intraday else volumes

        if current_price is None:
            current_price = closes[-1]

        n250 = min(250, len(indicator_closes))
        n200 = min(200, len(indicator_closes))
        n60 = min(60, len(indicator_closes))
        n20 = min(20, len(indicator_closes))
        n60_prev = min(60, max(1, len(indicator_closes) - 1))

        ma250 = round(sum(indicator_closes[-n250:]) / n250, 2) if n250 > 0 else 0
        ma200 = round(sum(indicator_closes[-n200:]) / n200, 2) if n200 > 0 else 0
        ma60 = round(sum(indicator_closes[-n60:]) / n60, 2) if n60 > 0 else 0
        ma20 = round(sum(indicator_closes[-n20:]) / n20, 2) if n20 > 0 else 0
        ma60_prev = round(sum(indicator_closes[-n60_prev-1:-1]) / n60_prev, 2) if n60_prev > 0 and len(indicator_closes) > n60_prev else ma60

        prev_19_sum = sum(indicator_closes[-19:]) if len(indicator_closes) >= 19 else 0

        if ma60 > ma60_prev * 1.005:
            ma60_trend = '向上'
        elif ma60 < ma60_prev * 0.995:
            ma60_trend = '向下'
        else:
            ma60_trend = '横盘'

        turnover_percentile = 50.0
        if len(indicator_volumes) >= 60:
            vol_60d = indicator_volumes[-60:]
            current_vol = indicator_volumes[-1]
            rank = sum(1 for v in vol_60d if v < current_vol)
            turnover_percentile = round(rank / len(vol_60d) * 100, 1)

        vol_surge = False
        if len(indicator_volumes) >= 65:
            vol_ma5 = sum(indicator_volumes[-5:]) / 5
            vol_ma60 = sum(indicator_volumes[-60:]) / 60
            if vol_ma60 > 0 and vol_ma5 > vol_ma60 * 1.5:
                vol_surge = True
        elif len(indicator_volumes) >= 25:
            vol_ma5 = sum(indicator_volumes[-5:]) / 5
            vol_ma20 = sum(indicator_volumes[-20:]) / 20
            if vol_ma20 > 0 and vol_ma5 > vol_ma20 * 1.5:
                vol_surge = True

        return {
            'current_price': current_price,
            'ma250': ma250,
            'ma200': ma200,
            'ma60': ma60,
            'ma20': ma20,
            'ma60_trend': ma60_trend,
            'deviation': round(((current_price - ma250) / ma250) * 100, 2),
            'turnover_percentile': turnover_percentile,
            'vol_surge': vol_surge,
            'is_intraday': is_intraday,
            'prev_19_sum': round(prev_19_sum, 4)
        }
    except Exception as e:
        print(f"[KLINE] {e}")
    return None

@app.route('/api/strategy_b')
def get_strategy_b():
    import concurrent.futures
    _t0 = time.time()
    print("[STRATEGY_B] 开始请求", file=sys.stderr, flush=True)
    result = {'success': True}

    is_intraday = _is_trading_hours()
    market_closed = _is_market_closed_today()
    result['is_trading_hours'] = is_intraday
    if is_intraday:
        result['data_status'] = 'intraday'
    elif market_closed:
        result['data_status'] = 'closed'
    else:
        result['data_status'] = 'non_trading'

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        kline_future = executor.submit(_get_kline_data, None)
        price_future = executor.submit(_get_zz500_price_and_turnover)
        hs300_future = executor.submit(_get_hs300)

        kline_data = kline_future.result()
        rt_price, _ = price_future.result()
        hs300_data = hs300_future.result()

    _t1 = time.time()
    print(f"[STRATEGY_B] 并行获取耗时: {_t1-_t0:.2f}s", file=sys.stderr, flush=True)

    if kline_data and rt_price:
        kline_data['current_price'] = rt_price
    result['kline'] = {'success': kline_data is not None, **(kline_data or {})}

    if not hs300_data.get('success'):
        try:
            import csv as _csv
            csv_path = os.path.join(BASE_DIR, 'zz500_factors.csv')
            with open(csv_path, encoding='utf-8-sig') as _f:
                _rows = list(_csv.DictReader(_f))
            if _rows:
                _last = _rows[-1]
                _hs300_close = float(_last.get('hs300_close', 0))
                _hs300_ma20 = float(_last.get('hs300_MA20', 0))
                if _hs300_close > 0 and _hs300_ma20 > 0:
                    hs300_data = {
                        'success': True,
                        'current_price': _hs300_close,
                        'ma20': _hs300_ma20,
                        'macro_strong': _hs300_close > _hs300_ma20,
                        'is_intraday': False,
                        'fallback': True
                    }
                    print(f"[HS300_FALLBACK] 实时获取失败，回退CSV: close={_hs300_close} ma20={_hs300_ma20}")
        except Exception as _e:
            print(f"[HS300_FALLBACK] CSV回退失败: {_e}")
    result['hs300'] = hs300_data

    _t2 = time.time()
    print(f"[STRATEGY_B] 总耗时: {_t2-_t0:.2f}s kline_price={kline_data.get('current_price') if kline_data else None} hs300={hs300_data.get('current_price') if hs300_data else None} intraday={is_intraday}", file=sys.stderr, flush=True)

    return jsonify(result)


@app.route('/api/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': time.time()})

@app.route('/api/refresh-csv')
def refresh_csv():
    try:
        _backfill_csv_from_eastmoney()
        _regenerate_factors_csv()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def _find_python():
    hardcoded = r'C:\Users\MY\AppData\Local\Programs\Python\Python313\python.exe'
    if os.path.exists(hardcoded):
        return hardcoded
    found = shutil.which('python')
    if found:
        return found
    return 'python'

PYTHON_EXE = _find_python()
VIBE_WRAPPER = os.path.join(BASE_DIR, 'vibe_wrapper.py')
VIBE_DATA_DIR = os.path.join(BASE_DIR, 'vibe-data')
VIBE_MODELS = ['gemini-2.5-flash', 'gemini-3-flash']

class VibeRateLimiter:
    RPM = 5
    RPD = 20

    def __init__(self):
        self._minute_calls = {}
        self._day_calls = {}

    def _clean_minute(self, model, now):
        cutoff = now - 60
        self._minute_calls[model] = [t for t in self._minute_calls.get(model, []) if t > cutoff]

    def can_call(self, model):
        now = time.time()
        self._clean_minute(model, now)
        if len(self._minute_calls.get(model, [])) >= self.RPM:
            return False
        today = datetime.date.today().isoformat()
        if self._day_calls.get(model, {}).get(today, 0) >= self.RPD:
            return False
        return True

    def record_call(self, model, count=1):
        now = time.time()
        self._minute_calls.setdefault(model, []).append(now)
        self._clean_minute(model, now)
        today = datetime.date.today().isoformat()
        self._day_calls.setdefault(model, {}).setdefault(today, 0)
        self._day_calls[model][today] += count

    def pick_model(self):
        for m in VIBE_MODELS:
            if self.can_call(m):
                return m
        return None

    def wait_seconds(self):
        now = time.time()
        best = float('inf')
        for m in VIBE_MODELS:
            calls = self._minute_calls.get(m, [])
            if calls and len(calls) >= self.RPM:
                wait = max(0, 60 - (now - calls[0]) + 0.5)
                best = min(best, wait)
        return best if best < float('inf') else 0

    def quota(self):
        result = []
        today = datetime.date.today().isoformat()
        for m in VIBE_MODELS:
            self._clean_minute(m, time.time())
            rpm_used = len(self._minute_calls.get(m, []))
            rpd_used = self._day_calls.get(m, {}).get(today, 0)
            result.append({
                'model': m,
                'rpm_remaining': max(0, self.RPM - rpm_used),
                'rpd_remaining': max(0, self.RPD - rpd_used),
            })
        return result

vibe_limiter = VibeRateLimiter()

def _detect_proxy():
    if os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY'):
        return
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Internet Settings')
        proxy_server, _ = winreg.QueryValueEx(key, 'ProxyServer')
        winreg.CloseKey(key)
        if proxy_server and proxy_server.strip():
            proxy_addr = proxy_server.strip()
            if not proxy_addr.startswith('http'):
                proxy_addr = 'http://' + proxy_addr
            os.environ['VIBE_PROXY_ADDR'] = proxy_addr
    except Exception:
        pass

_detect_proxy()

def _run_vibe(prompt, max_iter=30, timeout=300):
    model = vibe_limiter.pick_model()
    if not model:
        wait = vibe_limiter.wait_seconds()
        return {'status': 'failed', 'reason': f'所有模型已达速率限制，请等待{wait:.0f}秒后重试'}

    estimated_calls = min(max_iter, 10)
    vibe_limiter.record_call(model, count=estimated_calls)

    env = os.environ.copy()
    env['LANGCHAIN_MODEL_NAME'] = model
    env['LANGCHAIN_FALLBACK_MODEL_NAME'] = 'gemini-3-flash' if model == 'gemini-2.5-flash' else 'gemini-2.5-flash'
    vibe_proxy = os.environ.get('VIBE_PROXY_ADDR', '')
    if vibe_proxy:
        env['HTTPS_PROXY'] = vibe_proxy
        env['HTTP_PROXY'] = vibe_proxy

    try:
        cmd = [PYTHON_EXE, VIBE_WRAPPER, 'run', '-p', prompt, '--json', '--no-rich', '--max-iter', str(max_iter)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=BASE_DIR, env=env)
        stdout = result.stdout.strip()
        if stdout:
            try:
                return _json.loads(stdout)
            except _json.JSONDecodeError:
                pass
        if result.returncode != 0:
            err = result.stderr.strip()[-500:] if result.stderr else 'unknown error'
            return {'status': 'failed', 'reason': err}
        return {'status': 'failed', 'reason': 'no output'}
    except subprocess.TimeoutExpired:
        return {'status': 'failed', 'reason': f'timeout after {timeout}s'}
    except Exception as e:
        return {'status': 'failed', 'reason': str(e)}

def _read_run_result(run_id):
    run_dir = os.path.join(VIBE_DATA_DIR, 'runs', run_id)
    if not os.path.isdir(run_dir):
        return None
    state_path = os.path.join(run_dir, 'state.json')
    if os.path.exists(state_path):
        with open(state_path, encoding='utf-8') as f:
            return _json.load(f)
    return None

def _read_run_trace(run_id):
    run_dir = os.path.join(VIBE_DATA_DIR, 'runs', run_id)
    trace_path = os.path.join(run_dir, 'trace.jsonl')
    if not os.path.exists(trace_path):
        return []
    entries = []
    with open(trace_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(_json.loads(line))
                except _json.JSONDecodeError:
                    pass
    return entries

def _read_run_artifacts(run_id):
    run_dir = os.path.join(VIBE_DATA_DIR, 'runs', run_id)
    artifacts_dir = os.path.join(run_dir, 'artifacts')
    if not os.path.isdir(artifacts_dir):
        return {}
    artifacts = {}
    for fname in os.listdir(artifacts_dir):
        fpath = os.path.join(artifacts_dir, fname)
        if fname.endswith('.csv'):
            with open(fpath, encoding='utf-8-sig') as f:
                artifacts[fname] = f.read()
        elif fname.endswith('.json'):
            with open(fpath, encoding='utf-8') as f:
                artifacts[fname] = _json.load(f)
        else:
            with open(fpath, encoding='utf-8', errors='replace') as f:
                artifacts[fname] = f.read()
    return artifacts

def _read_run_code(run_id):
    run_dir = os.path.join(VIBE_DATA_DIR, 'runs', run_id)
    code_dir = os.path.join(run_dir, 'code')
    if not os.path.isdir(code_dir):
        return {}
    code = {}
    for fname in os.listdir(code_dir):
        fpath = os.path.join(code_dir, fname)
        if fname.endswith('.py') or fname.endswith('.json'):
            with open(fpath, encoding='utf-8') as f:
                code[fname] = f.read()
    return code

@app.route('/api/ai-analysis', methods=['POST'])
def ai_analysis():
    data = request.get_json(silent=True) or {}
    prompt = data.get('prompt', '').strip()
    max_iter = data.get('max_iter', 30)
    if not prompt:
        return jsonify({'success': False, 'error': 'prompt is required'})

    result = _run_vibe(prompt, max_iter=max_iter)
    if result.get('status') == 'success':
        run_id = result.get('run_id', '')
        answer = ''
        trace = _read_run_trace(run_id)
        for entry in reversed(trace):
            if entry.get('type') == 'answer' and entry.get('content'):
                answer = entry['content']
                break
        if not answer:
            state = _read_run_result(run_id)
            if state:
                answer = state.get('result', {}).get('content', '')
        if not answer:
            answer = 'Vibe-Trading执行完成，但未返回文本内容。'
        return jsonify({
            'success': True,
            'answer': answer,
            'run_id': run_id,
            'run_dir': result.get('run_dir', '')
        })
    else:
        return jsonify({'success': False, 'error': result.get('reason', 'unknown error')})

@app.route('/api/vibe/strategy', methods=['POST'])
def vibe_strategy():
    data = request.get_json(silent=True) or {}
    description = data.get('description', '').strip()
    codes = data.get('codes', ['000905.SH'])
    start_date = data.get('start_date', '')
    end_date = data.get('end_date', '')
    if not description:
        return jsonify({'success': False, 'error': 'description is required'})

    prompt = f'请使用 strategy-generate 技能，为以下策略需求生成量化策略并回测：\n\n策略描述：{description}\n标的代码：{", ".join(codes)}'
    if start_date:
        prompt += f'\n起始日期：{start_date}'
    if end_date:
        prompt += f'\n结束日期：{end_date}'
    prompt += '\n\n请严格按照 strategy-generate 技能的流程：1)解析需求写config.json 2)设计策略 3)编写signal_engine.py 4)语法检查 5)运行回测 6)评估结果。务必运行backtest工具获取真实回测数据，不要编造数字。'

    result = _run_vibe(prompt, max_iter=50, timeout=600)
    if result.get('status') == 'success':
        run_id = result.get('run_id', '')
        state = _read_run_result(run_id)
        trace = _read_run_trace(run_id)
        answer = ''
        for entry in reversed(trace):
            if entry.get('type') == 'answer' and entry.get('content'):
                answer = entry['content']
                break
        artifacts = _read_run_artifacts(run_id)
        code = _read_run_code(run_id)
        metrics_csv = artifacts.get('metrics.csv', '')
        equity_csv = artifacts.get('equity.csv', '')
        return jsonify({
            'success': True,
            'run_id': run_id,
            'answer': answer or '策略回测完成',
            'metrics': metrics_csv,
            'equity': equity_csv,
            'code': code,
            'artifacts': list(artifacts.keys())
        })
    else:
        return jsonify({'success': False, 'error': result.get('reason', 'unknown error')})

@app.route('/api/vibe/swarm', methods=['POST'])
def vibe_swarm():
    data = request.get_json(silent=True) or {}
    preset = data.get('preset', '').strip()
    variables = data.get('variables', {})
    if not preset:
        return jsonify({'success': False, 'error': 'preset is required'})

    try:
        vars_json = _json.dumps(variables, ensure_ascii=False) if variables else '{}'
        cmd = [PYTHON_EXE, VIBE_WRAPPER, '--swarm-run', preset, vars_json]
        env = os.environ.copy()
        vibe_proxy = os.environ.get('VIBE_PROXY_ADDR', '')
        if vibe_proxy:
            env['HTTPS_PROXY'] = vibe_proxy
            env['HTTP_PROXY'] = vibe_proxy
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=BASE_DIR, env=env)
        output = result.stdout.strip()
        if result.returncode != 0:
            err = result.stderr.strip()[-500:] if result.stderr else 'unknown error'
            return jsonify({'success': False, 'error': err})
        return jsonify({'success': True, 'output': output[-3000:]})
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'timeout after 900s'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vibe/skills')
def vibe_skills():
    try:
        cmd = [PYTHON_EXE, VIBE_WRAPPER, '--skills']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=BASE_DIR)
        if result.stdout is None:
            return jsonify({'success': False, 'error': 'subprocess returned None stdout'})
        return jsonify({'success': True, 'output': result.stdout.strip()[-5000:]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vibe/swarm-presets')
def vibe_swarm_presets():
    try:
        cmd = [PYTHON_EXE, VIBE_WRAPPER, '--swarm-presets']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=BASE_DIR)
        return jsonify({'success': True, 'output': result.stdout.strip()[-5000:]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vibe/runs')
def vibe_runs():
    try:
        cmd = [PYTHON_EXE, VIBE_WRAPPER, 'list']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=BASE_DIR)
        return jsonify({'success': True, 'output': result.stdout.strip()[-5000:]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vibe/run/<run_id>')
def vibe_run_detail(run_id):
    state = _read_run_result(run_id)
    if state is None:
        return jsonify({'success': False, 'error': 'run not found'})
    trace = _read_run_trace(run_id)
    artifacts = _read_run_artifacts(run_id)
    code = _read_run_code(run_id)
    return jsonify({
        'success': True,
        'state': state,
        'trace': trace,
        'artifacts': artifacts,
        'code': code
    })

@app.route('/api/vibe/quota')
def vibe_quota():
    return jsonify({'success': True, 'models': vibe_limiter.quota()})

if __name__ == '__main__':
    import socket
    import logging
    import threading
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    def _background_init():
        try:
            print("[INIT] Backfilling CSV from EastMoney (background)...")
            _backfill_csv_from_eastmoney()
            print("[INIT] Regenerating factors CSV (background)...")
            _regenerate_factors_csv()
        except Exception as e:
            print(f"[INIT] background init error: {e}")

    threading.Thread(target=_background_init, daemon=True).start()

    def is_port_available(port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return True
        except:
            return False

    base_port = 5001
    current_port = base_port
    max_port = 5010

    while current_port <= max_port:
        if not is_port_available(current_port):
            print(f"[WARN] port {current_port} in use")
            current_port += 1
            continue
        port_file = os.path.join(BASE_DIR, '.server_port')
        with open(port_file, 'w') as f:
            f.write(str(current_port))
        print(f"[OK] port {current_port}")
        print(f"[INFO] http://localhost:{current_port}")
        try:
            app.run(host='0.0.0.0', port=current_port, debug=False, threaded=True)
            break
        except OSError:
            print(f"[WARN] port {current_port} taken between check and bind, retrying...")
            current_port += 1
    else:
        print(f"[ERROR] no available port in {base_port}-{max_port}")

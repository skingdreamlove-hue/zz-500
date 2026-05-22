import requests
import csv
import os
import datetime
import json
import sys
import time

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

EASTMONEY_HEADERS = {**BROWSER_HEADERS, 'Referer': 'https://data.eastmoney.com/'}
EASTMONEY_QUOTE_HEADERS = {**BROWSER_HEADERS, 'Referer': 'https://quote.eastmoney.com/'}
TENCENT_HEADERS = {**BROWSER_HEADERS, 'Referer': 'https://gu.qq.com/'}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_session = None

def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(BROWSER_HEADERS)
    return _session


def fetch_zz500_klines(lmt=300):
    for attempt in range(3):
        try:
            url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
            params = {
                'secid': '1.000905',
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                'klt': '101', 'fqt': '1', 'end': '20500101', 'lmt': str(lmt)
            }
            resp = _get_session().get(url, headers=EASTMONEY_HEADERS, params=params, timeout=15)
            data = resp.json()
            if data.get('data') and data['data'].get('klines'):
                return data['data']['klines']
        except Exception as e:
            print(f"[ZZ500] eastmoney attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(3)

    print("[ZZ500] eastmoney failed, trying tencent...")
    try:
        t_url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        t_params = {'param': 'sh000905,day,,,400,qfq'}
        t_resp = _get_session().get(t_url, headers=TENCENT_HEADERS, params=t_params, timeout=15)
        t_data = t_resp.json()
        t_val = t_data.get('data', {})
        if isinstance(t_val, dict):
            t_sh = t_val.get('sh000905', {})
            if isinstance(t_sh, dict):
                klines = t_sh.get('qfqday', []) or t_sh.get('day', [])
                result = []
                for k in klines[-lmt:]:
                    result.append(f"{k[0]},{k[1]},{k[2]},{k[3]},{k[4]},{k[5]},0")
                if result:
                    print(f"[ZZ500] tencent fallback got {len(result)} klines")
                    return result
    except Exception as e2:
        print(f"[ZZ500] tencent also failed: {e2}")

    return []


def fetch_hs300_klines(lmt=3000):
    for attempt in range(3):
        try:
            url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
            params = {
                'secid': '1.000300',
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                'klt': '101', 'fqt': '1', 'end': '20500101', 'lmt': str(lmt)
            }
            resp = _get_session().get(url, headers=EASTMONEY_QUOTE_HEADERS, params=params, timeout=15)
            data = resp.json()
            if data.get('data') and data['data'].get('klines'):
                return data['data']['klines']
        except Exception as e:
            print(f"[HS300] eastmoney attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(3)

    print("[HS300] eastmoney failed, trying tencent...")
    try:
        t_url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        t_params = {'param': 'sh000300,day,,,2000,qfq'}
        t_resp = _get_session().get(t_url, headers=TENCENT_HEADERS, params=t_params, timeout=15)
        t_data = t_resp.json()
        t_val = t_data.get('data', {})
        if isinstance(t_val, dict):
            t_sh = t_val.get('sh000300', {})
            if isinstance(t_sh, dict):
                klines = t_sh.get('qfqday', []) or t_sh.get('day', [])
                result = [f"{k[0]},{k[1]},{k[2]},{k[3]},{k[4]},{k[5]},0,0,0,0,0" for k in klines]
                if result:
                    print(f"[HS300] tencent fallback got {len(result)} klines")
                    return result
    except Exception as e2:
        print(f"[HS300] tencent also failed: {e2}")
    return []


def build_full_csv(zz500_klines):
    fieldnames = ['date', 'open', 'close', 'high', 'low', 'volume', 'amount']
    rows = []
    for k in zz500_klines:
        parts = k.split(',')
        rows.append({
            'date': parts[0], 'open': parts[1], 'close': parts[2],
            'high': parts[3], 'low': parts[4], 'volume': parts[5], 'amount': parts[6]
        })
    csv_path = os.path.join(BASE_DIR, 'zz500_full_data.csv')
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[FULL_CSV] wrote {len(rows)} rows")
    return rows


def build_factors_csv(rows, hs300_klines):
    hs300_date_map = {}
    for k in hs300_klines:
        parts = k.split(',')
        hs300_date_map[parts[0]] = float(parts[2])

    closes = []
    volumes = []
    for row in rows:
        try:
            closes.append(float(row['close']))
        except (ValueError, TypeError):
            closes.append(None)
        try:
            volumes.append(float(row.get('volume', '')))
        except (ValueError, TypeError):
            volumes.append(None)

    fieldnames = ['date', 'open', 'close', 'high', 'low', 'volume', 'hs300_close',
                  'zz500_MA20', 'vol_MA5', 'vol_MA60', 'is_volume_surge',
                  'hs300_MA20', 'is_hs300_strong', 'ATR_14', 'ATR_percentile']

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

        if date_str in hs300_date_map:
            out['hs300_close'] = str(hs300_date_map[date_str])

        if i >= 19 and all(closes[i - j] is not None for j in range(20)):
            ma20 = sum(closes[i - 19:i + 1]) / 20
            out['zz500_MA20'] = str(round(ma20, 4))

        valid_vols = [v for v in volumes[max(0, i - 4):i + 1] if v is not None]
        if len(valid_vols) >= 3:
            out['vol_MA5'] = str(round(sum(valid_vols) / len(valid_vols), 1))

        valid_vols60 = [v for v in volumes[max(0, i - 59):i + 1] if v is not None]
        if len(valid_vols60) >= 30:
            vol_ma60 = sum(valid_vols60) / len(valid_vols60)
            out['vol_MA60'] = str(round(vol_ma60, 1))
            if len(valid_vols) >= 3 and vol_ma60 > 0:
                vol_ma5 = sum(valid_vols) / len(valid_vols)
                out['is_volume_surge'] = str(vol_ma5 > vol_ma60 * 1.5)

        if i >= 19 and date_str in hs300_date_map:
            hs300_vals = []
            for j in range(20):
                d_prev = rows[i - j].get('date', '').strip()
                if d_prev in hs300_date_map:
                    hs300_vals.append(hs300_date_map[d_prev])
            if len(hs300_vals) >= 15:
                hs300_ma20 = sum(hs300_vals) / len(hs300_vals)
                out['hs300_MA20'] = str(round(hs300_ma20, 4))
                out['is_hs300_strong'] = str(hs300_date_map[date_str] > hs300_ma20)

        if i >= 13 and all(closes[i - j] is not None for j in range(14)):
            trs = []
            for j in range(1, 14):
                try:
                    hi = float(rows[i - j].get('high', '')) if rows[i - j].get('high', '').strip() else closes[i - j]
                    lo = float(rows[i - j].get('low', '')) if rows[i - j].get('low', '').strip() else closes[i - j]
                    pc = closes[i - j - 1] if closes[i - j - 1] is not None else closes[i - j]
                    trs.append(max(hi, pc) - min(lo, pc))
                except (ValueError, TypeError):
                    continue
            if trs:
                atr14 = sum(trs) / len(trs)
                out['ATR_14'] = str(round(atr14, 4))
                if c > 0:
                    atr_pct = atr14 / c * 100
                    all_atr_pcts = []
                    for k in range(14, min(i + 1, 252)):
                        try:
                            if all(closes[k - m] is not None for m in range(15)):
                                inner_trs = []
                                for m in range(1, 14):
                                    hi2 = float(rows[k - m].get('high', '')) if rows[k - m].get('high', '').strip() else closes[k - m]
                                    lo2 = float(rows[k - m].get('low', '')) if rows[k - m].get('low', '').strip() else closes[k - m]
                                    pc2 = closes[k - m - 1] if closes[k - m - 1] is not None else closes[k - m]
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

    factors_path = os.path.join(BASE_DIR, 'zz500_factors.csv')
    with open(factors_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"[FACTORS] wrote {len(output_rows)} rows, latest={output_rows[-1]['date'] if output_rows else 'N/A'}")


def build_signal_json(rows, hs300_klines):
    hs300_date_map = {}
    for k in hs300_klines:
        parts = k.split(',')
        hs300_date_map[parts[0]] = float(parts[2])

    if not rows:
        return

    last = rows[-1]
    close = float(last.get('close', 0))
    ma20 = float(last.get('zz500_MA20', 0)) if last.get('zz500_MA20') else 0
    hs300_close = float(last.get('hs300_close', 0)) if last.get('hs300_close') else 0
    hs300_ma20 = float(last.get('hs300_MA20', 0)) if last.get('hs300_MA20') else 0
    is_hs300_strong = last.get('is_hs300_strong', '') == 'True'
    is_volume_surge = last.get('is_volume_surge', '') == 'True'

    signal = '观望-无效突破'
    if ma20 > 0:
        if close < ma20:
            signal = '清仓-跌破MA20'
        elif close > ma20 * 1.05:
            signal = '满仓-涨破5%'
        elif is_hs300_strong and is_volume_surge:
            signal = '满仓-量价共振'
        elif is_hs300_strong and close >= ma20 * 1.01:
            signal = '满仓-大盘撑腰'
        elif not is_hs300_strong and close >= ma20 * 1.01:
            signal = '底仓-逆市试错'

    signal_data = {
        'date': last.get('date', ''),
        'close': close,
        'ma20': ma20,
        'hs300_close': hs300_close,
        'hs300_ma20': hs300_ma20,
        'is_hs300_strong': is_hs300_strong,
        'is_volume_surge': is_volume_surge,
        'signal': signal,
        'updated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    json_path = os.path.join(BASE_DIR, 'signal.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(signal_data, f, ensure_ascii=False, indent=2)
    print(f"[SIGNAL] {signal} close={close} ma20={ma20}")


def main():
    print("=== 开始抓取数据 ===")
    zz500_klines = fetch_zz500_klines()
    if not zz500_klines:
        print("[ERROR] 无法获取中证500数据")
        sys.exit(1)
    print(f"[ZZ500] fetched {len(zz500_klines)} klines")

    hs300_klines = fetch_hs300_klines()
    print(f"[HS300] fetched {len(hs300_klines)} klines")

    rows = build_full_csv(zz500_klines)
    build_factors_csv(rows, hs300_klines)

    factors_path = os.path.join(BASE_DIR, 'zz500_factors.csv')
    with open(factors_path, encoding='utf-8-sig') as f:
        factor_rows = list(csv.DictReader(f))
    build_signal_json(factor_rows, hs300_klines)

    print("=== 数据抓取完成 ===")


if __name__ == '__main__':
    main()

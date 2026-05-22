window.StrategyCommon = (function () {
    const SIGNALS = [
        { name: '清仓-跌破MA20', position: 0, type: 'defense', color: '#22c55e' },
        { name: '满仓-涨破5%', position: 100, type: 'attack', color: '#ef4444' },
        { name: '满仓-量价共振', position: 100, type: 'attack', color: '#ef4444' },
        { name: '满仓-大盘撑腰', position: 100, type: 'attack', color: '#3b82f6' },
        { name: '底仓-逆市试错', position: 10, type: 'attack', color: '#f97316' },
        { name: '观望-无效突破', position: 0, type: 'defense', color: '#6b7280' }
    ];

    const SIGNAL_MAP = {};
    SIGNALS.forEach(function (s) { SIGNAL_MAP[s.name] = s; });

    var THRESHOLDS = { fwd5: 1.0, fwd10: 2.0, fwd20: 4.0 };
    var WEIGHTS = { fwd5: 0.2, fwd10: 0.3, fwd20: 0.5 };

    function getSignal(row) {
        var close = parseFloat(row.close);
        var ma20 = parseFloat(row.zz500_MA20);
        var isHs300Strong = row.is_hs300_strong === 'True';
        var isVolumeSurge = row.is_volume_surge === 'True';
        if (close < ma20) return SIGNAL_MAP['清仓-跌破MA20'];
        if (close > ma20 * 1.05) return SIGNAL_MAP['满仓-涨破5%'];
        if (isHs300Strong && isVolumeSurge) return SIGNAL_MAP['满仓-量价共振'];
        if (isHs300Strong && close >= ma20 * 1.01) return SIGNAL_MAP['满仓-大盘撑腰'];
        if (!isHs300Strong && close >= ma20 * 1.01) return SIGNAL_MAP['底仓-逆市试错'];
        return SIGNAL_MAP['观望-无效突破'];
    }

    function judge(signalName, fwdReturn, horizon) {
        if (fwdReturn === null) return 'pending';
        var threshold = THRESHOLDS[horizon];
        var isAttack = SIGNAL_MAP[signalName].type === 'attack';
        if (isAttack) {
            if (fwdReturn > threshold) return 'pass';
            if (fwdReturn < -threshold) return 'fail';
            return 'neutral';
        } else {
            if (fwdReturn < -threshold) return 'pass';
            if (fwdReturn > threshold) return 'fail';
            return 'neutral';
        }
    }

    function judgeScore(j) {
        if (j === 'pass') return 1;
        if (j === 'neutral') return 0.5;
        if (j === 'fail') return 0;
        return null;
    }

    function judgeLabel(j) {
        if (j === 'pass') return '✅';
        if (j === 'fail') return '❌';
        if (j === 'neutral') return '➖';
        return '⏳';
    }

    function weightedAccuracy(j5, j10, j20) {
        var s5 = judgeScore(j5);
        var s10 = judgeScore(j10);
        var s20 = judgeScore(j20);
        if (s5 === null || s10 === null || s20 === null) return null;
        return s5 * WEIGHTS.fwd5 + s10 * WEIGHTS.fwd10 + s20 * WEIGHTS.fwd20;
    }

    function processRealData(rawData) {
        var filtered = rawData.filter(function (r) { return r.zz500_MA20 && r.zz500_MA20.trim() !== ''; });
        var data = filtered.map(function (r) { return Object.assign({}, r, { signal: getSignal(r) }); });
        var nav = 1.0, benchNav = 1.0, pos = 0;
        for (var i = 0; i < data.length; i++) {
            var c = parseFloat(data[i].close);
            var pc = i > 0 ? parseFloat(data[i - 1].close) : c;
            var sr = i > 0 ? (c / pc - 1) : 0;
            var dr = pos * sr;
            nav *= (1 + dr);
            benchNav *= (1 + sr);
            pos = data[i].signal.position / 100;
            data[i].nav = nav;
            data[i].benchNav = benchNav;
        }
        for (var i = 0; i < data.length; i++) {
            var c = parseFloat(data[i].close);
            data[i].fwd5 = i + 5 < data.length ? (parseFloat(data[i + 5].close) / c - 1) * 100 : null;
            data[i].fwd10 = i + 10 < data.length ? (parseFloat(data[i + 10].close) / c - 1) * 100 : null;
            data[i].fwd20 = i + 20 < data.length ? (parseFloat(data[i + 20].close) / c - 1) * 100 : null;
            var j5 = judge(data[i].signal.name, data[i].fwd5, 'fwd5');
            var j10 = judge(data[i].signal.name, data[i].fwd10, 'fwd10');
            var j20 = judge(data[i].signal.name, data[i].fwd20, 'fwd20');
            data[i].j5 = j5;
            data[i].j10 = j10;
            data[i].j20 = j20;
            data[i].wa = weightedAccuracy(j5, j10, j20);
        }
        return data;
    }

    function calcKPI(data) {
        var s5Total = 0, s5Count = 0;
        var s10Total = 0, s10Count = 0;
        var s20Total = 0, s20Count = 0;
        var waTotal = 0, waCount = 0;
        var bySignal = {};
        SIGNALS.forEach(function (s) { bySignal[s.name] = { triggers: 0, waSum: 0, waCount: 0 }; });

        data.forEach(function (r) {
            var v5 = judgeScore(r.j5);
            var v10 = judgeScore(r.j10);
            var v20 = judgeScore(r.j20);
            if (v5 !== null) { s5Total += v5; s5Count++; }
            if (v10 !== null) { s10Total += v10; s10Count++; }
            if (v20 !== null) { s20Total += v20; s20Count++; }
            if (r.wa !== null) { waTotal += r.wa; waCount++; }
            bySignal[r.signal.name].triggers++;
            if (r.wa !== null) { bySignal[r.signal.name].waSum += r.wa; bySignal[r.signal.name].waCount++; }
        });

        var acc5 = s5Count > 0 ? (s5Total / s5Count * 100) : 0;
        var acc10 = s10Count > 0 ? (s10Total / s10Count * 100) : 0;
        var acc20 = s20Count > 0 ? (s20Total / s20Count * 100) : 0;
        var accWeighted = waCount > 0 ? (waTotal / waCount * 100) : 0;

        var last = data[data.length - 1];
        var years = data.length / 252;
        var annReturn = (Math.pow(last.nav, 1 / years) - 1) * 100;

        var episodes = [];
        var epName = data[0].signal.name, epLen = 1;
        for (var i = 1; i <= data.length; i++) {
            if (i < data.length && data[i].signal.name === epName) { epLen++; }
            else { episodes.push({ name: epName, len: epLen }); if (i < data.length) { epName = data[i].signal.name; epLen = 1; } }
        }

        var signalStats = SIGNALS.map(function (s) {
            var sigEps = episodes.filter(function (e) { return e.name === s.name; });
            var avgDur = sigEps.length > 0 ? sigEps.reduce(function (a, e) { return a + e.len; }, 0) / sigEps.length : 0;
            var info = bySignal[s.name];
            var avgWa = info.waCount > 0 ? (info.waSum / info.waCount * 100) : null;
            return {
                name: s.name, color: s.color,
                triggers: info.triggers,
                pct: data.length > 0 ? (info.triggers / data.length * 100) : 0,
                avgDur: avgDur,
                avgWa: avgWa
            };
        });

        var waRows = data.filter(function (r) { return r.wa !== null; });
        var recentWaRows = waRows.slice(-20);
        var recentWaAvg = recentWaRows.length > 0 ? (recentWaRows.reduce(function (s, r) { return s + r.wa; }, 0) / recentWaRows.length * 100) : 0;
        var accWeightedTrend = recentWaAvg - accWeighted;

        var annReturnTrend = 0;
        var recentData = data.slice(-20);
        if (recentData.length >= 2) {
            var recentStart = recentData[0].nav;
            var recentEnd = recentData[recentData.length - 1].nav;
            var recentReturn = recentEnd / recentStart - 1;
            var recentYears = 20 / 252;
            var recentAnnReturn = (Math.pow(1 + recentReturn, 1 / recentYears) - 1) * 100;
            annReturnTrend = recentAnnReturn - annReturn;
        }

        return {
            acc5: acc5, acc10: acc10, acc20: acc20, accWeighted: accWeighted,
            annReturn: annReturn, totalDays: data.length, signalStats: signalStats,
            accWeightedTrend: accWeightedTrend, annReturnTrend: annReturnTrend
        };
    }

    function fmtPct(v, d) { d = d || 1; return (v >= 0 ? '+' : '') + v.toFixed(d) + '%'; }
    function fmtNum(v, d) { d = d || 1; return v.toFixed(d); }

    return {
        SIGNALS: SIGNALS,
        SIGNAL_MAP: SIGNAL_MAP,
        THRESHOLDS: THRESHOLDS,
        WEIGHTS: WEIGHTS,
        getSignal: getSignal,
        judge: judge,
        judgeScore: judgeScore,
        judgeLabel: judgeLabel,
        weightedAccuracy: weightedAccuracy,
        processRealData: processRealData,
        calcKPI: calcKPI,
        fmtPct: fmtPct,
        fmtNum: fmtNum
    };
})();

# -*- coding: utf-8 -*-
"""
유성현황 — 전 세계 유성 관측 현황판 + 오늘 밤 한국 관측 가이드
====================================================================
· 데이터: Global Meteor Network (전 세계 아마추어 카메라망, CC-BY 4.0)
          https://globalmeteornetwork.org/
· 하는 일: GMN이 6시간마다 공개하는 유성 궤도 데이터를 받아
          ① 오늘 밤 관측 조건 + 시간대별 예상 관측 개수(복사점 고도·달·박명 직접 계산)
          ② 어디로 가면 잘 보이나 — 빛공해 추정으로 전국 관측지 순위 + 가장 어두운 지점 탐색
          ③ 최근 관측된 유성 세계지도
          ④~⑥ 시간대별 검출량 / 유성우 순위 / 밝은 유성 TOP
          ⑦ GMN 실시간 활동량(ZHR) 그래프  ⑧ 실시간 관측 사이트 링크
          를 한 장짜리 HTML로 만든다. (인터넷 없이도 열리는 self-contained)

· 예측 방식: 빛공해는 전국 도시 인구·거리로 추정(Walker 법칙)해 한계등급으로 환산하고,
            관측 개수는 IMO 표준식 HR = ZHR × sin(복사점고도) ÷ r^(6.5−한계등급) 로 계산.
            달이 뜬 시간대는 0.6배. 지형·구름은 반영하지 않으므로 순위 참고용.

사용법:  python 유성현황.py                    (서울 기준)
         python 유성현황.py --lat 35.18 --lon 129.08 --place 부산
         python 유성현황.py --nocache          (캐시 무시하고 새로 받기)

※ GMN '궤도' 데이터는 여러 나라 카메라를 대조해 계산하므로 관측 후 2~3일 지연된다.
   진짜 초 단위 실시간은 전파관측(2단계)·자체 카메라(3단계)에서 붙일 것.
"""
import os, sys, math, base64, datetime, re, urllib.parse

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    import requests
except ImportError:
    print("[설치 필요] pip install requests"); sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "_데이터")
OUT  = os.path.join(HERE, "유성현황.html")
KST  = datetime.timezone(datetime.timedelta(hours=9))
UTC  = datetime.timezone.utc

GMN_BASE  = "https://globalmeteornetwork.org"
GMN_FILES = ["traj_summary_latest_daily.txt", "traj_summary_yesterday.txt"]
FLUX_PAGE = GMN_BASE + "/flux/"
LAND_URL  = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector"
             "/master/geojson/ne_110m_land.geojson")

# 관측지 기본값(서울시청)
LAT, LON, PLACE = 37.5665, 126.9780, "서울"
NOCACHE = False

# IAU 유성우 코드 → 한글 이름 (확실한 것만. 없는 코드는 코드 그대로 표기)
SHOWER_KO = {
    "PER": "페르세우스자리", "GEM": "쌍둥이자리", "QUA": "사분의자리",
    "LYR": "거문고자리", "ETA": "물병자리 에타", "ORI": "오리온자리",
    "LEO": "사자자리", "URS": "작은곰자리", "DRA": "용자리",
    "NTA": "황소자리 북부", "STA": "황소자리 남부", "SDA": "물병자리 델타 남부",
    "CAP": "염소자리 알파", "KCG": "백조자리 카파", "AUR": "마차부자리",
    "MON": "외뿔소자리", "COM": "머리털자리", "LMI": "작은사자자리",
    "NDA": "물병자리 델타 북부", "PAU": "남쪽물고기자리",
    "ERI": "에리다누스자리", "AOA": "물병자리 오미크론",
}
SPORADIC = "..."

# 주요 유성우 연례 극대일 (월, 일) — 해마다 하루 안쪽에서만 움직이는 안정된 값
PEAK_DAY = {
    "QUA": (1, 3), "LYR": (4, 22), "ETA": (5, 6), "SDA": (7, 30), "CAP": (7, 30),
    "PER": (8, 12), "KCG": (8, 18), "DRA": (10, 8), "STA": (10, 10), "ORI": (10, 21),
    "NTA": (11, 12), "LEO": (11, 17), "GEM": (12, 14), "URS": (12, 22),
}


def days_to_peak(code, today):
    """오늘 기준 극대까지 남은 날수(음수면 지난 것). 모르는 유성우면 None"""
    if code not in PEAK_DAY:
        return None
    m, d = PEAK_DAY[code]
    best = None
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            delta = (datetime.date(y, m, d) - today).days
        except ValueError:
            continue
        if best is None or abs(delta) < abs(best):
            best = delta
    return best

PALETTE = ["#ffd166", "#4cc9f0", "#f72585", "#80ed99", "#b8b8ff",
           "#ff9e6d", "#8ecae6", "#c77dff", "#ffe66d", "#90be6d"]

# 유성우별 표준 활동량: (ZHR, r=밝기분포지수) — IMO 워킹리스트 공표값
SHOWER_ZHR = {
    "QUA": (110, 2.1), "LYR": (18, 2.1), "ETA": (50, 2.4), "SDA": (25, 3.0),
    "CAP": (5, 2.5), "PER": (100, 2.2), "KCG": (3, 3.0), "DRA": (5, 2.6),
    "STA": (5, 2.3), "ORI": (20, 2.5), "NTA": (5, 2.3), "LEO": (15, 2.5),
    "GEM": (150, 2.6), "URS": (10, 3.0),
}

# 광해 계산용 주요 도시 (이름, 위도, 경도, 인구만명) — 인구는 근사값
CITIES = [
    ("서울", 37.566, 126.978, 940), ("부산", 35.180, 129.075, 330),
    ("인천", 37.456, 126.705, 300), ("대구", 35.872, 128.601, 238),
    ("대전", 36.351, 127.385, 145), ("광주", 35.160, 126.851, 143),
    ("울산", 35.539, 129.311, 111), ("수원", 37.263, 127.029, 119),
    ("용인", 37.241, 127.178, 108), ("고양", 37.658, 126.832, 108),
    ("창원", 35.228, 128.681, 102), ("성남", 37.420, 127.127, 92),
    ("화성", 37.199, 126.831, 95), ("청주", 36.642, 127.489, 85),
    ("부천", 37.503, 126.766, 79), ("남양주", 37.636, 127.216, 73),
    ("천안", 36.815, 127.114, 66), ("전주", 35.824, 127.148, 65),
    ("안산", 37.322, 126.831, 64), ("평택", 36.992, 127.113, 58),
    ("안양", 37.394, 126.957, 55), ("김해", 35.229, 128.889, 54),
    ("시흥", 37.380, 126.803, 51), ("포항", 36.019, 129.343, 50),
    ("제주", 33.499, 126.531, 49), ("파주", 37.760, 126.780, 49),
    ("김포", 37.615, 126.716, 48), ("의정부", 37.738, 127.034, 46),
    ("구미", 36.120, 128.344, 41), ("원주", 37.342, 127.920, 36),
    ("양산", 35.335, 129.037, 35), ("진주", 35.180, 128.108, 34),
    ("아산", 36.790, 127.002, 34), ("경주", 35.856, 129.225, 25),
    ("춘천", 37.881, 127.730, 29), ("여수", 34.760, 127.662, 28),
    ("순천", 34.951, 127.487, 28), ("거제", 34.880, 128.621, 24),
    ("목포", 34.812, 126.392, 22), ("강릉", 37.752, 128.876, 21),
    ("충주", 36.991, 127.926, 21), ("안동", 36.568, 128.730, 16),
    ("통영", 34.854, 128.433, 12), ("정읍", 35.570, 126.856, 11),
    ("밀양", 35.504, 128.747, 10), ("영주", 36.806, 128.624, 10),
    ("속초", 38.207, 128.591, 8), ("남원", 35.416, 127.390, 8),
    ("태백", 37.164, 128.986, 4), ("합천", 35.567, 128.166, 4),
    ("영양", 36.667, 129.113, 2), ("인제", 38.070, 128.170, 3),
]

# 관측지 후보 (이름, 위도, 경도, 설명) — 좌표는 대략값(±수 km), 광해 판정에는 영향 없음
SITES = [
    ("김해천문대", 35.233, 128.799, "부산 바로 옆, 접근성 최고"),
    ("금정산 고당봉", 35.286, 129.057, "부산 시내 산 정상"),
    ("기장 달음산", 35.297, 129.204, "동해쪽 시야"),
    ("가덕도 연대봉", 35.030, 128.826, "남쪽 바다 방향 트임"),
    ("양산 배내골", 35.510, 129.021, "영남알프스 계곡"),
    ("울산 간월재", 35.573, 129.041, "억새평원, 사방 트임"),
    ("밀양 표충사·재약산", 35.489, 128.966, "산간 분지"),
    ("거제 학동몽돌해변", 34.786, 128.585, "남쪽 수평선"),
    ("통영 미륵산", 34.822, 128.428, "다도해 조망"),
    ("남해 금산 보리암", 34.744, 127.983, "남해안 고지대"),
    ("합천 황매산", 35.478, 128.055, "경남 대표 별보기 명소"),
    ("산청 지리산 중산리", 35.334, 127.771, "지리산 남부"),
    ("함양 오도재", 35.548, 127.658, "지리산 조망 고갯길"),
    ("하동 형제봉", 35.222, 127.727, "섬진강 상류"),
    ("거창 감악산", 35.626, 127.983, "고원 지대"),
    ("경주 토함산", 35.780, 129.343, "동해 일출 명소"),
    ("포항 호미곶", 36.076, 129.567, "동쪽 수평선"),
    ("무주 덕유산", 35.860, 127.750, "고지대 청정"),
    ("영양 반딧불이공원", 36.660, 129.108, "아시아 최초 국제밤하늘보호공원"),
    ("봉화 청옥산", 36.960, 128.900, "백두대간 오지"),
    ("태백 매봉산", 37.170, 128.930, "고랭지 배추밭"),
    ("정선 만항재", 37.220, 128.900, "국내 최고도 포장 고갯길"),
    ("평창 육백마지기", 37.400, 128.470, "청옥산 정상 평원"),
    ("인제 곰배령", 38.030, 128.360, "강원 오지"),
    ("화천 조경철천문대", 38.100, 127.700, "천문대 상주"),
    ("양평 벗고개", 37.600, 127.480, "수도권 대표 관측지"),
    ("홍천 살둔마을", 37.780, 128.320, "강원 산간"),
    ("강화 석모도", 37.700, 126.350, "서해 수평선"),
    ("제주 1100고지", 33.360, 126.470, "한라산 중산간"),
]


def haversine(lat1, lon1, lat2, lon2):
    """두 지점 거리(km)"""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def bearing(lat1, lon1, lat2, lon2):
    """방위각(도)"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def light_index(lat, lon):
    """빛공해 지수 — Walker 법칙 Σ(인구 / 거리^2.5). 값이 클수록 밝다(나쁘다)."""
    s = 0.0
    for _, cl, cn, pop in CITIES:
        d = max(1.0, haversine(lat, lon, cl, cn))
        s += pop * 10000.0 / d ** 2.5
    return s


def limiting_mag(idx):
    """빛공해 지수 → 맨눈 한계등급 추정. 서울 도심≈4.0, 청정 산간≈6.6 기준 보정."""
    ls = math.log10(max(idx, 1.0))
    return max(3.8, min(6.6, 4.0 + (7.0 - ls) * 0.52))


def bortle(lm_raw):
    lm = round(lm_raw, 1)                              # 화면에 쓰는 값과 같은 기준으로 판정
    """한계등급 → 보틀 등급(하늘 어둡기 9단계) 대략 표기"""
    for cut, name in ((6.4, "1~2 (최상급 청정)"), (6.2, "3 (시골 하늘)"),
                      (5.6, "4 (시골·교외 경계)"), (5.1, "5 (교외)"),
                      (4.6, "6 (밝은 교외)"), (4.2, "7 (도시 외곽)")):
        if lm >= cut:
            return name
    return "8~9 (도심)"


def hourly_rate(zhr, r, alt_deg, lm):
    """IMO 표준식으로 '실제로 눈에 보일' 시간당 개수 추정.
       HR = ZHR · sin(복사점고도) / r^(6.5−한계등급)"""
    if alt_deg <= 0:
        return 0.0
    return zhr * math.sin(math.radians(alt_deg)) / (r ** (6.5 - lm))


_LAND_RINGS = None


def land_rings():
    """육지 판정용 폴리곤(한반도 주변만). 바다 위를 '가장 어두운 곳'으로 추천하지 않기 위함."""
    global _LAND_RINGS
    if _LAND_RINGS is not None:
        return _LAND_RINGS
    import json
    _LAND_RINGS = []
    raw = cached(LAND_URL, "land.geojson", max_age_h=24 * 365)
    if raw:
        try:
            for feat in json.loads(raw).get("features", []):
                g = feat.get("geometry") or {}
                polys = [g["coordinates"]] if g.get("type") == "Polygon" else g.get("coordinates", [])
                for poly in polys:
                    for ring in poly:
                        xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
                        if max(xs) < 124 or min(xs) > 131 or max(ys) < 32 or min(ys) > 40:
                            continue                       # 한반도 주변 아니면 버림
                        _LAND_RINGS.append(ring)
        except Exception:
            pass
    return _LAND_RINGS


def on_land(lat, lon):
    """육지인가? (Natural Earth 110m 기준이라 해안선 오차 ±10km — 먼 바다 걸러내는 용도)"""
    rings = land_rings()
    if not rings:
        return True
    for ring in rings:
        inside = False
        n = len(ring)
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            if (y1 > lat) != (y2 > lat):
                xint = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
                if lon < xint:
                    inside = not inside
        if inside:
            return True
    return False


def south_of_dmz(lat, lon):
    """군사분계선 이남인가 — 서해(37.9°N)에서 동해(38.35°N)로 비스듬한 선을 근사"""
    limit = 37.9 + (lon - 126.7) * 0.265
    return lat <= max(37.9, min(38.4, limit))


def darkest_nearby(lat, lon, radius_km=120, step=0.04):
    """반경 안 육지에서 가장 어두운 지점을 격자 탐색 → (위도, 경도, 지수, 거리)"""
    best = None
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    y = lat - dlat
    while y <= lat + dlat:
        x = lon - dlon
        while x <= lon + dlon:
            if 33.0 <= y <= 38.4 and 125.9 <= x <= 129.7 and south_of_dmz(y, x):
                d = haversine(lat, lon, y, x)
                if d <= radius_km:
                    idx = light_index(y, x)
                    if (best is None or idx < best[2]) and on_land(y, x):
                        best = (y, x, idx, d)
            x += step * 1.25
        y += step
    return best


# ────────────────────────────── 다운로드 ──────────────────────────────
def cached(url, name, max_age_h=3, binary=False):
    """URL을 받아 _데이터/name 에 캐시. max_age_h 안이면 캐시 재사용.
    실패하면 캐시라도 있으면 캐시를 쓰고, 그것도 없으면 None."""
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name)
    fresh = False
    if os.path.exists(path) and not NOCACHE:
        age = (datetime.datetime.now().timestamp() - os.path.getmtime(path)) / 3600
        fresh = age < max_age_h
    if fresh:
        print(f"  · 캐시 사용: {name}")
    else:
        try:
            print(f"  · 받는 중: {name} ...", end="", flush=True)
            r = requests.get(url, timeout=180)
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)
            print(f" {len(r.content)//1024:,}KB")
        except Exception as e:
            print(f" 실패({e})")
            if not os.path.exists(path):
                return None
            print(f"    → 예전 캐시로 진행: {name}")
    if binary:
        return open(path, "rb").read()
    return open(path, encoding="utf-8", errors="replace").read()


# ────────────────────────────── GMN 파싱 ──────────────────────────────
# traj_summary 열 번호 (2026-08 기준 86열 포맷)
C_TIME, C_SHOWER, C_RA, C_DEC, C_VGEO = 2, 4, 7, 9, 15
C_LATB, C_LONB, C_HTB = 63, 65, 67
C_LATE, C_LONE = 69, 71
C_DUR, C_MAG, C_MASS, C_STATIONS = 75, 76, 79, 85


def parse_gmn(texts):
    """traj_summary 텍스트들 → 유성 dict 리스트 (중복 제거)"""
    seen, out = set(), []
    for text in texts:
        if not text:
            continue
        for line in text.splitlines():
            if line.startswith("#") or line.count(";") < 50:
                continue
            c = [x.strip() for x in line.split(";")]
            try:
                uid = c[0]
                if uid in seen:
                    continue
                seen.add(uid)
                t = datetime.datetime.strptime(c[C_TIME][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
                out.append({
                    "id": uid, "utc": t, "kst": t.astimezone(KST),
                    "shower": c[C_SHOWER] or SPORADIC,
                    "ra": float(c[C_RA]), "dec": float(c[C_DEC]),
                    "v": float(c[C_VGEO]),
                    "lat": float(c[C_LATB]), "lon": float(c[C_LONB]),
                    "lat2": float(c[C_LATE]), "lon2": float(c[C_LONE]),
                    "ht": float(c[C_HTB]),
                    "dur": float(c[C_DUR]), "mag": float(c[C_MAG]),
                    "mass": float(c[C_MASS]),
                    "stations": c[C_STATIONS].count(",") + 1 if c[C_STATIONS] else 0,
                })
            except Exception:
                continue
    out.sort(key=lambda m: m["utc"])
    return out


def shower_name(code):
    if code == SPORADIC:
        return "산발유성"
    return SHOWER_KO.get(code, f"{code} 유성우")


# ────────────────────────── 천문 계산 (직접 구현) ──────────────────────────
def jd(dt):
    return dt.timestamp() / 86400.0 + 2440587.5


def sun_radec(j):
    """태양 적경·적위(도). 저정밀(±0.01°) — 일몰·박명 계산엔 충분."""
    n = j - 2451545.0
    L = math.radians((280.460 + 0.9856474 * n) % 360)
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = L + math.radians(1.915) * math.sin(g) + math.radians(0.020) * math.sin(2 * g)
    eps = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    return math.degrees(ra) % 360, math.degrees(dec), math.degrees(lam) % 360


def moon_radec(j):
    """달 적경·적위(도) + 조도(0~1). 저정밀 — 관측 방해 판단용."""
    d = j - 2451545.0
    Lp = (218.316 + 13.176396 * d) % 360
    M  = math.radians((134.963 + 13.064993 * d) % 360)
    F  = math.radians((93.272 + 13.229350 * d) % 360)
    lam = math.radians(Lp) + math.radians(6.289) * math.sin(M)
    beta = math.radians(5.128) * math.sin(F)
    dist = 385001 - 20905 * math.cos(M)              # km
    eps = math.radians(23.4393 - 3.563e-7 * d)
    x = math.cos(beta) * math.cos(lam)
    y = math.cos(eps) * math.cos(beta) * math.sin(lam) - math.sin(eps) * math.sin(beta)
    z = math.sin(eps) * math.cos(beta) * math.sin(lam) + math.cos(eps) * math.sin(beta)
    ra, dec = math.degrees(math.atan2(y, x)) % 360, math.degrees(math.asin(z))
    # 조도: 태양과의 이각 → 위상각 → 밝은 면 비율
    _, _, slam = sun_radec(j)
    elong = math.acos(math.cos(beta) * math.cos(lam - math.radians(slam)))
    R = 149598000.0
    phase = math.atan2(R * math.sin(elong), dist - R * math.cos(elong))
    return ra, dec, (1 + math.cos(phase)) / 2


def gmst_deg(j):
    return (280.46061837 + 360.98564736629 * (j - 2451545.0)) % 360


def altitude(ra, dec, j, lat, lon):
    """지평고도(도)"""
    H = math.radians((gmst_deg(j) + lon - ra) % 360)
    la, de = math.radians(lat), math.radians(dec)
    return math.degrees(math.asin(math.sin(de) * math.sin(la) +
                                  math.cos(de) * math.cos(la) * math.cos(H)))


def azimuth(ra, dec, j, lat, lon):
    """방위각(도, 북=0 동=90)"""
    H = math.radians((gmst_deg(j) + lon - ra) % 360)
    la, de = math.radians(lat), math.radians(dec)
    az = math.atan2(math.sin(H),
                    math.cos(H) * math.sin(la) - math.tan(de) * math.cos(la))
    return (math.degrees(az) + 180) % 360


def compass(az):
    return ["북", "북동", "동", "남동", "남", "남서", "서", "북서"][int((az + 22.5) % 360 // 45)]


def crossings(alt_fn, t0, t1, target, step_min=4):
    """t0~t1 구간에서 고도가 target을 지나는 시각들 → [(시각, 상승여부)]"""
    out, prev_t, prev_v = [], None, None
    t = t0
    while t <= t1:
        v = alt_fn(t) - target
        if prev_v is not None and (prev_v < 0) != (v < 0):
            frac = prev_v / (prev_v - v)
            out.append((prev_t + (t - prev_t) * frac, v > 0))
        prev_t, prev_v = t, v
        t += datetime.timedelta(minutes=step_min)
    return out


def night_info(date_kst, lat, lon):
    """그날 저녁~다음날 아침의 일몰·천문박명·일출·달 정보"""
    t0 = datetime.datetime.combine(date_kst, datetime.time(12, 0), tzinfo=KST)
    t1 = t0 + datetime.timedelta(hours=24)
    sun_alt = lambda t: altitude(*sun_radec(jd(t))[:2], jd(t), lat, lon)
    moon_alt = lambda t: altitude(*moon_radec(jd(t))[:2], jd(t), lat, lon)

    def pick(cs, rising):
        for t, up in cs:
            if up == rising:
                return t
        return None

    sunset  = pick(crossings(sun_alt, t0, t1, -0.833), False)
    sunrise = pick(crossings(sun_alt, t0, t1, -0.833), True)
    dusk    = pick(crossings(sun_alt, t0, t1, -18), False)
    dawn    = pick(crossings(sun_alt, t0, t1, -18), True)
    mrise   = pick(crossings(moon_alt, t0, t1, -0.833), True)
    mset    = pick(crossings(moon_alt, t0, t1, -0.833), False)
    illum   = moon_radec(jd(t0 + datetime.timedelta(hours=12)))[2]
    return {"sunset": sunset, "sunrise": sunrise, "dusk": dusk, "dawn": dawn,
            "moonrise": mrise, "moonset": mset, "illum": illum,
            "moon_alt": moon_alt, "t0": t0, "t1": t1}


# ────────────────────────────── 세계지도 ──────────────────────────────
MAP_W, MAP_H = 1000, 500


def xy(lat, lon):
    return (lon + 180) / 360 * MAP_W, (90 - lat) / 180 * MAP_H


def land_paths():
    """Natural Earth 110m 육지 → SVG path 문자열 (간략화해서 용량 축소)"""
    import json
    cache = os.path.join(DATA, "land_paths.txt")
    if os.path.exists(cache) and not NOCACHE:
        return open(cache, encoding="utf-8").read()
    raw = cached(LAND_URL, "land.geojson", max_age_h=24 * 365)
    if not raw:
        return ""
    try:
        gj = json.loads(raw)
    except Exception:
        return ""
    parts = []
    for feat in gj.get("features", []):
        geom = feat.get("geometry") or {}
        polys = geom.get("coordinates", [])
        if geom.get("type") == "Polygon":
            polys = [polys]
        for poly in polys:
            for ring in (poly if geom.get("type") in ("Polygon", "MultiPolygon") else []):
                pts, last = [], None
                for lon, lat in ring:
                    x, y = xy(lat, lon)
                    p = (round(x, 1), round(y, 1))
                    if p != last:
                        pts.append(p); last = p
                if len(pts) < 4:
                    continue
                parts.append("M" + "L".join(f"{x},{y}" for x, y in pts) + "Z")
    out = " ".join(parts)
    try:
        with open(cache, "w", encoding="utf-8") as f:
            f.write(out)
    except Exception:
        pass
    return out


# ────────────────────────────── HTML 생성 ──────────────────────────────
def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build_html(meteors, flux_imgs, gen_time, fragment=False):
    """fragment=True 면 <html>·<head> 껍데기 없이 본문만 — 웹에 올릴 때(아티팩트 등) 쓴다."""
    import collections
    counts = collections.Counter(m["shower"] for m in meteors)
    ranked = [c for c, _ in counts.most_common() if c != SPORADIC]
    color = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(ranked)}
    color[SPORADIC] = "#7d8597"

    t_from = min(m["utc"] for m in meteors) if meteors else None
    t_to   = max(m["utc"] for m in meteors) if meteors else None
    lag_h  = (gen_time.astimezone(UTC) - t_to).total_seconds() / 3600 if t_to else 0

    # ── 오늘 밤 관측 가이드 ──
    today = gen_time.astimezone(KST).date()
    if gen_time.astimezone(KST).hour < 12:          # 새벽에 돌리면 '어젯밤'이 오늘 밤
        today = today - datetime.timedelta(days=1)
    ni = night_info(today, LAT, LON)

    # 관측 대상: 검출 30건 이상인 유성우 (복사점은 최근 관측 중앙값)
    import statistics
    idx_home = light_index(LAT, LON)
    lm_home = limiting_mag(idx_home)
    guide = []
    for code in ranked[:3]:                          # 상위 3개만 (나머지는 ④ 표에서)
        ms = [m for m in meteors if m["shower"] == code]
        if len(ms) < 100:
            continue
        ra = statistics.median(m["ra"] for m in ms)
        dec = statistics.median(m["dec"] for m in ms)
        v = statistics.median(m["v"] for m in ms)
        zhr, rr = SHOWER_ZHR.get(code, (None, None))
        hours = []
        t = datetime.datetime.combine(today, datetime.time(19, 0), tzinfo=KST)
        for _ in range(11):                          # 19시 ~ 05시
            j = jd(t)
            alt = altitude(ra, dec, j, LAT, LON)
            dark = altitude(*sun_radec(j)[:2], j, LAT, LON) < -18
            moon_up = ni["moon_alt"](t) > 0
            hr = None
            if zhr and dark:                          # 박명 중엔 사실상 관측 불가
                hr = hourly_rate(zhr, rr, alt, lm_home) * (0.6 if moon_up else 1.0)
            hours.append({"t": t, "alt": alt, "dark": dark, "moon": moon_up, "hr": hr,
                          "eff": max(0.0, math.sin(math.radians(alt)))})
            t += datetime.timedelta(hours=1)
        best = max(hours, key=lambda h: (h["dark"], h["eff"] * (0.55 if h["moon"] else 1.0)))
        guide.append({"code": code, "n": len(ms), "ra": ra, "dec": dec, "v": v,
                      "hours": hours, "best": best, "peak": days_to_peak(code, today),
                      "zhr": zhr, "r": rr,
                      "az": azimuth(ra, dec, jd(best["t"]), LAT, LON)})
    guide.sort(key=lambda g: -g["n"])

    def hhmm(t):
        return t.astimezone(KST).strftime("%H:%M") if t else "—"

    # ── 지도 점 ──
    dots = []
    for m in meteors:
        x, y = xy(m["lat"], m["lon"])
        r = 1.6 if m["mag"] > -1 else (2.6 if m["mag"] > -4 else 4.0)
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color[m["shower"]]}"/>')
    sx, sy = xy(LAT, LON)

    # ── 시간대별(KST) ──
    hourly = collections.Counter(m["kst"].hour for m in meteors)
    hmax = max(hourly.values()) if hourly else 1

    # ── 밝은 유성 TOP ──
    top = sorted(meteors, key=lambda m: m["mag"])[:12]

    css = """
    *{box-sizing:border-box} body{margin:0;background:#0b1020;color:#e7ecf5;
      font-family:'맑은 고딕','Malgun Gothic',system-ui,sans-serif;line-height:1.6}
    .wrap{max-width:1080px;margin:0 auto;padding:24px 18px 60px}
    h1{font-size:26px;margin:0 0 4px} h2{font-size:19px;margin:34px 0 12px;
      padding-bottom:8px;border-bottom:1px solid #263050}
    .sub{color:#8b97b5;font-size:13px}
    .card{background:#131a30;border:1px solid #222c4d;border-radius:12px;padding:16px;margin:12px 0;
      overflow-x:auto}
    .grid{display:grid;gap:12px}
    .g4{grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}
    .big{font-size:30px;font-weight:700;color:#ffd166;line-height:1.2}
    .lbl{color:#8b97b5;font-size:12px}
    table{width:100%;border-collapse:collapse;font-size:13px}
    th,td{padding:7px 8px;text-align:left;border-bottom:1px solid #222c4d;white-space:nowrap}
    th{color:#8b97b5;font-weight:600;font-size:12px}
    .r{text-align:right}
    .bar{height:9px;background:#1d2540;border-radius:5px;overflow:hidden}
    .bar>i{display:block;height:100%;background:linear-gradient(90deg,#4cc9f0,#ffd166)}
    .chip{display:inline-block;padding:2px 8px;border-radius:99px;font-size:12px;
      background:#1d2540;color:#cfd8ee;margin-right:4px}
    .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:middle}
    .hr{display:grid;grid-template-columns:52px 1fr 62px;gap:8px;align-items:center;
      font-size:12px;padding:2px 0}
    .hbar{height:14px;border-radius:4px;background:#1d2540;position:relative;overflow:hidden}
    .hbar>i{position:absolute;left:0;top:0;bottom:0;background:#3d7bd6}
    .hbar.dark>i{background:#4cc9f0} .hbar.moon>i{background:#8a6f3a}
    a{color:#7cc4ff} .note{color:#8b97b5;font-size:12px;margin-top:8px}
    @media (max-width:640px){
      .wrap{padding:16px 12px 40px} h1{font-size:22px} h2{font-size:17px}
      .big{font-size:24px} th,td{padding:6px 5px;font-size:12px}
      .hr{grid-template-columns:42px 1fr 68px}
    }
    #stale{display:none;background:#3a1c1c;border:1px solid #6b2b2b;color:#ffb3b3;
      border-radius:12px;padding:14px;margin:12px 0;font-size:14px}
    .warn{background:#2a1e12;border-color:#5a4020;color:#ffcf8f}
    svg text{font-size:11px}
    img.flux{width:100%;border-radius:8px;background:#fff}
    """

    # 카톡 등에 링크를 붙였을 때 보이는 미리보기 문구
    og_desc = ""
    if guide:
        og_desc = (f"{shower_name(guide[0]['code'])} 유성우 · {PLACE} 기준 "
                   f"{guide[0]['best']['t']:%H시} {compass(guide[0]['az'])}쪽 하늘이 가장 좋습니다")
    head = ("" if fragment else
            '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta property="og:type" content="website">'
            f'<meta property="og:locale" content="ko_KR">'
            f'<meta property="og:title" content="🌠 유성현황 — {esc(PLACE)} 기준 오늘 밤 예보">'
            f'<meta property="og:description" content="{esc(og_desc)}">'
            f'<meta name="description" content="{esc(og_desc)}">')
    open_body = "" if fragment else "</head><body>"
    H = [f"""{head}
<title>유성현황 — {esc(PLACE)} 기준</title><style>{css}</style>{open_body}<div class="wrap">
<h1>🌠 유성현황</h1>
<div class="sub">생성 {gen_time.astimezone(KST):%Y-%m-%d %H:%M} KST · 관측지 {esc(PLACE)}
 ({LAT:.3f}, {LON:.3f}) · 데이터 <a href="{GMN_BASE}" target="_blank">Global Meteor Network</a> (CC BY 4.0)</div>
"""]

    # 날짜가 지나면 스스로 알려주는 안내 (공유받은 친구가 며칠 뒤 열 수 있으므로)
    H.append(f'<div id="stale" data-night="{today:%Y-%m-%d}"></div>')

    # 오늘 밤 한 줄 요약
    moon_pct = ni["illum"] * 100
    head = guide[0] if guide else None
    if head:
        dp = head["peak"]
        when = ("오늘이 극대일" if dp == 0 else
                f"극대 {dp}일 전" if dp and 0 < dp <= 5 else
                f"극대 {-dp}일 지남" if dp and -5 <= dp < 0 else "활동 중")
        verdict = ("최고 조건" if moon_pct < 15 and dp is not None and abs(dp) <= 1 else
                   "볼 만함" if moon_pct < 40 else "달빛 때문에 아쉬움")
        banner = (f"<b style='color:#ffd166;font-size:20px'>{esc(shower_name(head['code']))} 유성우 · {when}</b><br>"
                  f"달 밝기 {moon_pct:.0f}% · 추천 {head['best']['t']:%H시}쯤 "
                  f"{compass(head['az'])}쪽 하늘 — <b>{esc(verdict)}</b>")
    else:
        banner = (f"지금은 큰 유성우 없이 산발유성 위주입니다. 달 밝기 {moon_pct:.0f}%.")
    H.append(f'<div class="card" style="border-color:#3d4a7a;background:#16203c">{banner}</div>')

    moon_txt = ("달 없음 — 최고 조건" if moon_pct < 15 else
                "달빛 약간" if moon_pct < 40 else
                "달빛 방해 있음" if moon_pct < 70 else "달이 밝아 불리")
    H.append(f"""<h2>① 오늘 밤 {esc(PLACE)} 관측 조건 · {today:%m월 %d일} 밤</h2>
<div class="card"><div class="grid g4">
  <div><div class="lbl">일몰</div><div class="big">{hhmm(ni['sunset'])}</div></div>
  <div><div class="lbl">완전히 어두워짐(천문박명 끝)</div><div class="big">{hhmm(ni['dusk'])}</div></div>
  <div><div class="lbl">새벽 밝아지기 시작</div><div class="big">{hhmm(ni['dawn'])}</div></div>
  <div><div class="lbl">달 밝기 · {esc(moon_txt)}</div><div class="big">{moon_pct:.0f}%</div>
       <div class="lbl">월출 {hhmm(ni['moonrise'])} · 월몰 {hhmm(ni['moonset'])}</div></div>
</div></div>""")

    if guide:
        for g in guide:
            best = g["best"]
            H.append(f"""<div class="card">
<div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px">
  <div><span class="dot" style="background:{color[g['code']]}"></span>
       <b style="font-size:17px">{esc(shower_name(g['code']))}</b>
       {'<span class="chip" style="background:#5a3a12;color:#ffd166">극대 D'
        + ('%+d' % -g['peak'] if g['peak'] else '-DAY') + '</span>' if g['peak'] is not None else ''}
       <span class="chip">최근 {g['n']:,}개 검출</span>
       <span class="chip">진입속도 {g['v']:.0f} km/s</span></div>
  <div class="lbl">복사점 적경 {g['ra']:.0f}° 적위 {g['dec']:+.0f}°</div>
</div>
<div class="note">추천 시간 <b style="color:#ffd166">{best['t']:%H시}</b>
  — 이때 복사점이 <b>{best['alt']:.0f}°</b> 높이({compass(g['az'])}쪽 하늘), 관측 효율 {best['eff']*100:.0f}%
  {'· 달 떠 있음' if best['moon'] else ''}</div>
<div style="margin-top:10px">""")
            hrmax = max([h["hr"] or 0 for h in g["hours"]] + [1])
            for h in g["hours"]:
                use_hr = h["hr"] is not None
                w = (h["hr"] / hrmax * 100) if use_hr else max(0, min(100, h["alt"] / 90 * 100))
                cls = "hbar" + (" dark" if h["dark"] else "") + (" moon" if h["moon"] and h["dark"] else "")
                right = (f"{h['hr']:.0f}개/시" if use_hr else
                         ("박명" if not h["dark"] else f"{h['alt']:+.0f}°"))
                H.append(f"""<div class="hr"><span class="lbl">{h['t']:%H시}</span>
<span class="{cls}"><i style="width:{w:.0f}%"></i></span>
<span class="lbl r">{right}{' 🌙' if h['moon'] else ''}</span></div>""")
            if g["zhr"]:
                H.append(f'<div class="note">막대 = <b>{esc(PLACE)}에서 눈으로 보일 시간당 개수</b> 예측 '
                         f'(표준 활동량 ZHR {g["zhr"]} 기준, 이곳 한계등급 {lm_home:.1f}등급 반영). '
                         f'박명 시간대는 관측 불가로 봅니다.</div>')
            H.append("</div></div>")
        H.append('<div class="note">파란 막대 = 하늘이 완전히 어두운 시간, 갈색 = 달이 떠 있어 손해 보는 시간, '
                 '회색 = 아직 박명. 막대 길이는 복사점 고도(높을수록 많이 보임). '
                 '복사점 위치는 최근 GMN 관측의 중앙값이라 실제와 몇 도 차이날 수 있습니다.</div>')
    else:
        H.append('<div class="card warn">지금은 검출량 30개 이상인 주요 유성우가 없습니다. '
                 '산발유성만 시간당 몇 개 보이는 시기입니다.</div>')

    # ── ② 어디로 가면 잘 보이나 ──
    if guide:
        g0 = guide[0]
        alt_best = g0["best"]["alt"]
        moon_f = 0.6 if g0["best"]["moon"] else 1.0
        zhr, rr = (g0["zhr"], g0["r"]) if g0["zhr"] else (100, 2.2)
        home_hr = hourly_rate(zhr, rr, alt_best, lm_home) * moon_f

        cand = []
        for name, sl, sn, desc in SITES:
            d = haversine(LAT, LON, sl, sn)
            if d > 150:                                # 당일 왕복 가능한 범위만
                continue
            lm = limiting_mag(light_index(sl, sn))
            alt_s = altitude(g0["ra"], g0["dec"], jd(g0["best"]["t"]), sl, sn)
            hr = hourly_rate(zhr, rr, alt_s, lm) * moon_f
            cand.append({"name": name, "desc": desc, "d": d, "lm": lm, "hr": hr,
                         "dir": compass(bearing(LAT, LON, sl, sn)),
                         "gain": hr / home_hr if home_hr > 0 else 0,
                         "lat": sl, "lon": sn})
        cand.sort(key=lambda c: -c["hr"])
        if not cand:                                   # 후보가 아예 없으면(해외 등) 섹션 생략
            guide[0]["nosite"] = True
        near = sorted([c for c in cand if c["d"] <= 60], key=lambda c: -c["hr"])[:3] or cand[:1]
        far = [c for c in cand if c not in near][:5]
        # 멀리 갈 값어치가 있는지 한 줄로
        worth = ""
        if near and cand and near[0]["hr"] > 0:
            extra = cand[0]["hr"] / near[0]["hr"]
            worth = ("가까운 곳과 먼 곳 차이가 크지 않으니 <b>가까운 데서 오래 보는 편</b>이 낫습니다."
                     if extra < 1.25 else
                     f"멀리 가면 {extra:.1f}배 더 보입니다 — 시간이 되면 나갈 값어치가 있습니다.")

        dk = darkest_nearby(LAT, LON, 120)
        dk_txt = ""
        if dk:
            dlat, dlon, didx, dd = dk
            dlm = limiting_mag(didx)
            nearest = min(SITES, key=lambda s: haversine(dlat, dlon, s[1], s[2]))
            nd = haversine(dlat, dlon, nearest[1], nearest[2])
            where = f"{nearest[0]} 부근" if nd < 20 else f"{compass(bearing(LAT, LON, dlat, dlon))}쪽 산간"
            dk_txt = (f"반경 120km 안에서 계산상 가장 어두운 지점은 <b>{esc(where)}</b> "
                      f"({dlat:.2f}, {dlon:.2f}) — {esc(PLACE)}에서 {dd:.0f}km, "
                      f"예상 한계등급 {dlm:.1f}등급.")

        H.append(f"""<h2>② 어디로 가면 잘 보이나 — {esc(PLACE)} 기준</h2>
<div class="card"><div class="grid g4">
  <div><div class="lbl">지금 계신 곳({esc(PLACE)}) 하늘</div>
       <div class="big">{home_hr:.0f}개<span style="font-size:15px">/시간</span></div>
       <div class="lbl">한계등급 {lm_home:.1f} · 보틀 {esc(bortle(lm_home))}</div></div>
  <div><div class="lbl">60km 이내 최선</div>
       <div class="big">{near[0]['hr']:.0f}개<span style="font-size:15px">/시간</span></div>
       <div class="lbl">{esc(near[0]['name'])} · {near[0]['d']:.0f}km</div></div>
  <div><div class="lbl">150km 이내 최선</div>
       <div class="big">{cand[0]['hr']:.0f}개<span style="font-size:15px">/시간</span></div>
       <div class="lbl">{esc(cand[0]['name'])} · {cand[0]['d']:.0f}km</div></div>
  <div><div class="lbl">보는 방향</div>
       <div class="big">{esc(compass(g0['az']))}쪽</div>
       <div class="lbl">{g0['best']['t']:%H시} 기준 고도 {alt_best:.0f}°</div></div>
</div></div>

<div class="card"><table>
<tr><th>관측지</th><th class="r">방향·거리</th><th class="r">예상 한계등급</th>
    <th class="r">보틀</th><th class="r">예상 관측</th><th class="r">지금 위치 대비</th></tr>""")
        for c in near + far:
            hl = ' style="background:#16203c"' if c in near else ""
            H.append(f"""<tr{hl}><td><b>{esc(c['name'])}</b><br>
<span class="lbl">{esc(c['desc'])}</span></td>
<td class="r">{esc(c['dir'])} {c['d']:.0f}km</td>
<td class="r">{c['lm']:.1f}등급</td><td class="r"><span class="lbl">{esc(bortle(c['lm']))}</span></td>
<td class="r" style="color:#ffd166"><b>{c['hr']:.0f}개/시</b></td>
<td class="r">{c['gain']:.1f}배</td></tr>""")
        H.append(f"""</table>
<div class="note">{worth} {dk_txt}</div>
<div class="note">계산 방식: 전국 주요 도시 인구·거리로 빛공해를 추정(Walker 법칙)해 한계등급을 내고,
 IMO 표준식 <b>시간당 개수 = ZHR × sin(복사점 고도) ÷ r<sup>(6.5−한계등급)</sup></b> 로 환산했습니다.
 달이 떠 있는 시간대는 0.6배로 깎았습니다. 실제 관측은 구름·산지 지형·주변 가로등에 더 좌우되니
 <b>순위 참고용</b>으로 보시고, {esc(compass(g0['az']))}쪽 지평선이 트인 자리를 고르세요.</div>
<div class="note">복사점이 {esc(compass(g0['az']))}쪽에 있어도 유성은 하늘 전체에 흐릅니다.
 복사점에서 30~50° 떨어진 하늘을 넓게 보는 게 가장 많이 잡힙니다. 누워서 하늘 전체를 보세요.</div>
</div>""")

    # 세계지도
    lagtxt = (f"관측 시각 {t_from.astimezone(KST):%m/%d %H:%M} ~ {t_to.astimezone(KST):%m/%d %H:%M} KST "
              f"(약 {lag_h:.0f}시간 전까지)") if t_to else ""
    H.append(f"""<h2>③ 최근 관측된 유성 {len(meteors):,}개 — 세계 지도</h2>
<div class="card"><div class="lbl" style="margin-bottom:8px">{lagtxt}</div>
<svg viewBox="0 0 {MAP_W} {MAP_H}" style="width:100%;background:#0a1226;border-radius:8px">
  <path d="{land_paths()}" fill="#182444" stroke="#24345e" stroke-width="0.6"/>
  <g>{''.join(dots)}</g>
  <circle cx="{sx:.1f}" cy="{sy:.1f}" r="5" fill="none" stroke="#ff4d6d" stroke-width="2"/>
  <text x="{sx+9:.1f}" y="{sy+4:.1f}" fill="#ff8fa3">{esc(PLACE)}</text>
</svg>
<div class="note">점 하나 = 유성 하나가 빛나기 시작한 지점(대기권 약 100km). 큰 점일수록 밝은 유성.
 유럽·북미에 몰려 보이는 건 그쪽에 카메라가 많아서지, 유성이 거기만 떨어져서가 아닙니다.
 한국에는 GMN 카메라가 거의 없습니다 — 3단계에서 우리가 놓을 자리입니다.</div>
<div style="margin-top:10px">""")
    for c in ranked[:8] + [SPORADIC]:
        H.append(f'<span class="chip"><span class="dot" style="background:{color[c]}"></span>'
                 f'{esc(shower_name(c))} {counts[c]:,}</span>')
    H.append("</div></div>")

    # 시간대별
    H.append("""<h2>④ 한국 시간대별 검출량</h2><div class="card">""")
    for h in range(24):
        n = hourly.get(h, 0)
        H.append(f"""<div class="hr"><span class="lbl">{h:02d}시</span>
<span class="hbar"><i style="width:{n/hmax*100:.0f}%"></i></span>
<span class="lbl r">{n:,}</span></div>""")
    H.append('<div class="note">전 세계 카메라 합계라 "한국에서 몇 시에 많이 보인다"는 뜻은 아닙니다. '
             '지구 자전으로 관측망이 밤을 통과하는 리듬입니다.</div></div>')

    # 유성우 순위
    H.append("""<h2>⑤ 유성우별 순위</h2><div class="card"><table>
<tr><th>유성우</th><th class="r">검출</th><th class="r">평균 속도</th><th class="r">가장 밝은 등급</th><th class="r">비중</th></tr>""")
    total = len(meteors)
    for c, n in counts.most_common(12):
        ms = [m for m in meteors if m["shower"] == c]
        vv = sum(m["v"] for m in ms) / len(ms)
        mg = min(m["mag"] for m in ms)
        H.append(f"""<tr><td><span class="dot" style="background:{color[c]}"></span>{esc(shower_name(c))}</td>
<td class="r">{n:,}</td><td class="r">{vv:.0f} km/s</td><td class="r">{mg:+.1f}</td>
<td class="r" style="width:120px"><span class="bar"><i style="width:{n/total*100:.0f}%"></i></span></td></tr>""")
    H.append("</table></div>")

    # 밝은 유성
    H.append("""<h2>⑥ 가장 밝았던 유성 TOP 12</h2><div class="card"><table>
<tr><th>시각(KST)</th><th>유성우</th><th class="r">밝기</th><th class="r">속도</th>
<th class="r">질량</th><th class="r">위치</th><th class="r">카메라</th></tr>""")
    for m in top:
        H.append(f"""<tr><td>{m['kst']:%m/%d %H:%M}</td>
<td><span class="dot" style="background:{color[m['shower']]}"></span>{esc(shower_name(m['shower']))}</td>
<td class="r" style="color:#ffd166">{m['mag']:+.1f}등</td><td class="r">{m['v']:.0f} km/s</td>
<td class="r">{m['mass']*1000:.2f} g</td>
<td class="r">{m['lat']:.1f}°, {m['lon']:.1f}°</td><td class="r">{m['stations']}대</td></tr>""")
    H.append('<div class="note">밝기는 등급(magnitude) — 숫자가 작을수록 밝습니다. '
             '0등이 밝은 별, -4등이면 금성만큼, 그보다 밝으면 화구(fireball)라 부릅니다.</div></table></div>')

    # 실시간 활동량
    if flux_imgs:
        H.append("""<h2>⑦ 지금 활동량 (GMN 실시간 ZHR)</h2><div class="card">""")
        for title, b64 in flux_imgs:
            H.append(f'<div class="lbl" style="margin:6px 0">{esc(title)}</div>'
                     f'<img class="flux" src="data:image/png;base64,{b64}">')
        H.append('<div class="note">GMN이 몇 시간 간격으로 갱신하는 실측 활동량(ZHR) 그래프입니다. '
                 f'원본: <a href="{FLUX_PAGE}" target="_blank">globalmeteornetwork.org/flux</a></div></div>')

    # 실시간으로 보는 곳
    H.append(f"""<h2>⑧ 지금 이 순간을 보고 싶다면</h2><div class="card">
<table>
<tr><th>사이트</th><th>방식</th><th>실시간성</th></tr>
<tr><td><a href="https://livemeteors.com/" target="_blank">LiveMeteors.com</a></td>
    <td>전파(라디오) 반사 — 소리와 스펙트로그램</td><td style="color:#80ed99">초 단위 실시간</td></tr>
<tr><td><a href="https://tammojan.github.io/meteormap/" target="_blank">Meteor Map</a></td>
    <td>GMN 궤도 지도</td><td>1~3일 지연</td></tr>
<tr><td><a href="https://meteorshowers.seti.org/" target="_blank">NASA CAMS 포털</a></td>
    <td>복사점 3D</td><td>하루 단위</td></tr>
<tr><td><a href="https://www.amsmeteors.org/fireballs/fireball-report/" target="_blank">AMS 화구 신고 로그</a></td>
    <td>목격자 신고</td><td style="color:#ffd166">큰 화구는 수십 분 내</td></tr>
</table>
<div class="note">이 현황판이 쓰는 GMN 궤도 데이터는 여러 나라 카메라를 대조해 계산하느라
 관측 후 <b>2~3일</b> 걸립니다. 초 단위 실시간을 원하면 전파 관측(RTL-SDR)이나
 자체 카메라 스테이션을 붙여야 합니다.</div></div>

<div class="sub" style="margin-top:30px">
유성 데이터 © Global Meteor Network (CC BY 4.0) · 지도 © Natural Earth ·
 일몰·달·복사점 고도는 이 프로그램이 직접 계산합니다(오차 ±1분 수준).<br>
 이 페이지는 <b>{gen_time.astimezone(KST):%Y-%m-%d %H:%M}</b>에 만들어진 스냅샷입니다 — 스스로 갱신되지 않습니다.
</div></div>""")

    # 공유받은 사람이 며칠 뒤에 열면 스스로 알려주는 스크립트 (f-string 아님 — JS 중괄호 때문)
    H.append("""
<script>
(function(){
  var el = document.getElementById('stale'); if(!el) return;
  var night = new Date(el.dataset.night + 'T12:00:00+09:00');
  var now = new Date();
  // 한국 시각 기준으로 '오늘 밤'을 판정 (0~11시는 아직 어젯밤으로 친다)
  var kst = new Date(now.getTime() + now.getTimezoneOffset()*60000 + 9*3600000);
  var todayNight = new Date(kst);
  if (kst.getHours() < 12) todayNight.setDate(kst.getDate() - 1);
  todayNight.setHours(12,0,0,0);
  var diff = Math.round((todayNight - night) / 86400000);
  if (diff === 0) return;
  var d = night.toLocaleDateString('ko-KR', {month:'long', day:'numeric'});
  el.innerHTML = (diff > 0)
    ? '\\u26a0 이 예보는 <b>' + d + ' 밤</b> 기준으로 만들어졌습니다. ' + diff + '일 지났으니 '
      + '시각\\u00b7복사점 고도\\u00b7달 정보는 오늘 밤과 맞지 않습니다. '
      + '(유성우 자체는 며칠씩 이어지므로 경향은 참고할 수 있습니다)'
    : '\\u26a0 이 예보는 <b>' + d + ' 밤</b> 기준입니다 — 아직 그날이 오지 않았습니다.';
  el.style.display = 'block';
})();
</script>
""")
    if not fragment:
        H.append("</body></html>")
    return "".join(H)


# ────────────────────────────── 실행 ──────────────────────────────
def main():
    global LAT, LON, PLACE, NOCACHE
    a = sys.argv[1:]
    if "--nocache" in a:
        NOCACHE = True
    for k, setter in (("--lat", "lat"), ("--lon", "lon"), ("--place", "place")):
        if k in a:
            v = a[a.index(k) + 1]
            if setter == "lat": LAT = float(v)
            elif setter == "lon": LON = float(v)
            else: PLACE = v

    print(f"유성현황 생성 — 관측지 {PLACE} ({LAT}, {LON})")
    texts = [cached(f"{GMN_BASE}/data/traj_summary_data/daily/{n}", n) for n in GMN_FILES]
    meteors = parse_gmn(texts)
    if not meteors:
        print("[중단] GMN 데이터를 받지 못했습니다. 인터넷 연결을 확인하세요.")
        return 1
    print(f"  · 유성 {len(meteors):,}개 파싱")

    # 활동 중인 유성우 flux 그래프 (최대 2개)
    flux_imgs = []
    page = cached(FLUX_PAGE, "flux.html", max_age_h=6)
    if page:
        year = datetime.datetime.now(UTC).year
        urls = re.findall(rf'src="([^"]*flux_[A-Z]{{3}}_[^"]*year_{year}\.png)"', page)
        import collections
        top_codes = [c for c, _ in collections.Counter(m["shower"] for m in meteors).most_common()
                     if c != SPORADIC]
        def rank(u):                                  # 지금 가장 활발한 유성우 그래프를 먼저
            c = re.search(r"flux_([A-Z]{3})_", u)
            return top_codes.index(c.group(1)) if c and c.group(1) in top_codes else 99
        urls.sort(key=rank)
        for u in urls[:2]:
            full = urllib.parse.urljoin(FLUX_PAGE, u)
            code = re.search(r"flux_([A-Z]{3})_", u)
            raw = cached(full, os.path.basename(u).replace("=", "_"), max_age_h=3, binary=True)
            if raw:
                flux_imgs.append((f"{shower_name(code.group(1)) if code else ''} 활동량(ZHR) — 올해",
                                  base64.b64encode(raw).decode()))

    now = datetime.datetime.now(UTC)
    html = build_html(meteors, flux_imgs, now)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n생성 완료: {OUT}  ({len(html)//1024:,}KB)")

    # 웹에 올릴 공유본(본문만) — 클로드에게 "유성현황 올려줘" 할 때 이 파일을 쓴다
    share = build_html(meteors, flux_imgs, now, fragment=True)
    share_path = os.path.join(HERE, "유성현황_공유본.html")
    with open(share_path, "w", encoding="utf-8") as f:
        f.write(share)
    print(f"공유본 생성: {share_path}  ({len(share)//1024:,}KB)")

    # 웹사이트(GitHub Pages)용 — docs/index.html 이 그대로 인터넷에 올라간다
    docs = os.path.join(HERE, "docs")
    os.makedirs(docs, exist_ok=True)
    with open(os.path.join(docs, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"사이트용 생성: {os.path.join(docs, 'index.html')}")
    if "--noopen" not in a:
        try:
            os.startfile(OUT)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

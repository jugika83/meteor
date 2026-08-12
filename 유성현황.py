# -*- coding: utf-8 -*-
"""
유성현황 — 전 세계 유성 관측 현황판 + 오늘 밤 한국 관측 가이드
====================================================================
· 데이터: Global Meteor Network (전 세계 아마추어 카메라망, CC-BY 4.0)
          https://globalmeteornetwork.org/
· 하는 일: 오늘 밤 별·유성을 어디서 몇 시에 볼지 알려주는 한 장짜리 HTML을 만든다.
          방문자가 서울·대전·대구·부산·제주 중에서 고르면 그 지역 기준으로 전부 다시 그려진다.
          ① 오늘 밤 하늘  — 장소별 구름·미세먼지·종합점수 (브라우저가 실시간으로 받아옴)
          ② 하늘 시간표   — 일몰·천문박명·달·은하수·유성우별 시간대별 예상 개수
          ③ 어디로 가면 어두운가 — 전국 관측지 순위 (빛공해 추정)
          ④ 다음 유성우 달력
          ⑤~⑨ 최근 관측된 유성 세계지도·순위·밝은 유성·실시간 활동량
          ⑩ 실시간 관측 사이트 링크

· 예측 방식: 빛공해는 전국 도시 인구·거리로 추정(Walker 법칙)해 한계등급으로 환산하고,
            관측 개수는 IMO 표준식 HR = ZHR × sin(복사점고도) ÷ r^(6.5−한계등급) 로 계산.
            달이 뜬 시간대는 0.6배. 지형·구름은 반영하지 않으므로 순위 참고용.

사용법:  python 유성현황.py                    (서울 기준)
         python 유성현황.py --lat 35.18 --lon 129.08 --place 부산
         python 유성현황.py --nocache          (캐시 무시하고 새로 받기)

※ GMN '궤도' 데이터는 여러 나라 카메라를 대조해 계산하므로 관측 후 2~3일 지연된다.
   진짜 초 단위 실시간은 전파관측(2단계)·자체 카메라(3단계)에서 붙일 것.
"""
import os, sys, math, json, base64, datetime, re, urllib.parse

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

# 관측지 — 같은 폴더의 '관측지.txt' 로 고정한다. 파일이 없으면 서울, 명령줄 옵션이 최우선.
LAT, LON, PLACE = 37.5665, 126.9780, "서울"
NOCACHE = False
PLACE_FILE = os.path.join(HERE, "관측지.txt")


def load_place():
    """관측지.txt 읽기. 없으면 기본값 그대로. (한 번 정해두면 매번 옵션 안 써도 된다)"""
    global LAT, LON, PLACE
    if not os.path.exists(PLACE_FILE):
        return False
    try:
        for enc in ("utf-8-sig", "cp949"):
            try:
                body = open(PLACE_FILE, encoding=enc).read(); break
            except UnicodeDecodeError:
                continue
        for line in body.splitlines():
            line = line.split("#")[0].strip()
            if "=" not in line:
                continue
            k, v = [x.strip() for x in line.split("=", 1)]
            if k in ("장소", "place") and v:
                PLACE = v
            elif k in ("위도", "lat"):
                LAT = float(v)
            elif k in ("경도", "lon"):
                LON = float(v)
        return True
    except Exception as e:
        print(f"  (관측지.txt 를 읽지 못해 기본값으로 진행합니다: {e})")
        return False

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


# 연간 유성우 달력 — (코드, 이름, 극대 월, 일, 대략 ZHR, 한 줄 설명)
CALENDAR = [
    ("QUA", "사분의자리", 1, 3, 110, "새해 첫 대형 유성우. 극대가 몇 시간뿐이라 타이밍이 전부"),
    ("LYR", "거문고자리", 4, 22, 18, "봄철 대표. 가끔 폭발적으로 늘기도"),
    ("ETA", "물병자리 에타", 5, 6, 50, "핼리혜성 부스러기. 새벽에만 보임"),
    ("SDA", "물병자리 델타 남부", 7, 30, 25, "한여름, 페르세우스 직전 워밍업"),
    ("PER", "페르세우스자리", 8, 12, 100, "여름 최대 유성우. 밤새 보이고 밝은 것이 많음"),
    ("KCG", "백조자리 카파", 8, 18, 3, "수는 적지만 느리고 밝은 화구가 특징"),
    ("ORI", "오리온자리", 10, 21, 20, "핼리혜성 부스러기. 빠르고 흔적을 남김"),
    ("STA", "황소자리 남부", 10, 10, 5, "느리고 아주 밝은 화구가 특기"),
    ("NTA", "황소자리 북부", 11, 12, 5, "가을 화구 시즌"),
    ("LEO", "사자자리", 11, 17, 15, "33년 주기로 대폭발. 평년엔 조용"),
    ("GEM", "쌍둥이자리", 12, 14, 150, "연중 최대. 초저녁부터 밤새, 겨울이라 하늘도 맑음"),
    ("URS", "작은곰자리", 12, 22, 10, "한 해 마지막. 북극 근처라 밤새 보임"),
]


def calendar_rows(today, n=4):
    """오늘 이후 가까운 유성우 n개 — (이름, 날짜, D-day, ZHR, 설명)"""
    out = []
    for code, name, mo, da, zhr, note in CALENDAR:
        for y in (today.year, today.year + 1):
            try:
                d = datetime.date(y, mo, da)
            except ValueError:
                continue
            if (d - today).days >= -2:                   # 이틀 지난 것까지는 아직 진행 중으로
                out.append({"name": name, "date": f"{mo}월 {da}일", "dday": (d - today).days,
                            "zhr": zhr, "note": note, "year": y})
                break
    out.sort(key=lambda r: r["dday"])
    return out[:n]


def milkyway(today, lat, lon):
    """은하수 중심(궁수자리 방향, 적경 266.4° 적위 -28.9°)이 잘 보이는 시간대.
    고도 15° 이상이고 하늘이 어두운 시간을 찾는다."""
    base = datetime.datetime.combine(today, datetime.time(19, 0), tzinfo=KST)
    good = []
    for i in range(11):
        t = base + datetime.timedelta(hours=i)
        j = jd(t)
        alt = altitude(266.4, -28.9, j, lat, lon)
        dark = altitude(*sun_radec(j)[:2], j, lat, lon) < -18
        if alt >= 15 and dark:
            good.append((t, alt))
    if not good:
        return None
    best = max(good, key=lambda x: x[1])
    return {"from": good[0][0].strftime("%H시"), "to": good[-1][0].strftime("%H시"),
            "best": best[0].strftime("%H시"), "alt": round(best[1]),
            "dir": compass(azimuth(266.4, -28.9, jd(best[0]), lat, lon))}


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
    # ── 시·군 단위 보강 (2026-08-13): 시골 지역이 실제보다 어둡게 나오던 문제 보정 ──
    ("광명", 37.478, 126.865, 29), ("군포", 37.361, 126.935, 27),
    ("하남", 37.539, 127.215, 33), ("광주경기", 37.429, 127.255, 39),
    ("이천", 37.272, 127.435, 22), ("오산", 37.150, 127.077, 23),
    ("양주", 37.785, 127.046, 26), ("구리", 37.594, 127.130, 19),
    ("안성", 37.008, 127.280, 19), ("포천", 37.895, 127.200, 15),
    ("의왕", 37.345, 126.968, 16), ("여주", 37.298, 127.637, 11),
    ("양평", 37.492, 127.488, 12), ("가평", 37.831, 127.510, 6),
    ("동두천", 37.904, 127.060, 9), ("과천", 37.429, 126.988, 8),
    ("동해", 37.525, 129.114, 9), ("삼척", 37.450, 129.165, 6),
    ("홍천", 37.697, 127.889, 7), ("횡성", 37.492, 127.985, 5),
    ("평창", 37.371, 128.390, 4), ("영월", 37.184, 128.462, 4),
    ("정선", 37.381, 128.661, 3), ("철원", 38.147, 127.313, 4),
    ("양양", 38.075, 128.619, 3), ("고성강원", 38.380, 128.468, 3),
    ("제천", 37.133, 128.191, 13), ("음성", 36.940, 127.690, 9),
    ("진천", 36.855, 127.436, 8), ("옥천", 36.306, 127.571, 5),
    ("영동", 36.175, 127.776, 4), ("괴산", 36.815, 127.787, 4),
    ("단양", 36.985, 128.365, 3), ("보은", 36.489, 127.729, 3),
    ("서산", 36.785, 126.450, 17), ("당진", 36.890, 126.646, 17),
    ("논산", 36.187, 127.099, 12), ("공주", 36.447, 127.119, 10),
    ("보령", 36.333, 126.613, 10), ("홍성", 36.601, 126.661, 10),
    ("예산", 36.683, 126.845, 8), ("태안", 36.746, 126.298, 6),
    ("서천", 36.080, 126.691, 5), ("부여", 36.276, 126.910, 6),
    ("금산", 36.109, 127.488, 5), ("계룡", 36.274, 127.249, 4),
    ("익산", 35.948, 126.958, 27), ("군산", 35.968, 126.737, 26),
    ("완주", 35.905, 127.162, 9), ("김제", 35.804, 126.881, 8),
    ("부안", 35.732, 126.733, 5), ("고창", 35.436, 126.702, 5),
    ("무주", 36.007, 127.661, 2), ("임실", 35.618, 127.289, 3),
    ("광양", 34.940, 127.696, 15), ("나주", 35.016, 126.711, 11),
    ("무안", 34.990, 126.482, 9), ("화순", 35.064, 126.986, 6),
    ("해남", 34.573, 126.599, 6), ("영광", 35.277, 126.512, 5),
    ("고흥", 34.611, 127.285, 6), ("담양", 35.321, 126.988, 4),
    ("영암", 34.800, 126.697, 5), ("완도", 34.311, 126.755, 5),
    ("구례", 35.202, 127.463, 2), ("보성", 34.771, 127.080, 4),
    ("경산", 35.825, 128.741, 26), ("김천", 36.140, 128.114, 14),
    ("영천", 35.973, 128.939, 10), ("상주", 36.411, 128.159, 9),
    ("문경", 36.587, 128.187, 7), ("칠곡", 35.996, 128.402, 11),
    ("성주", 35.919, 128.283, 4), ("청도", 35.648, 128.734, 4),
    ("영덕", 36.415, 129.366, 3), ("울진", 36.993, 129.400, 5),
    ("봉화", 36.893, 128.732, 3), ("예천", 36.658, 128.453, 5),
    ("의성", 36.353, 128.697, 5), ("청송", 36.436, 129.057, 2),
    ("사천", 35.004, 128.064, 11), ("거창", 35.687, 127.910, 6),
    ("창녕", 35.545, 128.492, 6), ("함안", 35.272, 128.406, 6),
    ("남해", 34.838, 127.892, 4), ("하동", 35.067, 127.751, 4),
    ("산청", 35.415, 127.874, 3), ("함양", 35.520, 127.725, 3),
    ("고성경남", 34.973, 128.322, 5), ("의령", 35.322, 128.262, 2),
    ("서귀포", 33.254, 126.560, 18), ("성산", 33.450, 126.916, 1),
    ("한림", 33.412, 126.266, 2), ("표선", 33.326, 126.833, 1),
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
    ("영양 반딧불이공원", 36.830, 129.170, "아시아 최초 국제밤하늘보호공원(수비면)"),
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
    ("제주 사려니숲길", 33.417, 126.638, "중산간 숲길"),
    ("제주 성산일출봉", 33.458, 126.942, "동쪽 바다 수평선"),
    ("제주 송악산", 33.199, 126.290, "남서쪽 해안"),
    ("논산 대둔산", 36.135, 127.330, "충청권에서 가장 가까운 산간"),
    ("보은 속리산 말티재", 36.520, 127.820, "충북 고갯길"),
    ("서산 간월도", 36.635, 126.363, "서해 수평선"),
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


# 사이트에서 고를 수 있는 도시 (이름, 위도, 경도)
PICK_CITIES = [
    ("서울", 37.5665, 126.9780), ("대전", 36.3504, 127.3845),
    ("대구", 35.8714, 128.6014), ("부산", 35.1800, 129.0750),
    ("제주", 33.4996, 126.5312),
]


def city_report(place, lat, lon, stats, today):
    """도시 하나의 오늘 밤 예보 + 관측지 추천을 통째로 계산해 dict로.
    브라우저에서 도시를 바꿔 누르면 이 dict를 그대로 그린다."""
    ni = night_info(today, lat, lon)
    lm = limiting_mag(light_index(lat, lon))
    hhmm = lambda t: t.astimezone(KST).strftime("%H:%M") if t else "—"
    base = datetime.datetime.combine(today, datetime.time(19, 0), tzinfo=KST)

    showers = []
    for s in stats:
        hours = []
        for i in range(11):                              # 19시 ~ 05시
            t = base + datetime.timedelta(hours=i)
            j = jd(t)
            alt = altitude(s["ra"], s["dec"], j, lat, lon)
            dark = altitude(*sun_radec(j)[:2], j, lat, lon) < -18
            moon_up = ni["moon_alt"](t) > 0
            hr = None
            if s["zhr"] and dark:                        # 박명 중엔 사실상 관측 불가
                hr = round(hourly_rate(s["zhr"], s["r"], alt, lm) * (0.6 if moon_up else 1.0), 1)
            hours.append({"h": t.strftime("%H시"), "alt": round(alt, 1), "dark": dark,
                          "moon": moon_up, "hr": hr,
                          "eff": round(max(0.0, math.sin(math.radians(alt))), 3)})
        bi = max(range(11), key=lambda i: (hours[i]["dark"],
                                           hours[i]["eff"] * (0.55 if hours[i]["moon"] else 1.0)))
        bt = base + datetime.timedelta(hours=bi)
        showers.append({
            "name": s["name"], "color": s["color"], "n": s["n"], "peak": s["peak"],
            "v": round(s["v"]), "ra": round(s["ra"]), "dec": round(s["dec"]),
            "zhr": s["zhr"], "hours": hours,
            "best": {"h": hours[bi]["h"], "alt": round(hours[bi]["alt"]),
                     "eff": round(hours[bi]["eff"] * 100), "moon": hours[bi]["moon"],
                     "hr": hours[bi]["hr"],
                     "dir": compass(azimuth(s["ra"], s["dec"], jd(bt), lat, lon))},
        })

    # ── 어디로 가면 잘 보이나 ──
    spots = None
    if showers:
        s0, g0 = showers[0], stats[0]
        bi = [h["h"] for h in s0["hours"]].index(s0["best"]["h"])
        bt = base + datetime.timedelta(hours=bi)
        moon_f = 0.6 if s0["best"]["moon"] else 1.0
        zhr, rr = (g0["zhr"], g0["r"]) if g0["zhr"] else (100, 2.2)
        home_hr = hourly_rate(zhr, rr, s0["best"]["alt"], lm) * moon_f

        cand = []
        for name, sl, sn, desc in SITES:
            d = haversine(lat, lon, sl, sn)
            if d > 150:                                  # 당일 왕복 가능한 범위만
                continue
            slm = limiting_mag(light_index(sl, sn))
            hr = hourly_rate(zhr, rr, altitude(g0["ra"], g0["dec"], jd(bt), sl, sn), slm) * moon_f
            cand.append({"name": name, "desc": desc, "d": round(d), "lm": round(slm, 1),
                         "hr": round(hr), "dir": compass(bearing(lat, lon, sl, sn)),
                         "bortle": bortle(slm), "lat": sl, "lon": sn,
                         "gain": round(hr / home_hr, 1) if home_hr > 0 else 0})
        cand.sort(key=lambda c: -c["hr"])
        near = [c for c in cand if c["d"] <= 60][:3] or cand[:1]
        far = [c for c in cand if c not in near][:5]

        worth = ""
        if near and cand and near[0]["hr"] > 0:
            extra = cand[0]["hr"] / near[0]["hr"]
            worth = ("가까운 곳과 먼 곳 차이가 크지 않으니 <b>가까운 데서 오래 보는 편</b>이 낫습니다."
                     if extra < 1.25 else
                     f"멀리 가면 {extra:.1f}배 더 보입니다 — 시간이 되면 나갈 값어치가 있습니다.")

        dk_txt = ""
        dk = darkest_nearby(lat, lon, 120)
        if dk:
            dlat, dlon, didx, dd = dk
            nearest = min(SITES, key=lambda s: haversine(dlat, dlon, s[1], s[2]))
            nd = haversine(dlat, dlon, nearest[1], nearest[2])
            where = (f"{nearest[0]} 부근" if nd < 20
                     else f"{compass(bearing(lat, lon, dlat, dlon))}쪽 산간")
            dk_txt = (f"반경 120km 안에서 계산상 가장 어두운 지점은 <b>{esc(where)}</b> "
                      f"({dlat:.2f}, {dlon:.2f}) — {esc(place)}에서 {dd:.0f}km, "
                      f"예상 한계등급 {limiting_mag(didx):.1f}등급.")

        spots = {"homeHr": round(home_hr), "homeLm": round(lm, 1), "homeBortle": bortle(lm),
                 "near": near, "far": far, "best": cand[0] if cand else None,
                 "worth": worth, "darkest": dk_txt, "dir": s0["best"]["dir"],
                 # 날씨를 붙일 후보들 (브라우저가 이 좌표로 예보를 받아 온다)
                 "wx": [{"name": "지금 계신 곳", "lat": lat, "lon": lon, "d": 0,
                         "lm": round(lm, 1), "home": True}] +
                       [{"name": c["name"], "lat": c["lat"], "lon": c["lon"], "d": c["d"],
                         "lm": c["lm"], "home": False} for c in (near + far)]}

    # ── 한 줄 요약 ──
    moon_pct = ni["illum"] * 100
    moon_txt = ("달 없음 — 최고 조건" if moon_pct < 15 else "달빛 약간" if moon_pct < 40 else
                "달빛 방해 있음" if moon_pct < 70 else "달이 밝아 불리")
    if showers:
        dp = showers[0]["peak"]
        when = ("오늘이 극대일" if dp == 0 else f"극대 {dp}일 전" if dp and 0 < dp <= 5 else
                f"극대 {-dp}일 지남" if dp and -5 <= dp < 0 else "활동 중")
        verdict = ("최고 조건" if moon_pct < 15 and dp is not None and abs(dp) <= 1 else
                   "볼 만함" if moon_pct < 40 else "달빛 때문에 아쉬움")
        banner = {"title": f"{showers[0]['name']} 유성우 · {when}",
                  "sub": (f"달 밝기 {moon_pct:.0f}% · 추천 {showers[0]['best']['h']}쯤 "
                          f"{showers[0]['best']['dir']}쪽 하늘 — <b>{verdict}</b>")}
    else:
        banner = {"title": "지금은 큰 유성우가 없습니다",
                  "sub": f"산발유성 위주입니다. 달 밝기 {moon_pct:.0f}%."}

    return {
        "place": place, "lat": lat, "lon": lon,
        "night": {"sunset": hhmm(ni["sunset"]), "dusk": hhmm(ni["dusk"]),
                  "dawn": hhmm(ni["dawn"]), "moonrise": hhmm(ni["moonrise"]),
                  "moonset": hhmm(ni["moonset"]), "illum": round(moon_pct),
                  "moontext": moon_txt},
        "banner": banner, "showers": showers, "spots": spots,
        "milkyway": milkyway(today, lat, lon),
    }


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
    # 유성우별 복사점·속도는 도시와 무관하므로 한 번만 구한다
    import statistics
    stats = []
    for code in ranked[:3]:                          # 상위 3개만 (나머지는 ⑤ 표에서)
        ms = [m for m in meteors if m["shower"] == code]
        if len(ms) < 100:
            continue
        zhr, rr = SHOWER_ZHR.get(code, (None, None))
        stats.append({"code": code, "name": shower_name(code), "color": color[code],
                      "n": len(ms), "peak": days_to_peak(code, today),
                      "ra": statistics.median(m["ra"] for m in ms),
                      "dec": statistics.median(m["dec"] for m in ms),
                      "v": statistics.median(m["v"] for m in ms), "zhr": zhr, "r": rr})
    stats.sort(key=lambda s: -s["n"])

    # 고를 수 있는 도시 전부를 미리 계산해 페이지에 담는다 (클릭하면 즉시 전환)
    picks = list(PICK_CITIES)
    if PLACE not in [p[0] for p in picks]:           # 관측지.txt가 5개 밖이면 그것도 추가
        picks.insert(0, (PLACE, LAT, LON))
    reports = {}
    for name, la, lo in picks:
        print(f"  · {name} 계산 중...")
        reports[name] = city_report(name, la, lo, stats, today)
    default_city = PLACE if PLACE in reports else picks[0][0]
    og_city = reports[default_city]

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
    /* 도시 고르기 */
    .picker{background:#131a30;border:1px solid #33406e;border-radius:12px;padding:18px;margin:14px 0}
    .picklbl{font-size:16px;font-weight:700;margin-bottom:12px}
    .pickrow{display:flex;flex-wrap:wrap;gap:8px}
    .pick{font:inherit;font-size:16px;font-weight:700;color:#cfd8ee;background:#1d2540;
      border:1px solid #33406e;border-radius:99px;padding:10px 22px;cursor:pointer;
      transition:background .12s,color .12s,border-color .12s}
    .pick:hover{background:#26314f;color:#fff}
    .pick:focus-visible{outline:2px solid #7cc4ff;outline-offset:2px}
    .pick.on{background:#ffd166;border-color:#ffd166;color:#20160a}
    .hint{color:#8b97b5;font-size:13px;margin-top:10px}
    """

    # 카톡 등에 링크를 붙였을 때 보이는 미리보기 문구 (기본 도시 기준)
    s0 = og_city["showers"][0] if og_city["showers"] else None
    og_desc = (f"{s0['name']} 유성우 · 서울·대전·대구·부산·제주 중에서 고르면 "
               f"그 지역에서 잘 보이는 장소와 시간을 알려드립니다") if s0 else \
              "오늘 밤 유성 관측 예보 — 어디서 몇 시에 보면 되는지"
    head = ("" if fragment else
            '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta property="og:type" content="website">'
            f'<meta property="og:locale" content="ko_KR">'
            f'<meta property="og:title" content="🌠 유성현황 — 오늘 밤 어디서 몇 시에">'
            f'<meta property="og:description" content="{esc(og_desc)}">'
            f'<meta property="og:image" content="https://jugika83.github.io/meteor/icon-512.png">'
            f'<meta name="description" content="{esc(og_desc)}">'
            f'<meta name="theme-color" content="#0b1020">'
            f'<link rel="manifest" href="manifest.json">'
            f'<link rel="icon" href="favicon.png" type="image/png">'
            f'<link rel="apple-touch-icon" href="icon-192.png">')
    open_body = "" if fragment else "</head><body>"
    H = [f"""{head}
<title>유성현황 — 오늘 밤 유성 보기</title><style>{css}</style>{open_body}<div class="wrap">
<h1>🌠 유성현황</h1>
<div class="sub">생성 {gen_time.astimezone(KST):%Y-%m-%d %H:%M} KST ·
 데이터 <a href="{GMN_BASE}" target="_blank">Global Meteor Network</a> (CC BY 4.0)</div>
"""]

    # 날짜가 지나면 스스로 알려주는 안내 (공유받은 친구가 며칠 뒤 열 수 있으므로)
    H.append(f'<div id="stale" data-night="{today:%Y-%m-%d}"></div>')

    # ── 도시 고르기 ──
    H.append('<div class="picker"><div class="picklbl">📍 어디에서 보실 건가요?</div><div class="pickrow">')
    for name, la, lo in picks:
        H.append(f'<button type="button" class="pick" data-city="{esc(name)}">{esc(name)}</button>')
    H.append('</div><div class="hint" id="pickhint">한 곳을 누르면 그 지역 기준으로 '
             '오늘 밤 몇 시에 어디로 가면 잘 보이는지 알려드립니다.</div></div>')

    # 도시별 내용이 그려질 자리
    H.append(f'<div id="report" data-night-label="{today:%m월 %d일}" hidden></div>')

    # 도시별 계산 결과를 통째로 심어둔다 (클릭하면 즉시 전환, 인터넷 불필요)
    payload = json.dumps(reports, ensure_ascii=False).replace("</", "<\\/")
    H.append(f'<script id="citydata" type="application/json">{payload}</script>')
    cal = json.dumps(calendar_rows(today), ensure_ascii=False).replace("</", "<\\/")
    H.append(f'<script id="caldata" type="application/json">{cal}</script>')
    H.append("""
<script>
/* ── 오늘 밤 실제 하늘: 구름·미세먼지·습도를 받아 장소별 점수를 매긴다 ──
   날씨는 시시각각 바뀌므로 페이지를 열 때마다 새로 받아온다.
   출처: Open-Meteo (무료, 키 불필요) */
(function(){
  window.MeteorWx = {};
  var CACHE = {};

  function nightHours(){            // 오늘 밤 21시~다음날 04시 (한국시각)
    var now = new Date();
    var kst = new Date(now.getTime() + now.getTimezoneOffset()*60000 + 9*3600000);
    var d = new Date(kst);
    if (kst.getHours() < 12) d.setDate(d.getDate() - 1);   // 새벽이면 어젯밤이 '오늘 밤'
    var ymd = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
    var nx = new Date(d.getTime() + 86400000);
    var ymd2 = nx.getFullYear() + '-' + String(nx.getMonth()+1).padStart(2,'0') + '-' + String(nx.getDate()).padStart(2,'0');
    var hs = [];
    [21,22,23].forEach(function(h){ hs.push(ymd + 'T' + String(h).padStart(2,'0') + ':00'); });
    [0,1,2,3,4].forEach(function(h){ hs.push(ymd2 + 'T' + String(h).padStart(2,'0') + ':00'); });
    return hs;
  }

  function pick(times, values, want){
    var out = [];
    want.forEach(function(t){
      var i = times.indexOf(t);
      out.push(i >= 0 ? values[i] : null);
    });
    return out;
  }

  function avg(a){
    var v = a.filter(function(x){ return x !== null && x !== undefined; });
    if (!v.length) return null;
    return v.reduce(function(s,x){ return s+x; },0) / v.length;
  }

  /* 오늘 밤 점수 0~100 — 구름이 압도적으로 중요하고, 그다음이 하늘 어둡기 */
  function score(cloud, lm, pm10, dewGap){
    if (cloud === null) return null;
    var clear = Math.pow(1 - cloud/100, 1.3);                 // 구름 0%면 1, 50%면 0.41
    var dark  = Math.max(0, Math.min(1, (lm - 3.8) / 2.8));   // 3.8등급 0, 6.6등급 1
    var air   = pm10 === null ? 1 : Math.max(0.75, Math.min(1, 1 - (pm10 - 30) / 150));
    return Math.round(100 * clear * (0.55 + 0.45*dark) * air);
  }

  function grade(s){
    if (s === null) return {t:'—', c:'#7d8597'};
    if (s >= 70) return {t:'최상', c:'#80ed99'};
    if (s >= 50) return {t:'좋음', c:'#a7e34d'};
    if (s >= 30) return {t:'보통', c:'#ffd166'};
    if (s >= 15) return {t:'나쁨', c:'#ff9e6d'};
    return {t:'관측 불가', c:'#ff6b6b'};
  }

  MeteorWx.load = function(sites){
    var key = sites.map(function(s){ return s.lat+','+s.lon; }).join(';');
    if (CACHE[key]) return Promise.resolve(CACHE[key]);
    var lats = sites.map(function(s){ return s.lat; }).join(',');
    var lons = sites.map(function(s){ return s.lon; }).join(',');
    var base = 'https://api.open-meteo.com/v1/forecast?latitude=' + lats + '&longitude=' + lons +
      '&hourly=cloud_cover,relative_humidity_2m,dew_point_2m,temperature_2m,wind_speed_10m' +
      '&timezone=Asia%2FSeoul&forecast_days=2&past_days=1';   // 자정 넘어 봐도 초저녁 시간대가 나오도록
    var air = 'https://air-quality-api.open-meteo.com/v1/air-quality?latitude=' + lats + '&longitude=' + lons +
      '&hourly=pm10&timezone=Asia%2FSeoul&forecast_days=2&past_days=1';
    var want = nightHours();

    return Promise.all([
      fetch(base).then(function(r){ return r.json(); }),
      fetch(air).then(function(r){ return r.json(); }).catch(function(){ return null; })
    ]).then(function(res){
      var w = res[0], a = res[1];
      if (!Array.isArray(w)) w = [w];
      if (a && !Array.isArray(a)) a = [a];
      var out = sites.map(function(s, i){
        var h = (w[i] || {}).hourly;
        if (!h) return Object.assign({}, s, {score: null});
        var cloud = pick(h.time, h.cloud_cover, want);
        var hum   = pick(h.time, h.relative_humidity_2m, want);
        var temp  = pick(h.time, h.temperature_2m, want);
        var dew   = pick(h.time, h.dew_point_2m, want);
        var pm    = (a && a[i] && a[i].hourly) ? avg(pick(a[i].hourly.time, a[i].hourly.pm10, want)) : null;
        var cAvg = avg(cloud);
        var gap = null;
        var tv = temp.filter(function(x){return x!==null;}), dv = dew.filter(function(x){return x!==null;});
        if (tv.length && dv.length) gap = avg(tv) - avg(dv);
        return Object.assign({}, s, {
          cloud: cAvg === null ? null : Math.round(cAvg),
          cloudHours: cloud,
          hum: avg(hum) === null ? null : Math.round(avg(hum)),
          pm10: pm === null ? null : Math.round(pm),
          dewGap: gap === null ? null : Math.round(gap*10)/10,
          score: score(cAvg, s.lm, pm === null ? null : Math.round(pm), gap)
        });
      });
      CACHE[key] = out;
      return out;
    });
  };

  MeteorWx.grade = grade;
  MeteorWx.hourLabels = ['21','22','23','00','01','02','03','04'];
})();
</script>
""")

    H.append("""
<script>
(function(){
  var DATA, CAL, out = document.getElementById('report');
  try {
    DATA = JSON.parse(document.getElementById('citydata').textContent);
    CAL  = JSON.parse(document.getElementById('caldata').textContent);
  } catch(e) { return; }
  var KEY = 'meteor-city', NIGHT = out.dataset.nightLabel, CUR = null;

  function esc(s){ var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
  function n0(v){ return Math.round(v); }

  function bars(sh){
    var max = 1;
    sh.hours.forEach(function(h){ if (h.hr && h.hr > max) max = h.hr; });
    return sh.hours.map(function(h){
      var useHr = (h.hr !== null && h.hr !== undefined);
      var w = useHr ? (h.hr / max * 100) : Math.max(0, Math.min(100, h.alt / 90 * 100));
      var cls = 'hbar' + (h.dark ? ' dark' : '') + (h.moon && h.dark ? ' moon' : '');
      var right = useHr ? (n0(h.hr) + '개/시')
                        : (h.dark ? ((h.alt > 0 ? '+' : '') + n0(h.alt) + '°') : '박명');
      return '<div class="hr"><span class="lbl">' + h.h + '</span>' +
             '<span class="' + cls + '"><i style="width:' + w.toFixed(0) + '%"></i></span>' +
             '<span class="lbl r">' + right + (h.moon ? ' 🌙' : '') + '</span></div>';
    }).join('');
  }

  function showerCard(sh){
    var peak = '';
    if (sh.peak !== null && sh.peak !== undefined) {
      var t = (sh.peak === 0) ? 'D-DAY' : (sh.peak > 0 ? 'D-' + sh.peak : 'D+' + (-sh.peak));
      peak = '<span class="chip" style="background:#5a3a12;color:#ffd166">극대 ' + t + '</span>';
    }
    var b = sh.best;
    var note = '<div class="note">추천 시간 <b style="color:#ffd166">' + b.h + '</b>' +
      ' — 이때 복사점이 <b>' + b.alt + '°</b> 높이(' + b.dir + '쪽 하늘), 관측 효율 ' + b.eff + '%' +
      (b.moon ? ' · 달 떠 있음' : '') + '</div>';
    var foot = sh.zhr ? ('<div class="note">막대 = <b>구름이 없다고 볼 때 눈으로 보일 시간당 개수</b> ' +
      '(표준 활동량 ZHR ' + sh.zhr + ' 기준, 이 지역 빛공해 반영). 실제로는 위의 구름 예보를 함께 보세요.</div>') : '';
    return '<div class="card">' +
      '<div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px">' +
      '<div><span class="dot" style="background:' + sh.color + '"></span>' +
      '<b style="font-size:17px">' + esc(sh.name) + '</b> ' + peak +
      '<span class="chip">최근 ' + sh.n.toLocaleString() + '개 검출</span>' +
      '<span class="chip">진입속도 ' + sh.v + ' km/s</span></div>' +
      '<div class="lbl">복사점 적경 ' + sh.ra + '° 적위 ' + (sh.dec >= 0 ? '+' : '') + sh.dec + '°</div>' +
      '</div>' + note + '<div style="margin-top:10px">' + bars(sh) + '</div>' + foot + '</div>';
  }

  function spotRow(c, hi){
    return '<tr' + (hi ? ' style="background:#16203c"' : '') + '>' +
      '<td><b>' + esc(c.name) + '</b><br><span class="lbl">' + esc(c.desc) + '</span></td>' +
      '<td class="r">' + c.dir + ' ' + c.d + 'km</td>' +
      '<td class="r">' + c.lm.toFixed(1) + '등급</td>' +
      '<td class="r"><span class="lbl">' + esc(c.bortle) + '</span></td>' +
      '<td class="r" style="color:#ffd166"><b>' + c.hr + '개/시</b></td>' +
      '<td class="r">' + c.gain.toFixed(1) + '배</td></tr>';
  }

  /* ── 오늘 밤 실제 하늘(날씨) ── */
  function wxSkeleton(){
    return '<h2>① 오늘 밤 하늘 — 지금 예보 기준</h2>' +
      '<div class="card" id="wxcard"><div class="lbl">구름·미세먼지 예보를 받아오는 중입니다...</div></div>';
  }

  function cloudBar(v){
    if (v === null || v === undefined) return '<span class="hbar"></span>';
    var col = v < 20 ? '#4cc9f0' : (v < 50 ? '#7cc4ff' : (v < 80 ? '#8a6f3a' : '#6b3a3a'));
    return '<span class="hbar"><i style="width:' + v + '%;background:' + col + '"></i></span>';
  }

  function renderWx(list, place){
    var card = document.getElementById('wxcard');
    if (!card) return;
    var ok = list.filter(function(s){ return s.score !== null; });
    if (!ok.length) {
      card.innerHTML = '<div class="lbl">날씨 예보를 불러오지 못했습니다. ' +
        '(오프라인 사본이거나 네트워크가 막혀 있을 수 있습니다)</div>';
      return;
    }
    var sorted = ok.slice().sort(function(a,b){ return b.score - a.score; });
    var top = sorted[0], home = list.filter(function(s){ return s.home; })[0];
    var near60 = sorted.filter(function(s){ return !s.home && s.d <= 60; })[0];
    if (near60 && near60.name === top.name) near60 = null;   // 1등과 같으면 중복이라 안 보여준다
    var g = window.MeteorWx.grade(top.score), gh = window.MeteorWx.grade(home ? home.score : null);

    var h = [];
    h.push('<div class="grid g4">' +
      '<div><div class="lbl">오늘 밤 가장 좋은 곳</div>' +
      '<div class="big" style="color:' + g.c + '">' + esc(top.home ? place : top.name) + '</div>' +
      '<div class="lbl">' + (top.home ? '지금 계신 곳' : top.d + 'km · ' + '차로 나가야 함') + '</div></div>' +
      '<div><div class="lbl">그곳의 하늘</div>' +
      '<div class="big" style="color:' + g.c + '">' + g.t + '</div>' +
      '<div class="lbl">100점 만점에 ' + top.score + '점</div></div>' +
      (near60 ? '<div><div class="lbl">60km 이내 최선</div>' +
      '<div class="big" style="color:' + window.MeteorWx.grade(near60.score).c + '">' +
      esc(near60.name) + '</div>' +
      '<div class="lbl">' + near60.d + 'km · ' + near60.score + '점 · 구름 ' + near60.cloud + '%</div></div>'
      : '<div><div class="lbl">구름</div><div class="big">' + top.cloud + '%</div>' +
      '<div class="lbl">21시~새벽 4시 평균</div></div>') +
      '<div><div class="lbl">' + esc(place) + '에서 그냥 본다면</div>' +
      '<div class="big" style="color:' + gh.c + '">' + gh.t + '</div>' +
      '<div class="lbl">' + (home && home.score !== null ? home.score + '점 · 구름 ' + home.cloud + '%' : '—') + '</div></div>' +
      '</div>');

    // 시간대별 구름
    var labels = window.MeteorWx.hourLabels;
    h.push('<div style="margin-top:14px"><div class="lbl" style="margin-bottom:6px">' +
      esc(top.home ? place : top.name) + ' 시간대별 구름</div>');
    labels.forEach(function(lb, i){
      var v = top.cloudHours ? top.cloudHours[i] : null;
      h.push('<div class="hr"><span class="lbl">' + lb + '시</span>' + cloudBar(v) +
        '<span class="lbl r">' + (v === null ? '—' : v + '%') + '</span></div>');
    });
    h.push('</div>');

    // 장소별 표
    h.push('<table style="margin-top:14px">' +
      '<tr><th>장소</th><th class="r">거리</th><th class="r">구름</th><th class="r">미세먼지</th>' +
      '<th class="r">하늘 어둡기</th><th class="r">종합</th></tr>');
    sorted.forEach(function(s){
      var sg = window.MeteorWx.grade(s.score);
      h.push('<tr' + (s.home ? ' style="background:#16203c"' : '') + '>' +
        '<td><b>' + esc(s.home ? place + ' (지금 계신 곳)' : s.name) + '</b></td>' +
        '<td class="r">' + (s.home ? '—' : s.d + 'km') + '</td>' +
        '<td class="r">' + (s.cloud === null ? '—' : s.cloud + '%') + '</td>' +
        '<td class="r">' + (s.pm10 === null ? '—' : s.pm10 + 'µg') + '</td>' +
        '<td class="r">' + s.lm.toFixed(1) + '등급</td>' +
        '<td class="r"><b style="color:' + sg.c + '">' + s.score + '점 ' + sg.t + '</b></td></tr>');
    });
    h.push('</table>');

    // 결로 경고
    var dewWarn = sorted.filter(function(s){ return s.dewGap !== null && s.dewGap < 2; });
    if (dewWarn.length) {
      h.push('<div class="note" style="color:#ffcf8f">💧 기온과 이슬점 차이가 ' +
        dewWarn[0].dewGap + '°C밖에 안 됩니다 — 렌즈·안경에 이슬이 맺히기 쉬운 밤입니다. ' +
        '수건이나 김서림 방지 용품을 챙기세요.</div>');
    }
    h.push('<div class="note">종합 점수 = 구름(가장 큼) × 하늘 어둡기 × 미세먼지로 계산한 값입니다. ' +
      '구름이 80%를 넘으면 아무리 어두운 곳도 소용없기 때문에 구름에 가장 큰 비중을 뒀습니다. ' +
      '날씨 출처: <a href="https://open-meteo.com/" target="_blank">Open-Meteo</a> · ' +
      '페이지를 열 때마다 새로 받아옵니다.</div>');
    card.innerHTML = h.join('');
  }

  function loadWx(d){
    if (!d.spots || !d.spots.wx || !window.MeteorWx) return;
    var mine = CUR;
    window.MeteorWx.load(d.spots.wx).then(function(list){
      if (CUR !== mine) return;                 // 그새 다른 도시를 눌렀으면 무시
      renderWx(list, d.place);
    }).catch(function(){
      var card = document.getElementById('wxcard');
      if (card) card.innerHTML = '<div class="lbl">날씨 예보를 불러오지 못했습니다.</div>';
    });
  }

  function milkyCard(mw){
    if (!mw) return '';
    return '<div class="card"><b style="font-size:17px">🌌 은하수</b>' +
      '<div class="note">오늘 밤 <b style="color:#ffd166">' + mw.from + ' ~ ' + mw.to + '</b> 사이에 ' +
      '은하수 중심(궁수자리 방향)이 지평선 위로 올라옵니다. ' +
      '<b>' + mw.best + '</b>쯤 가장 높아지며(' + mw.alt + '°), ' + mw.dir + '쪽 하늘입니다. ' +
      '달이 없고 도시 불빛에서 벗어나면 맨눈으로도 뿌연 띠가 보입니다.</div></div>';
  }

  function calCard(){
    if (!CAL || !CAL.length) return '';
    var rows = CAL.map(function(c){
      var dd = c.dday === 0 ? '<b style="color:#ffd166">오늘</b>' :
               (c.dday < 0 ? '진행 중' : 'D-' + c.dday);
      return '<tr><td><b>' + esc(c.name) + '</b><br><span class="lbl">' + esc(c.note) + '</span></td>' +
        '<td class="r">' + c.date + '</td><td class="r">' + dd + '</td>' +
        '<td class="r">시간당 ' + c.zhr + '개</td></tr>';
    }).join('');
    return '<h2>④ 다음 유성우는 언제</h2><div class="card"><table>' +
      '<tr><th>유성우</th><th class="r">극대일</th><th class="r">남은 날</th><th class="r">최대 활동량</th></tr>' +
      rows + '</table><div class="note">최대 활동량은 하늘이 완벽할 때의 이론값(ZHR)입니다. ' +
      '도시에서는 이보다 훨씬 적게 보이고, 달이 밝으면 더 줄어듭니다.</div></div>';
  }

  function render(city){
    var d = DATA[city];
    if (!d) return;
    CUR = city;
    var h = [];

    h.push('<div class="card" style="border-color:#3d4a7a;background:#16203c">' +
      '<b style="color:#ffd166;font-size:20px">' + esc(d.banner.title) + '</b><br>' +
      d.banner.sub + '</div>');

    h.push(wxSkeleton());

    var nt = d.night;
    h.push('<h2>② 오늘 밤 ' + esc(d.place) + ' 하늘 시간표 · ' + NIGHT + ' 밤</h2>' +
      '<div class="card"><div class="grid g4">' +
      '<div><div class="lbl">일몰</div><div class="big">' + nt.sunset + '</div></div>' +
      '<div><div class="lbl">완전히 어두워짐(천문박명 끝)</div><div class="big">' + nt.dusk + '</div></div>' +
      '<div><div class="lbl">새벽 밝아지기 시작</div><div class="big">' + nt.dawn + '</div></div>' +
      '<div><div class="lbl">달 밝기 · ' + esc(nt.moontext) + '</div><div class="big">' + nt.illum + '%</div>' +
      '<div class="lbl">월출 ' + nt.moonrise + ' · 월몰 ' + nt.moonset + '</div></div>' +
      '</div></div>');

    h.push(milkyCard(d.milkyway));

    if (d.showers.length) {
      d.showers.forEach(function(sh){ h.push(showerCard(sh)); });
      h.push('<div class="note">파란 막대 = 하늘이 완전히 어두운 시간, 갈색 = 달이 떠 있어 손해 보는 시간, ' +
        '회색 = 아직 박명. 복사점 위치는 최근 관측의 중앙값이라 실제와 몇 도 차이날 수 있습니다.</div>');
    } else {
      h.push('<div class="card warn">지금은 큰 유성우가 없습니다. 산발유성만 시간당 몇 개 보이는 시기입니다.</div>');
    }

    var sp = d.spots;
    if (sp) {
      h.push('<h2>③ 어디로 가면 어두운가 — ' + esc(d.place) + ' 기준</h2>' +
        '<div class="card"><div class="grid g4">' +
        '<div><div class="lbl">지금 계신 곳(' + esc(d.place) + ') 하늘</div>' +
        '<div class="big">' + sp.homeHr + '개<span style="font-size:15px">/시간</span></div>' +
        '<div class="lbl">한계등급 ' + sp.homeLm.toFixed(1) + ' · 보틀 ' + esc(sp.homeBortle) + '</div></div>' +
        '<div><div class="lbl">' + (sp.near[0].d <= 60 ? '60km 이내 최선' : '가장 가까운 추천지') + '</div>' +
        '<div class="big">' + sp.near[0].hr + '개<span style="font-size:15px">/시간</span></div>' +
        '<div class="lbl">' + esc(sp.near[0].name) + ' · ' + sp.near[0].d + 'km</div></div>' +
        (sp.best && sp.best.name !== sp.near[0].name ?
        '<div><div class="lbl">더 멀리 나간다면</div>' +
        '<div class="big">' + sp.best.hr + '개<span style="font-size:15px">/시간</span></div>' +
        '<div class="lbl">' + esc(sp.best.name) + ' · ' + sp.best.d + 'km</div></div>' : '') +
        '<div><div class="lbl">보는 방향</div><div class="big">' + sp.dir + '쪽</div>' +
        '<div class="lbl">' + d.showers[0].best.h + ' 기준 고도 ' + d.showers[0].best.alt + '°</div></div>' +
        '</div></div>');

      var rows = sp.near.map(function(c){ return spotRow(c, true); }).join('') +
                 sp.far.map(function(c){ return spotRow(c, false); }).join('');
      h.push('<div class="card"><table>' +
        '<tr><th>관측지</th><th class="r">방향·거리</th><th class="r">예상 한계등급</th>' +
        '<th class="r">보틀</th><th class="r">예상 관측</th><th class="r">지금 위치 대비</th></tr>' +
        rows + '</table>' +
        '<div class="note">' + sp.worth + ' ' + sp.darkest + '</div>' +
        '<div class="note">이 표는 <b>구름을 뺀 순수 어둡기</b> 기준입니다. 오늘 밤 실제로 어디가 나은지는 ' +
        '맨 위 ①번(구름 반영)을 보세요. 빛공해는 전국 시·군 인구와 거리로 추정한 값이라 ' +
        '순위는 믿을 만하지만 절대 수치는 참고용입니다.</div>' +
        '<div class="note">복사점이 ' + sp.dir + '쪽에 있어도 유성은 하늘 전체에 흐릅니다. ' +
        '누워서 하늘을 넓게 보는 게 가장 많이 잡힙니다.</div></div>');
    }

    h.push(calCard());

    out.innerHTML = h.join('');
    out.hidden = false;
    loadWx(d);

    var pin = document.getElementById('mepin'), lab = document.getElementById('melabel');
    if (pin && lab) {
      var x = (d.lon + 180) / 360 * 1000, y = (90 - d.lat) / 180 * 500;
      pin.setAttribute('cx', x.toFixed(1)); pin.setAttribute('cy', y.toFixed(1));
      lab.setAttribute('x', (x + 9).toFixed(1)); lab.setAttribute('y', (y + 4).toFixed(1));
      lab.textContent = d.place;
    }
    var hint = document.getElementById('pickhint');
    if (hint) hint.textContent = d.place + ' 기준으로 보고 있습니다. 다른 곳을 누르면 바로 바뀝니다.';
    Array.prototype.forEach.call(document.querySelectorAll('.pick'), function(b){
      b.classList.toggle('on', b.dataset.city === city);
      b.setAttribute('aria-pressed', b.dataset.city === city ? 'true' : 'false');
    });
    document.title = '유성현황 — ' + d.place + ' 기준';
    try { localStorage.setItem(KEY, city); } catch(e) {}
  }

  Array.prototype.forEach.call(document.querySelectorAll('.pick'), function(b){
    b.addEventListener('click', function(){ render(b.dataset.city); });
  });

  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch(e) {}
  if (saved && DATA[saved]) render(saved);
})();
</script>
""")

    # 세계지도
    lagtxt = (f"관측 시각 {t_from.astimezone(KST):%m/%d %H:%M} ~ {t_to.astimezone(KST):%m/%d %H:%M} KST "
              f"(약 {lag_h:.0f}시간 전까지)") if t_to else ""
    H.append(f"""<h2>⑤ 최근 관측된 유성 {len(meteors):,}개 — 세계 지도</h2>
<div class="card"><div class="lbl" style="margin-bottom:8px">{lagtxt}</div>
<svg viewBox="0 0 {MAP_W} {MAP_H}" style="width:100%;background:#0a1226;border-radius:8px">
  <path d="{land_paths()}" fill="#182444" stroke="#24345e" stroke-width="0.6"/>
  <g>{''.join(dots)}</g>
  <circle id="mepin" cx="{sx:.1f}" cy="{sy:.1f}" r="5" fill="none" stroke="#ff4d6d" stroke-width="2"/>
  <text id="melabel" x="{sx+9:.1f}" y="{sy+4:.1f}" fill="#ff8fa3">{esc(PLACE)}</text>
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
    H.append("""<h2>⑥ 한국 시간대별 검출량</h2><div class="card">""")
    for h in range(24):
        n = hourly.get(h, 0)
        H.append(f"""<div class="hr"><span class="lbl">{h:02d}시</span>
<span class="hbar"><i style="width:{n/hmax*100:.0f}%"></i></span>
<span class="lbl r">{n:,}</span></div>""")
    H.append('<div class="note">전 세계 카메라 합계라 "한국에서 몇 시에 많이 보인다"는 뜻은 아닙니다. '
             '지구 자전으로 관측망이 밤을 통과하는 리듬입니다.</div></div>')

    # 유성우 순위
    H.append("""<h2>⑦ 유성우별 순위</h2><div class="card"><table>
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
    H.append("""<h2>⑧ 가장 밝았던 유성 TOP 12</h2><div class="card"><table>
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
        H.append("""<h2>⑨ 지금 활동량 (GMN 실시간 ZHR)</h2><div class="card">""")
        for title, b64 in flux_imgs:
            H.append(f'<div class="lbl" style="margin:6px 0">{esc(title)}</div>'
                     f'<img class="flux" src="data:image/png;base64,{b64}">')
        H.append('<div class="note">GMN이 몇 시간 간격으로 갱신하는 실측 활동량(ZHR) 그래프입니다. '
                 f'원본: <a href="{FLUX_PAGE}" target="_blank">globalmeteornetwork.org/flux</a></div></div>')

    # 실시간으로 보는 곳
    H.append(f"""<h2>⑩ 지금 이 순간을 보고 싶다면</h2><div class="card">
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
    from_file = load_place()                       # ① 관측지.txt
    if "--nocache" in a:
        NOCACHE = True
    for k, setter in (("--lat", "lat"), ("--lon", "lon"), ("--place", "place")):
        if k in a:
            v = a[a.index(k) + 1]
            if setter == "lat": LAT = float(v)
            elif setter == "lon": LON = float(v)
            else: PLACE = v

    overridden = any(k in a for k in ("--lat", "--lon", "--place"))
    tag = "  [이번만 옵션으로 지정]" if overridden else ("  [관측지.txt 고정]" if from_file else "")
    print(f"유성현황 생성 — 관측지 {PLACE} ({LAT}, {LON}){tag}")
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

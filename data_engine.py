"""
世界杯实时比分数据引擎 - 纯真实数据，无任何模拟

数据源: ESPN API
- 完全免费、无需 API Key、提供极致精确的比赛阶段和实时分钟数
"""
import json
import time
import requests
from threading import Lock
from datetime import datetime, timedelta, timezone

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

# 英文队名 → 中文队名映射
TEAM_ZH = {
    "Mexico": "墨西哥", "South Africa": "南非", "South Korea": "韩国",
    "Canada": "加拿大", "Qatar": "卡塔尔", "Switzerland": "瑞士", "Sweden": "瑞典",
    "Brazil": "巴西", "Morocco": "摩洛哥", "Haiti": "海地", "Scotland": "苏格兰",
    "United States": "美国", "USA": "美国", "Paraguay": "巴拉圭", "Australia": "澳大利亚",
    "Germany": "德国", "Curacao": "库拉索", "Ivory Coast": "科特迪瓦", "Ecuador": "厄瓜多尔",
    "Netherlands": "荷兰", "Japan": "日本", "Tunisia": "突尼斯", "Poland": "波兰",
    "Belgium": "比利时", "Egypt": "埃及", "Iran": "伊朗", "New Zealand": "新西兰",
    "Spain": "西班牙", "Cape Verde": "佛得角", "Saudi Arabia": "沙特阿拉伯", "Uruguay": "乌拉圭",
    "France": "法国", "Senegal": "塞内加尔", "Norway": "挪威", "Honduras": "洪都拉斯",
    "Argentina": "阿根廷", "Algeria": "阿尔及利亚", "Austria": "奥地利", "Jordan": "约旦",
    "Portugal": "葡萄牙", "Uzbekistan": "乌兹别克斯坦", "Colombia": "哥伦比亚", "Peru": "秘鲁",
    "England": "英格兰", "Croatia": "克罗地亚", "Ghana": "加纳", "Panama": "巴拿马",
    "Ukraine": "乌克兰", "Wales": "威尔士", "Turkey": "土耳其", "Indonesia": "印度尼西亚",
    "Cote d'Ivoire": "科特迪瓦", "China": "中国", "Italy": "意大利"
}

class WorldCupDataEngine:
    def __init__(self):
        self.lock = Lock()
        self.matches = []
        self.latest_goal_event = None
        self.last_fetch_time = 0
        self.fetch_error = None
        self._prev_scores = {}
        self._fetch_all_data()

    def _fetch_all_data(self):
        try:
            yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y%m%d")
            today = datetime.utcnow().strftime("%Y%m%d")
            tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y%m%d")

            all_events = []
            request_errors = []
            successful_requests = 0
            for date_str in [yesterday, today, tomorrow]:
                try:
                    r = requests.get(f"{BASE_URL}?dates={date_str}", timeout=8)
                    if r.status_code == 200:
                        successful_requests += 1
                        all_events.extend(r.json().get("events", []))
                    else:
                        request_errors.append(f"{date_str}: HTTP {r.status_code}")
                except Exception as e:
                    request_errors.append(f"{date_str}: {e}")

            if successful_requests == 0:
                raise RuntimeError("ESPN 数据请求全部失败: " + "; ".join(request_errors))

            new_matches = []
            for ev in all_events:
                comp = ev.get("competitions", [{}])[0]
                status_obj = comp.get("status", {})
                status_type = status_obj.get("type", {})
                
                state = status_type.get("state", "pre")  # pre, in, post
                is_live = (state == "in")
                is_finished = (state == "post")
                
                # ESPN 提供非常精准的文字，如 "68'", "Half-Time", "Full Time"
                display_clock = status_obj.get("displayClock", "")
                status_desc = status_type.get("description", "")
                
                if is_live and display_clock:
                    status_zh = display_clock
                else:
                    # 翻译常见状态
                    desc_map = {
                        "Halftime": "中场休息",
                        "Half-Time": "中场休息",
                        "Full Time": "已完赛",
                        "Scheduled": "未开始",
                        "Postponed": "已推迟",
                        "Canceled": "已取消",
                        "End of Second Half": "下半场结束",
                        "End of First Half": "上半场结束"
                    }
                    status_zh = desc_map.get(status_desc, status_desc)

                competitors = comp.get("competitors", [])
                home_team = {}
                away_team = {}
                for c in competitors:
                    if c.get("homeAway") == "home":
                        home_team = c
                    else:
                        away_team = c

                h_name_en = home_team.get("team", {}).get("name", "Home")
                a_name_en = away_team.get("team", {}).get("name", "Away")
                
                h_score_str = home_team.get("score", "")
                a_score_str = away_team.get("score", "")
                
                h_score = int(h_score_str) if h_score_str else (0 if (is_live or is_finished) else None)
                a_score = int(a_score_str) if a_score_str else (0 if (is_live or is_finished) else None)

                # 解析时间
                utc_date_obj = datetime.strptime(ev["date"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
                local_date_obj = utc_date_obj.astimezone()
                date_str = local_date_obj.strftime("%Y-%m-%d")
                time_str = local_date_obj.strftime("%H:%M")

                match_id = ev.get("id", "")

                match = {
                    "id": match_id,
                    "home_team": TEAM_ZH.get(h_name_en, h_name_en),
                    "home_badge": home_team.get("team", {}).get("logo", ""),
                    "away_team": TEAM_ZH.get(a_name_en, a_name_en),
                    "away_badge": away_team.get("team", {}).get("logo", ""),
                    "date": date_str,
                    "time": time_str,
                    "group": ev.get("season", {}).get("slug", "").replace("-", " ").title(),
                    "venue": comp.get("venue", {}).get("fullName", ""),
                    "status_raw": status_type.get("name", ""),
                    "status": status_zh,
                    "is_live": is_live,
                    "is_finished": is_finished,
                    "home_score": h_score,
                    "away_score": a_score
                }
                new_matches.append(match)

            # 去重（可能跨日历请求有重复）
            unique_matches = {m["id"]: m for m in new_matches}.values()
            new_matches = list(unique_matches)
            new_matches.sort(key=lambda m: (m["date"], m["time"]))

            with self.lock:
                for m in new_matches:
                    mid = m["id"]
                    if m["home_score"] is not None and m["away_score"] is not None:
                        curr_total = m["home_score"] + m["away_score"]
                        prev_total = self._prev_scores.get(mid)
                        if prev_total is not None and curr_total > prev_total:
                            self.latest_goal_event = {
                                "match_id": mid,
                                "home_team": m["home_team"],
                                "away_team": m["away_team"],
                                "new_score": f"{m['home_score']} - {m['away_score']}"
                            }
                        self._prev_scores[mid] = curr_total

                self.matches = new_matches
                self.fetch_error = "; ".join(request_errors) if request_errors else None
                self.last_fetch_time = time.time()

        except Exception as e:
            self.fetch_error = str(e)
            print(f"[数据引擎] 拉取失败: {e}")

    def update_tick(self):
        now = time.time()
        has_live = any(m.get("is_live") for m in self.matches)
        interval = 20 if has_live else 120

        if now - self.last_fetch_time >= interval:
            self._fetch_all_data()

    def pop_latest_goal_event(self):
        with self.lock:
            event = self.latest_goal_event
            self.latest_goal_event = None
            return event

    def get_full_data(self):
        with self.lock:
            has_live = any(m.get("is_live") for m in self.matches)
            return {
                "matches": self.matches,
                "has_live": has_live,
                "fetch_error": self.fetch_error,
                "last_fetch": self.last_fetch_time
            }

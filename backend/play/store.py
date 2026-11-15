# -*- coding: utf-8 -*-
"""观众积分存档：一个本地 JSON 文件（默认 data/play.json），跨场保留；原子写（先写临时文件再 replace），有改动才落盘。
结构：{"v": 1, "scopes": {房间号: {"users": {uid: {name, pts, chats, gifts, likes, follows, first, last}}, "days": {"2026-11-15": {uid: 当天得分}}}}}
演示房间（demo）的数据只放内存，不落盘，免得测试假观众混进真实榜单。"""
import json
import os
import threading
import time
from pathlib import Path


def today(now=None):
    return time.strftime("%Y-%m-%d", time.localtime(now or time.time()))


class PlayStore:
    def __init__(self, path, keep_days=60, log=print):
        self.path = Path(path) if path else None
        self.keep_days = max(1, int(keep_days))
        self.log = log
        self.scopes = {}
        self.dirty = False
        self.lock = threading.Lock()
        self.load()

    # ---- 读写 ----
    def load(self):
        if not self.path or not self.path.exists():
            return
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self.scopes = d.get("scopes", {}) if isinstance(d, dict) else {}
        except Exception as e:
            self.log(f"[play] 积分存档读取失败（{e!r}），已改名备份后重新开始")
            try:
                self.path.replace(self.path.with_suffix(".json.bad"))
            except Exception:
                pass

    def save(self, force=False):
        if not self.path or not (self.dirty or force):
            return False
        with self.lock:
            data = {"v": 1, "scopes": {k: v for k, v in self.scopes.items() if k != "demo"}}
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, self.path)
                self.dirty = False
                return True
            except Exception as e:
                self.log(f"[play] 积分存档写入失败：{e!r}")
                return False

    # ---- 数据 ----
    def scope(self, rid):
        return self.scopes.setdefault(str(rid or "0"), {"users": {}, "days": {}})

    def user(self, rid, uid, name=""):
        s = self.scope(rid)
        u = s["users"].get(uid)
        if u is None:
            u = s["users"][uid] = {"name": name or "神秘人", "pts": 0, "chats": 0, "gifts": 0, "likes": 0, "follows": 0, "first": int(time.time()), "last": int(time.time())}
        if name:
            u["name"] = name
        return u

    def add(self, rid, uid, name, pts, kind=None, now=None):
        """加分（pts 可以为 0，只更新名字 / 计数）。返回 (用户记录, 当天得分)。"""
        u = self.user(rid, uid, name)
        u["last"] = int(now or time.time())
        if kind in ("chats", "gifts", "likes", "follows"):
            u[kind] = u.get(kind, 0) + 1
        s = self.scope(rid)
        day = today(now)
        dd = s["days"].setdefault(day, {})
        if pts:
            u["pts"] += pts
            dd[uid] = dd.get(uid, 0) + pts
        self.dirty = True
        return u, dd.get(uid, 0)

    def prune(self, now=None):
        """只留最近 keep_days 天的日榜。"""
        cut = today((now or time.time()) - self.keep_days * 86400)
        for s in self.scopes.values():
            for d in [d for d in s["days"] if d < cut]:
                del s["days"][d]
                self.dirty = True

    def rank(self, rid, by="total", n=20, now=None):
        s = self.scope(rid)
        if by == "day":
            dd = s["days"].get(today(now), {})
            rows = [(uid, p) for uid, p in dd.items() if p > 0]
        else:
            rows = [(uid, u["pts"]) for uid, u in s["users"].items() if u["pts"] > 0]
        rows.sort(key=lambda r: (-r[1], r[0]))
        out = []
        for i, (uid, p) in enumerate(rows[: max(1, n)]):
            u = s["users"].get(uid, {})
            out.append({"rank": i + 1, "uid": uid, "name": u.get("name", "神秘人"), "pts": p, "total": u.get("pts", p)})
        return out

    def position(self, rid, uid, by="total", now=None):
        """某人在榜上第几名（没分 = 0）。"""
        s = self.scope(rid)
        if by == "day":
            mine = s["days"].get(today(now), {}).get(uid, 0)
            allp = s["days"].get(today(now), {}).values()
        else:
            mine = s["users"].get(uid, {}).get("pts", 0)
            allp = [u["pts"] for u in s["users"].values()]
        if mine <= 0:
            return 0
        return 1 + sum(1 for p in allp if p > mine)

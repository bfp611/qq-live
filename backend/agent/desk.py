# -*- coding: utf-8 -*-
"""页面上报的桌面快照（窗口、图标、壁纸、歌曲…）的只读封装：目标解析、状态判断、给 LLM 的摘要文本。

快照格式（agent.js 生成，字段都可缺省）：
  wins:[{id, app, title, state(normal|max|min|closed), x,y,w,h, z(0=最上), active, prot, cover(挡住群聊的比例 0~1), blocks}]
  chat:{x,y,w,h,vis(可见比例), state}   icons:[{id,name,vis}]   wall:"Bliss"   music:{on,title,artist,playing}
  start:bool  dialogs:[title]  mine:{w,h,over,left}  vol:70
"""
from . import registry as R


class Desk:
    def __init__(self, snap=None):
        self.s = snap or {}

    @property
    def known(self):
        return bool(self.s.get("wins") is not None and self.s.get("ts"))

    @property
    def wins(self):
        return [w for w in (self.s.get("wins") or []) if w.get("state") != "closed"]

    def win_by_id(self, i):
        for w in self.s.get("wins") or []:
            if w.get("id") == i:
                return w
        return None

    def apps_open(self):
        return [w.get("app") for w in self.wins if w.get("app")]

    def label(self, w):
        a = w.get("app")
        return R.app_label(a) if a in R.APPS or a == "qqchat" else (w.get("title") or w.get("id"))

    def find(self, target, include_min=True):
        """把 target 解析成窗口列表（按 z 从上到下）。

        支持：窗口 id / 应用 id / 应用别名 / active / chat / blocking / all / 标题片段"""
        t = str(target or "").strip()
        if not t:
            return []
        ws = sorted(self.wins, key=lambda w: w.get("z", 99))
        if not include_min:
            ws = [w for w in ws if w.get("state") != "min"]
        low = t.lower()
        if low in ("active", "当前", "当前窗口", "top", "最前面", "最上面"):
            act = [w for w in ws if w.get("active")] or [w for w in ws if w.get("state") != "min" and not w.get("dialog")][:1]
            return act[:1]
        if low in ("chat", "群聊", "qqchat"):
            return [w for w in ws if w.get("id") == "qqchat"]
        if low in ("blocking", "blocker", "挡住的", "挡着的"):
            return [w for w in ws if w.get("blocks")]
        if low in ("all", "全部", "所有"):
            return [w for w in ws if not w.get("prot")]
        for w in ws:
            if w.get("id") == t:
                return [w]
        app = t if (t in R.APPS or t == "qqchat") else R.find_app(t)
        if app:
            hits = [w for w in ws if w.get("app") == app or (app == "ttplayer" and w.get("id") in ("ttplayer", "ttplaylist"))]
            if app in ("mycomputer", "mydocs", "mypics", "mymusic", "recycle", "control"):
                hits = [w for w in ws if w.get("app") == "explorer" and R.norm(w.get("title")).find(R.norm(R.APPS[app][0])) >= 0] or hits
            return hits
        nt = R.norm(t)
        return [w for w in ws if nt and nt in R.norm(w.get("title"))]

    def blockers(self):
        return [w for w in self.wins if w.get("blocks")]

    def worst_blocker(self):
        b = sorted(self.blockers(), key=lambda w: (-(w.get("cover") or 0), w.get("z", 99)))
        return b[0] if b else None

    def summary(self, max_icons=18):
        """给 LLM 看的紧凑状态文本。"""
        s = self.s
        if not self.known:
            return "（页面还没上报桌面状态；假设桌面上有默认的图标，没有窗口）"
        L = []
        ws = sorted(self.wins, key=lambda w: w.get("z", 99))
        if ws:
            L.append("窗口（z 从上到下）：")
            for w in ws:
                extra = []
                if w.get("active"):
                    extra.append("当前活动")
                if w.get("prot"):
                    extra.append("受保护")
                if w.get("blocks"):
                    extra.append(f"挡住群聊/歌词 {int((w.get('cover') or 0) * 100)}%")
                L.append(f"  id={w['id']} app={w.get('app') or '-'} 「{w.get('title','')}」 {w.get('state')} "
                         f"({int(w.get('x', 0))},{int(w.get('y', 0))} {int(w.get('w', 0))}x{int(w.get('h', 0))})" + (" [" + "，".join(extra) + "]" if extra else ""))
        else:
            L.append("窗口：无")
        ch = s.get("chat") or {}
        if ch:
            L.append(f"群聊窗口 {ch.get('state', 'normal')}，可见 {int((ch.get('vis', 1)) * 100)}%")
        ic = [i.get("name") for i in (s.get("icons") or []) if i.get("name")][:max_icons]
        if ic:
            L.append("桌面图标：" + "、".join(ic))
        L.append(f"壁纸：{s.get('wall') or '?'}")
        m = s.get("music") or {}
        L.append("歌曲：" + (f"{m.get('artist', '')} - {m.get('title', '')}（{'播放中' if m.get('playing') else '已暂停'}）" if m.get("on") else "没有在播"))
        if s.get("start"):
            L.append("开始菜单：已打开")
        if s.get("dialogs"):
            L.append("弹出的对话框：" + "、".join(s["dialogs"][:4]))
        if s.get("mine"):
            mi = s["mine"]
            L.append(f"扫雷：{mi.get('w')}x{mi.get('h')} {'已结束' if mi.get('over') else '进行中'}")
        return "\n".join(L)

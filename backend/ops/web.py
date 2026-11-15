# -*- coding: utf-8 -*-
"""ops 的 HTTP 接口（server.py 注册）。/ops/report* 只给本机（中间件在监听局域网时拦掉其它来源），手机面板走 /ops/api/*（要令牌，见 panel.py）。"""
import asyncio
import json
import re
from pathlib import Path

from aiohttp import web

from . import logs as L
from . import report as R

NAME_RE = re.compile(r"^(latest|report-\d{8}-\d{6})\.(html|md)$")


def jr(o, status=200):
    return web.json_response(o, status=status, dumps=lambda x: json.dumps(x, ensure_ascii=False))


def add_routes(app, ops):
    async def reports(request):
        return jr({"reports": R.list_reports(ops.cfg), "sessions": L.list_sessions(ops.rec.logdir())[:30], "current": ops.rec.snapshot(),
                   "last": ops.last_report, "busy": ops.report_busy})

    async def report_file(request):
        name = request.match_info["name"]
        m = NAME_RE.match(name)
        if not m:
            return web.Response(status=404, text="no such report")
        d = R.report_dir(ops.cfg)
        if m.group(1) == "latest":
            files = sorted(d.glob(f"report-*.{m.group(2)}"))
            if not files:
                return web.Response(status=404, text="还没有复盘：下播后会自动生成，或 /ops/report/make 现在就生成一份", content_type="text/plain", charset="utf-8")
            p = files[-1]
        else:
            p = d / name
            if not p.exists():
                return web.Response(status=404, text="no such report")
        ct = "text/html" if m.group(2) == "html" else "text/markdown"
        return web.Response(body=p.read_bytes(), content_type=ct, charset="utf-8")

    async def make(request):
        sid = request.query.get("sid") or None
        if sid and not re.fullmatch(r"\d{8}-\d{6}", sid):
            return jr({"ok": False, "error": "sid 格式不对"}, 400)
        llm = None if "llm" not in request.query else request.query["llm"] not in ("0", "false")
        r = await asyncio.get_running_loop().run_in_executor(None, lambda: ops.make_report(sid, llm))
        if not r:
            return jr({"ok": False, "error": "没有可生成的场次（还没有记录到直播数据）"})
        return jr({"ok": True, "sid": r["sid"], "html": f"/ops/report/report-{r['sid']}.html", "md": f"/ops/report/report-{r['sid']}.md", "summary": r["stats"]["summary"]})

    async def state(request):
        return jr(ops.state())

    app.router.add_get("/ops/reports.json", reports)
    app.router.add_get("/ops/report/make", make)
    app.router.add_get("/ops/report/{name}", report_file)
    async def health(request):
        which = [x for x in request.query.get("which", "").split(",") if x] or None
        from . import health as H
        res = await asyncio.get_running_loop().run_in_executor(None, lambda: H.run_all(ops, which))
        return jr({"items": res, "ok": not any(x["status"] == "fail" for x in res), "lan": ops.panel_urls(), "token_file": ops.token_path_display()})

    from .api import add_routes as api_routes
    api_routes(app, ops)
    app.router.add_get("/ops/health.json", health)
    app.router.add_get("/ops/state", state)

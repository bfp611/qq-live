# -*- coding: utf-8 -*-
"""OpenAI 兼容 chat/completions（DeepSeek、通义、Kimi、智谱、Ollama、OpenAI…都用同一个接口）。"""
import requests


def thinking_extra(cfg):
    """智谱 GLM 默认会“先思考”，短回复的 token 常被思考吃光 → content 为空；这里和 agent 一样默认关掉（[agent] llm_thinking = auto|off|on）。"""
    try:
        mode = cfg.s("agent", "llm_thinking").lower()
    except Exception:
        mode = "auto"
    base = cfg.s("ai", "base_url").lower()
    if mode == "off" or (mode == "auto" and "bigmodel.cn" in base):
        return {"thinking": {"type": "disabled"}}
    if mode == "on" and "bigmodel.cn" in base:
        return {"thinking": {"type": "enabled"}}
    return {}


def chat(cfg, messages, max_tokens=None, model=None, timeout=None):
    base = cfg.s("ai", "base_url").rstrip("/")
    if not base:
        raise RuntimeError("ai.base_url 未配置")
    key = cfg.s("ai", "api_key")
    body = {"model": model or cfg.s("ai", "model"), "messages": messages,
            "temperature": cfg.f("ai", "temperature"), "max_tokens": max_tokens or cfg.i("ai", "max_tokens"), "stream": False, **thinking_extra(cfg)}
    r = requests.post(base + "/chat/completions", timeout=timeout or cfg.f("ai", "timeout"),
                      headers={"Authorization": f"Bearer {key}"} if key else {}, json=body)
    r.raise_for_status()
    out = r.json()["choices"][0]["message"].get("content") or ""
    if not out.strip():
        raise RuntimeError("LLM 返回空内容")
    return out

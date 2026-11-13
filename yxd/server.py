#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""印小单 · 非标计价引擎（零依赖）。

启动：
    python3 server.py
默认 http://127.0.0.1:8787，仅响应 /internal/pricing/*（供 ERP 后端调用）。

配置：复制 config.example.json 为 config.json，可配置 host / port / data_dir /
internal_secret / legacy_api；环境变量优先级高于配置文件，仅用于本机临时覆盖。
"""

from __future__ import annotations

import csv
import email
from email import policy
import hashlib
import hmac
import io
import json
import mimetypes
import os
import re
import sys
import time
import traceback
import uuid
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# 配置文件（可选）：默认读 yxd/config.json，可用 YXD_CONFIG 指向别的路径。
# 优先级：环境变量 > config.json > 代码默认值。
# 正式环境请用 config.json 配置端口/数据目录/内部密钥；环境变量仅用于本机临时覆盖。
CONFIG_FILE = os.environ.get("YXD_CONFIG") or os.path.join(BASE_DIR, "config.json")


def _load_config(path: str) -> Dict[str, Any]:
    """读取 config.json；文件不存在或格式错误时返回空字典，不阻断启动。"""
    try:
        if not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        print("[yxd] 配置文件读取失败，改用默认值：%s (%s)" % (path, exc))
        return {}


CONFIG = _load_config(CONFIG_FILE)

DATA_DIR = os.environ.get("YXD_DATA_DIR") or CONFIG.get("data_dir") or os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.environ.get("YXD_DB") or CONFIG.get("db_path") or os.path.join(DATA_DIR, "mall.db")

from core import algorithms, formulas, presenters  # noqa: E402
from core.db import Database, now_str  # noqa: E402
from core.engine import QuoteEngine, EngineError, MODE_NAMES, STATUS_NAMES, PAYMENT_NAMES  # noqa: E402
from core.security import (  # noqa: E402
    mask_phone, new_id, new_number, sign_session, verify_password, verify_session,
)

COOKIE = "yxd_session"
MAX_BODY = 8 * 1024 * 1024

# 对端主动断开连接（不是服务端故障）：Windows 10053 = ConnectionAbortedError，
# Linux 104 = ConnectionResetError，写半截管道 = BrokenPipeError。
# 统一当成「审计噪音」处理：不写 500、不打 traceback。
CLIENT_DISCONNECT_ERRORS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)


def _json_default(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


def _num(v, d=0.0):
    try:
        x = float(v)
        return x if x == x else d
    except Exception:
        return d


def _int(v, d=0):
    try:
        return int(float(v))
    except Exception:
        return d


def _clean_phone(v: str) -> str:
    return re.sub(r"[^0-9+]", "", str(v or ""))


def _valid_phone(v: str) -> bool:
    p = _clean_phone(v)
    return 6 <= len(p) <= 20


def _quote_no(db: Database) -> str:
    for _ in range(8):
        no = new_number("BJ")
        if not db.get_quote(no):
            return no
    return new_number("BJ")


def _order_no(db: Database) -> str:
    for _ in range(8):
        no = new_number("YX")
        if not db.get_order(no):
            return no
    return new_number("YX")


def _expire_quote(db: Database, quote: Dict[str, Any]) -> Dict[str, Any]:
    if quote.get("status") == "active" and quote.get("valid_until"):
        if str(quote.get("valid_until")) < now_str():
            quote["status"] = "expired"
            db.update_quote_data(quote.get("no"), quote)
    return quote


def _viewer_for_quote(handler, quote: Dict[str, Any]) -> str:
    user = handler.current_user
    if user and user.get("role") == "admin":
        return "admin"
    if user and user.get("role") == "agent" and quote.get("agent_id") == user.get("id"):
        return "agent"
    return "customer"


def _viewer_for_order(handler, order: Dict[str, Any]) -> str:
    user = handler.current_user
    if user and user.get("role") == "admin":
        return "admin"
    if user and user.get("role") == "agent" and order.get("agent_id") == user.get("id"):
        return "agent"
    return "customer"


def present_order(order: Dict[str, Any], viewer: str) -> Dict[str, Any]:
    data = json.loads(json.dumps(order, ensure_ascii=False))
    if viewer == "admin":
        data["view"] = "admin"
        return data
    if viewer == "agent":
        totals = data.get("totals") or {}
        data["totals"] = {
            "agent": totals.get("agent"),
            "retail": totals.get("retail"),
            "unit_agent": totals.get("unit_agent"),
            "unit_retail": totals.get("unit_retail"),
            "agent_profit": totals.get("agent_profit"),
        }
        data.pop("internal_lines", None)
        data.pop("lines", None)
        data.pop("cost", None)
        data.pop("shipping", None)
        data.pop("subtotal", None)
        data.pop("overhead", None)
        data.pop("tax", None)
        data["aux_lines"] = [
            {k: v for k, v in p.items() if k not in ("amount", "list_amount")}
            for p in data.get("aux_lines") or []
        ]
        data["alternatives"] = [
            {k: v for k, v in p.items() if k not in ("cost",)}
            for p in data.get("alternatives") or []
        ]
        data["view"] = "agent"
        return data
    for k in ("internal_lines", "lines", "cost", "subtotal", "overhead", "tax", "shipping", "markup",
              "agent_id", "agent_code", "platform_fee", "platform_profit", "agent_profit"):
        data.pop(k, None)
    totals = data.get("totals") or {}
    data["totals"] = {
        "retail": totals.get("retail"),
        "unit_retail": totals.get("unit_retail"),
        "shipping_included": True,
    }
    data["view"] = "customer"
    if data.get("customer"):
        data["customer"] = {
            "name": data["customer"].get("name", ""),
            "phone": mask_phone(data["customer"].get("phone", "")),
            "company": data["customer"].get("company", ""),
            "address": data["customer"].get("address", ""),
        }
    data["process_lines"] = [
        {k: v for k, v in p.items() if k not in ("amount", "list_amount", "waived")}
        for p in data.get("process_lines") or []
    ]
    data["aux_lines"] = [
        {k: v for k, v in p.items() if k not in ("amount", "list_amount")}
        for p in data.get("aux_lines") or []
    ]
    data.pop("alternatives", None)
    if isinstance(data.get("optimization"), dict):
        data["optimization"] = {
            "objective": data["optimization"].get("objective"),
            "plans_compared": data["optimization"].get("plans_compared"),
            "message": "系统已比选 %s 个生产方案，选择成本与交期更平衡的方案。" % data["optimization"].get("plans_compared", ""),
        }
    return data



def _export_product(p: Dict[str, Any]) -> Dict[str, Any]:
    """给商品中心/ERP 的稳定 JSON 结构，不包含平台成本与渲染细节。"""
    mode = p.get("pricing_mode") or "nonstandard"
    out = {
        "id": p.get("id"),
        "code": p.get("sku") or p.get("id"),
        "name": p.get("name"),
        "category": p.get("category"),
        "pricing_mode": mode,
        "status": p.get("status", "draft"),
        "subtitle": p.get("subtitle", ""),
        "description": p.get("description", ""),
        "images": p.get("images") or ([p.get("image")] if p.get("image") else []),
        "lead_days": p.get("lead_days", 5),
        "unit": p.get("unit", "个"),
        "quantity": p.get("quantity") or {},
        "modes": p.get("modes") or [],
    }
    if mode == "standard":
        out["standard_price"] = float(p.get("standard_price") or 0)
        out["sku"] = p.get("sku", "")
    else:
        for k in ("kind", "structure", "formula_params", "dim_fields", "size_presets", "bleed",
                  "materials", "default_material", "aux_groups", "colors", "default_colors",
                  "processes", "packagings", "default_packaging", "sample", "production",
                  "overprint_methods", "stock", "pricing", "source_ids", "logistics"):
            if k in p:
                out[k] = p.get(k)
        out["quote_api"] = "/api/admin/product-preview"
    return out


class MallServer(ThreadingHTTPServer):
    daemon_threads = True
    # Windows 下 SO_REUSEADDR 允许新进程重复绑定已被监听的端口，造成多进程叠加；
    # 关闭后重复启动会直接报 WinError 10048，便于立刻暴露重复启动。
    allow_reuse_address = False

    def __init__(self, addr, handler, db: Database):
        super().__init__(addr, handler)
        self.db = db
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    def handle_error(self, request, client_address):
        """客户端主动断开不算服务端故障，不打整段 traceback。

        典型场景：ERP 侧重启/热部署、浏览器取消请求、vite 代理中断——
        连接被对端 RST，Windows 上表现为 ConnectionAbortedError(10053)，
        Linux 上多为 ConnectionResetError(104)。这类噪音会淹掉真正的报错。
        """
        if isinstance(sys.exc_info()[1], CLIENT_DISCONNECT_ERRORS):
            return
        super().handle_error(request, client_address)


class Handler(BaseHTTPRequestHandler):
    server_version = "YinXiaoDan/1.0"
    protocol_version = "HTTP/1.1"

    # ---------------------------------------------------------------- lifecycle
    def log_message(self, fmt, *args):
        if os.environ.get("YXD_QUIET") != "1":
            sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    @property
    def db(self) -> Database:
        return self.server.db

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        self._dispatch("GET", head=True)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_DELETE(self):
        self._dispatch("DELETE")

    # ------------------------------------------------------------------ parsing
    def parse_request(self):
        super().parse_request()
        self.url = urlparse(self.path)
        self.path_only = unquote(self.url.path)
        self.query = {k: v[-1] for k, v in parse_qs(self.url.query).items()}
        # P4：内部接口不依赖 yxd_session cookie，也不再读 users 表。
        # 保留属性只为兼容已不可达的旧 /api/* 代码（P4 后可整段删除）。
        self.current_user = None
        return True

    def body_json(self) -> Dict[str, Any]:
        length = _int(self.headers.get("Content-Length"), 0)
        if length > MAX_BODY:
            raise EngineError("请求体过大")
        raw = self.rfile.read(length) if length else b""
        # 缓存原始请求体，供 /internal/* 的 HMAC 验签复用（对现有 /api/* 无影响）
        self._raw_body = raw.decode("utf-8", "replace") if raw else ""
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            raise EngineError("请求数据格式错误")

    # ------------------------------------------------------------------ output
    def send_json(self, data: Any, status: int = 200, cookies: Optional[List[str]] = None):
        raw = json.dumps(data, ensure_ascii=False, default=_json_default).encode("utf-8")
        # 整段包起来：对端在发头/发体的任意时刻断连都会抛（Windows 上是 ConnectionAbortedError），
        # 一律按「客户端放弃」处理，不再往上抛成 500 + traceback。
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if cookies:
                for c in cookies:
                    self.send_header("Set-Cookie", c)
            self.end_headers()
            self.wfile.write(raw)
        except CLIENT_DISCONNECT_ERRORS:
            # 对端已关闭（ERP 重启 / 前端取消请求 / 代理中断）：关连接即可
            self.close_connection = True


    def download_json(self, data: Any, filename: str):
        raw = json.dumps(data, ensure_ascii=False, default=_json_default).encode("utf-8")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % filename)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
        except CLIENT_DISCONNECT_ERRORS:
            self.close_connection = True

    def ok(self, data: Any = None, status: int = 200, cookies: Optional[List[str]] = None):
        self.send_json({"ok": True, "data": data}, status=status, cookies=cookies)

    def fail(self, message: str, status: int = 400):
        self.send_json({"ok": False, "error": message}, status=status)

    def redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---------------------------------------------------------------- dispatch
    def _dispatch(self, method: str, head: bool = False):
        try:
            # P4：默认「纯接口模式」，只响应 /internal/pricing/*（HMAC 签名 + 网关注入 viewer）。
            # 旧的 /api/*、公开报价页、后台静态页、/uploads/* 全部不可达。
            # 如需临时回退排查，在 config.json 里设 "legacy_api": true（不应在生产使用）。
            if self.path_only.startswith("/internal/"):
                return self.handle_internal(method)
            legacy = os.environ.get("YXD_LEGACY_API", "").lower() in ("1", "true", "yes") or bool(CONFIG.get("legacy_api"))
            if not legacy:
                return self.fail("该服务已切换为内部接口模式（P4）", 404)
            if self.path_only.startswith("/api/"):
                return self.handle_api(method)
            if self.path_only.startswith("/uploads/"):
                return self.serve_file(os.path.join(UPLOAD_DIR, self.path_only[len("/uploads/"):]))
            if method != "GET":
                return self.fail("不支持的请求", 405)
            if self.path_only in ("/", "/index.html") or not self.path_only.startswith(("/assets/", "/vendor/", "/css/", "/js/")):
                return self.serve_file(os.path.join(STATIC_DIR, "index.html"))
            return self.serve_file(os.path.join(STATIC_DIR, self.path_only.lstrip("/")))
        except EngineError as e:
            return self.fail(str(e), 400)
        except CLIENT_DISCONNECT_ERRORS:
            # 客户端断开：没有可写的对端，直接关连接（打 500 只会再抛一次）
            self.close_connection = True
            return
        except Exception as e:
            traceback.print_exc()
            return self.fail("服务器开小差了：%s" % e, 500)

    def serve_file(self, path: str):
        path = os.path.abspath(path)
        allowed = False
        for base in (STATIC_DIR, UPLOAD_DIR):
            if path == os.path.abspath(base) or path.startswith(os.path.abspath(base) + os.sep):
                allowed = True
        if not allowed or not os.path.isfile(path):
            if not self.path_only.startswith("/api/"):
                path = os.path.join(STATIC_DIR, "index.html")
            else:
                return self.fail("文件不存在", 404)
        mime, _ = mimetypes.guess_type(path)
        mime = mime or "application/octet-stream"
        if mime.startswith("text/") or mime in ("application/javascript", "image/svg+xml"):
            mime += "; charset=utf-8"
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError:
            return self.fail("文件读取失败", 404)
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(raw)))
        if path.endswith((".html", ".js", ".css")):
            self.send_header("Cache-Control", "no-cache")
        else:
            self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(raw)
            except CLIENT_DISCONNECT_ERRORS:
                self.close_connection = True

    # ------------------------------------------------------------------- auth
    def require_admin(self) -> Optional[Dict[str, Any]]:
        u = self.current_user
        if not u or u.get("role") != "admin":
            self.fail("请先登录管理后台", 401)
            return None
        return u

    def require_agent(self) -> Optional[Dict[str, Any]]:
        u = self.current_user
        if not u or u.get("role") != "agent":
            self.fail("请先登录代理商账号", 401)
            return None
        return u

    def set_session(self, user: Dict[str, Any]) -> str:
        token = sign_session({"uid": user["id"], "role": user["role"]}, self.db.session_secret(), days=7)
        secure = os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes")
        return "%s=%s; Path=/; HttpOnly; SameSite=Lax; Max-Age=%d%s" % (
            COOKIE, token, 7 * 86400, "; Secure" if secure else ""
        )

    def clear_session(self) -> str:
        return "%s=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0" % COOKIE

    def public_user(self, u: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": u.get("id"),
            "role": u.get("role"),
            "name": u.get("name"),
            "phone": mask_phone(u.get("phone", "")),
            "company": u.get("company", ""),
            "agent_code": u.get("agent_code", ""),
            "default_markup": u.get("default_markup", 0),
            "enabled": u.get("enabled", 1),
        }

    # --------------------------------------------------- internal API (ERP BFF)
    # 仅供 ERP 后端服务端到服务端调用，共用 8787 端口，不对外暴露。
    # 硬约束：
    #   1) 产品计价配置由 ERP 随请求传入，绝不读取本地 products / categories 表；
    #   2) viewer 只取网关注入的签名头，忽略请求体与 yxd_session cookie；
    #   3) 资料库 / settings 仍来自 db（productConfig 里只有 ID 引用）。
    def _internal_viewer(self, method: str) -> Optional[str]:
        # 密钥来源：环境变量（仅本机调试） > config.json 的 internal_secret > 库内 settings.integration_key
        secret = (os.environ.get("YXD_INTERNAL_SECRET")
                  or str(CONFIG.get("internal_secret") or "")
                  or str(self.db.setting("integration_key", "") or ""))
        if not secret:
            self.fail("内部接口密钥未配置（config.json 的 internal_secret）", 401)
            return None
        ts = self.headers.get("X-YXD-Timestamp") or ""
        try:
            delta = abs(int(time.time()) - int(ts))
        except Exception:
            delta = 10 ** 9
        if delta > 300:
            self.fail("内部请求已过期", 401)
            return None
        raw = getattr(self, "_raw_body", "") or ""
        payload = "%s\n%s\n%s\n%s" % (method, self.path_only, ts, raw)
        expect = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        given = self.headers.get("X-YXD-Sign") or ""
        if not hmac.compare_digest(expect, given):
            self.fail("内部接口签名不正确", 401)
            return None
        viewer = self.headers.get("X-YXD-Viewer") or "customer"
        if viewer not in ("customer", "agent", "admin"):
            viewer = "customer"
        return viewer

    def _internal_product(self, body: Dict[str, Any]) -> Dict[str, Any]:
        product = body.get("product") or body.get("productConfig") or {}
        if not isinstance(product, dict) or not product:
            raise EngineError("缺少产品计价配置 product / productConfig")
        if not product.get("modes"):
            product["modes"] = ["overprint"] if product.get("kind") == "overprint" else ["custom"]
        return product

    def _internal_require_admin(self, viewer: str) -> bool:
        """内部「写」接口：ERP 侧只有具备 config 权限的角色才会注入 viewer=admin。"""
        if viewer != "admin":
            self.fail("内部管理接口需要 admin 权限", 403)
            return False
        return True

    def handle_internal(self, method: str):
        p = self.path_only
        body = self.body_json()
        viewer = self._internal_viewer(method)
        if not viewer:
            return
        engine = QuoteEngine(self.db)
        markup = _num(self.db.setting("direct_markup"), 0.35)

        if p == "/internal/pricing/quote" and method == "POST":
            product = self._internal_product(body)
            cfg = body.get("config") or {}
            quote = None
            if (product.get("pricing_mode") or "nonstandard") != "standard" and (product.get("source_ids") or []):
                comp = engine.compare_sources(product, cfg, agent=None, markup=markup)
                rec = comp.get("recommended") or {}
                fac = engine.factories.get(rec.get("id")) if rec else None
                if fac:
                    quote = engine.quote(product, cfg, agent=None, viewer=viewer, markup=markup, factory=fac)
                else:
                    quote = comp.get("base")
            if quote is None:
                quote = engine.quote(product, cfg, agent=None, viewer=viewer, markup=markup)
            return self.ok({"quote": engine.present(quote, viewer)})

        if p == "/internal/pricing/table" and method == "POST":
            product = self._internal_product(body)
            table = engine.price_table(product, body.get("config") or {}, None, markup, body.get("quantities"))
            if viewer == "customer":
                for row in table.get("rows", []):
                    row.pop("unit_agent", None)
                    row.pop("agent", None)
                    row.pop("cost", None)
            return self.ok({"table": table})

        if p == "/internal/pricing/libraries" and method == "GET":
            out = {}
            for t in ("materials", "presses", "sheets", "processes", "packagings"):
                out[t] = self.db.list_library(t, only_enabled=True)
            out["factories"] = self.db.list_factories(include_disabled=False)
            out["structures"] = formulas.list_structures()
            out["algorithms"] = algorithms.list_algorithms()
            return self.ok(out)

        if p == "/internal/pricing/templates" and method == "GET":
            from core import catalog
            keys = (
                "pricing_mode", "kind", "modes", "structure", "dim_fields", "formula_params",
                "bleed", "size_presets", "materials", "default_material", "aux_groups",
                "colors", "default_colors", "processes", "packagings", "default_packaging",
                "quantity", "production", "pricing", "source_ids", "logistics", "sample",
                "overprint_methods", "stock",
            )
            tpls = []
            for prod in catalog.PRODUCTS:
                if (prod.get("pricing_mode") or "") == "standard":
                    continue
                cfg = dict((k, prod[k]) for k in keys if k in prod)
                tpls.append({
                    "key": prod.get("id"),
                    "label": prod.get("name"),
                    "structure": prod.get("structure"),
                    "config": cfg,
                })
            return self.ok({"templates": tpls})

        # -------- P3：管理类内部接口（ERP 全 Vue 化后由 BFF 代理调用） --------
        # 写操作统一要求 viewer=admin；ERP 侧由 system:goodsPricing:config 权限决定。
        lib_tables = ("materials", "presses", "sheets", "processes", "packagings")

        # 全量资料库（含停用项 + 物流默认值），供 ERP 配置向导与资料库页使用。
        # 注意不含 categories：商品分类主数据只在 ERP 维护。
        if p == "/internal/pricing/libraries/full" and method == "GET":
            full = {}
            for t in lib_tables:
                full[t] = self.db.list_library(t)
            full["factories"] = self.db.list_factories()
            full["structures"] = formulas.list_structures()
            full["algorithms"] = algorithms.list_algorithms()
            full["logistics_defaults"] = {
                "mode": "home",
                "provider": "统一配送",
                "warehouse": self.db.setting("warehouse", "杭州中心仓"),
                "base_fee": _num(self.db.setting("shipping_base"), 10),
                "per_kg": _num(self.db.setting("shipping_per_kg"), 1.8),
                "free_over": _num(self.db.setting("free_shipping_over"), 3000),
                "lead_days": 1,
                "included": True,
                "note": self.db.setting("delivery_note", "全国送货上门"),
            }
            return self.ok(full)

        m = re.match(r"^/internal/pricing/libraries/([a-z]+)$", p)
        if m and m.group(1) in lib_tables:
            table = m.group(1)
            if method == "GET":
                return self.ok({"items": self.db.list_library(table)})
            if method == "POST":
                if not self._internal_require_admin(viewer):
                    return
                item = dict(body.get("item") or body)
                if not item.get("id"):
                    item["id"] = new_id("lib-", 10)
                else:
                    # save_library 是 INSERT OR REPLACE 整行覆盖，局部提交前必须合并旧对象
                    old = self.db.get_library(table, item["id"])
                    if old:
                        merged = dict(old)
                        merged.update(item)
                        item = merged
                if not item.get("name"):
                    return self.fail("请填写名称", 400)
                item.setdefault("enabled", 1)
                return self.ok({"item": self.db.save_library(table, item)})

        m = re.match(r"^/internal/pricing/libraries/([a-z]+)/([^/]+)$", p)
        if m and m.group(1) in lib_tables and method == "DELETE":
            if not self._internal_require_admin(viewer):
                return
            table, item_id = m.group(1), m.group(2)
            used = self._library_in_use(table, item_id)
            if used:
                return self.fail("该资料正被商品使用，不能删除：%s" % "、".join(used[:3]), 409)
            self.db.delete_library(table, item_id)
            return self.ok({"deleted": item_id})

        if p == "/internal/pricing/settings" and method == "GET":
            s = self.db.settings()
            s.pop("session_secret", None)
            s.pop("integration_key", None)  # 密钥由运维/环境变量管理，不下发前端
            return self.ok({"settings": s})

        if p == "/internal/pricing/settings" and method in ("POST", "PUT", "PATCH"):
            if not self._internal_require_admin(viewer):
                return
            allowed = {
                "site_name", "site_slogan", "service_phone", "warehouse",
                "platform_margin", "direct_markup", "default_agent_markup",
                "tax_rate", "overhead_rate", "loss_rate", "shipping_base",
                "shipping_per_kg", "free_shipping_over", "min_order_total",
                "quote_valid_days", "delivery_note", "quote_note", "payment_note",
            }
            str_keys = ("site_name", "site_slogan", "service_phone", "warehouse",
                        "delivery_note", "quote_note", "payment_note")
            vals = {}
            for k, v in body.items():
                if k not in allowed:
                    continue
                if k in str_keys:
                    vals[k] = str(v)[:500]
                elif k == "quote_valid_days":
                    vals[k] = max(1, min(90, _int(v, 15)))
                else:
                    vals[k] = max(0, _num(v))
            self.db.save_settings(vals)
            s = self.db.settings()
            s.pop("session_secret", None)
            s.pop("integration_key", None)
            return self.ok({"settings": s})

        if p == "/internal/pricing/factories" and method == "GET":
            return self.ok({"factories": self.db.admin_factories()})

        if p == "/internal/pricing/factories" and method == "POST":
            if not self._internal_require_admin(viewer):
                return
            fac = dict(body.get("factory") or body)
            if not str(fac.get("name") or "").strip():
                return self.fail("请填写工厂名称", 400)
            if not fac.get("id"):
                fac["id"] = new_id("fac-", 8)
            else:
                old = self.db.get_factory(fac["id"])
                if old:
                    merged = dict(old)
                    merged.update(fac)
                    fac = merged
            return self.ok({"factory": self.db.save_factory(fac)})

        m = re.match(r"^/internal/pricing/factories/([^/]+)$", p)
        if m and m.group(1) != "prices" and method == "DELETE":
            if not self._internal_require_admin(viewer):
                return
            ok, msg = self.db.delete_factory(m.group(1))
            if not ok:
                return self.fail(msg, 409)
            return self.ok({"deleted": m.group(1)})

        # 发布前校验：复用后台 _validate_product + 引擎试算（展开/拼版/比价）
        if p == "/internal/pricing/validate" and method == "POST":
            draft = body.get("draft") or body.get("product") or {}
            errs = self._validate_product(draft, active=bool(body.get("active")))
            try:
                preview = QuoteEngine(self.db).technical_preview(
                    draft, body.get("dims"), body.get("material_id"), body.get("qty"))
            except Exception as e:
                preview = {"ok": False, "errors": [str(e)]}
            return self.ok({"errors": errs, "preview": preview})

        return self.fail("接口不存在", 404)

    # ----------------------------------------------------------------- router
    def handle_api(self, method: str):
        p = self.path_only
        db = self.db

        # ---------------- health / bootstrap
        if p == "/api/health" and method == "GET":
            return self.ok({"service": "yxd", "time": now_str()})

        if p == "/api/bootstrap" and method == "GET":
            s = db.settings()
            agent = db.user_by_agent_code(self.query.get("a", ""))
            cats = db.categories()
            return self.ok({
                "site": {
                    "name": s.get("site_name", "印小单"),
                    "slogan": s.get("site_slogan", ""),
                    "phone": s.get("service_phone", ""),
                    "warehouse": s.get("warehouse", ""),
                    "delivery_note": s.get("delivery_note", ""),
                    "quote_note": s.get("quote_note", ""),
                    "payment_note": s.get("payment_note", ""),
                    "quote_valid_days": s.get("quote_valid_days", 15),
                    "tax_rate": s.get("tax_rate", 0.06),
                    "free_shipping_over": s.get("free_shipping_over", 3000),
                },
                "categories": cats,
                "agent": ({
                    "name": agent.get("name"), "company": agent.get("company"),
                    "code": agent.get("agent_code"), "phone": mask_phone(agent.get("phone", "")),
                } if agent else None),
                "structures": formulas.list_structures(),
                "counts": {"products": len(db.list_products())},
            })

        # ---------------- auth
        if p == "/api/auth/login" and method == "POST":
            body = self.body_json()
            login = str(body.get("username") or body.get("phone") or "").strip()
            password = str(body.get("password") or "")
            if not login or not password:
                return self.fail("请输入账号和密码", 400)
            user = db.user_by_login(login)
            if not user or not verify_password(password, user.get("password_hash", "")):
                time.sleep(0.15)
                return self.fail("账号或密码不正确", 401)
            if not user.get("enabled"):
                return self.fail("账号已停用", 403)
            cookie = self.set_session(user)
            return self.ok({"user": self.public_user(user)}, cookies=[cookie])

        if p == "/api/auth/logout" and method == "POST":
            return self.ok({"bye": True}, cookies=[self.clear_session()])

        if p == "/api/auth/me" and method == "GET":
            if not self.current_user:
                return self.ok({"user": None})
            return self.ok({"user": self.public_user(self.current_user)})

        # ---------------- integration (商品中心/ERP 拉取)
        if p == "/api/integration/products" and method == "GET":
            expected = str(db.setting("integration_key", "") or "")
            given = self.headers.get("X-Integration-Key") or self.query.get("key", "")
            if not expected or given != expected:
                return self.fail("集成密钥不正确", 401)
            products = db.list_products(include_inactive=False)
            return self.ok({
                "schema": "yxd.product.v1",
                "exported_at": now_str(),
                "products": [_export_product(x) for x in products],
            })

        m = re.match(r"^/api/integration/products/([^/]+)$", p)
        if m and method == "GET":
            expected = str(db.setting("integration_key", "") or "")
            given = self.headers.get("X-Integration-Key") or self.query.get("key", "")
            if not expected or given != expected:
                return self.fail("集成密钥不正确", 401)
            product = db.get_product(m.group(1))
            if not product or product.get("status") != "active":
                return self.fail("商品不存在或未上架", 404)
            return self.ok({"schema": "yxd.product.v1", "products": [_export_product(product)]})

        # ---------------- public products
        if p == "/api/products" and method == "GET":
            agent = db.user_by_agent_code(self.query.get("a", ""))
            category = self.query.get("category", "")
            kind = self.query.get("kind", "")
            mode = self.query.get("mode", "")
            q = self.query.get("q", "").strip()
            products = db.list_products(include_inactive=False, category=category, kind=kind, q=q)
            if mode:
                products = [x for x in products if mode in (x.get("modes") or [])]
            engine = QuoteEngine(db)
            out = [presenters.public_product(engine, x, agent=agent) for x in products]
            return self.ok({"products": out, "total": len(out)})

        m = re.match(r"^/api/products/([^/]+)$", p)
        if m and method == "GET":
            product = db.get_product(m.group(1))
            if not product or product.get("status") != "active":
                user = self.current_user
                if not (user and user.get("role") == "admin"):
                    return self.fail("商品不存在或未上架", 404)
            agent = db.user_by_agent_code(self.query.get("a", ""))
            engine = QuoteEngine(db)
            return self.ok({"product": presenters.public_product(engine, product, agent=agent, detail=True)})

        # ---------------- quote preview
        if p == "/api/quote" and method == "POST":
            return self.api_quote_preview()

        if p == "/api/quote/table" and method == "POST":
            return self.api_quote_table()

        # ---------------- quotes
        if p == "/api/quotes" and method == "POST":
            return self.api_quote_create()

        m = re.match(r"^/api/quotes/([^/]+)$", p)
        if m and method == "GET":
            quote = db.get_quote(m.group(1))
            if not quote:
                return self.fail("报价单不存在", 404)
            quote = _expire_quote(db, quote)
            viewer = _viewer_for_quote(self, quote)
            engine = QuoteEngine(db)
            return self.ok({"quote": engine.present(quote, viewer)})

        # ---------------- orders
        if p == "/api/orders" and method == "POST":
            return self.api_order_create()

        if p == "/api/orders/lookup" and method == "POST":
            body = self.body_json()
            phone = _clean_phone(body.get("phone", ""))
            if not _valid_phone(phone):
                return self.fail("请输入正确的手机号", 400)
            orders = db.orders_by_phone(phone)
            return self.ok({"orders": [present_order(o, "customer") for o in orders]})

        m = re.match(r"^/api/orders/([^/]+)$", p)
        if m and method == "GET":
            order = db.get_order(m.group(1))
            if not order:
                return self.fail("订单不存在", 404)
            viewer = _viewer_for_order(self, order)
            if viewer == "customer":
                phone = _clean_phone(self.query.get("phone", ""))
                if not phone or phone != _clean_phone(order.get("customer", {}).get("phone", "")):
                    return self.fail("请输入下单手机号后查看订单", 401)
            return self.ok({"order": present_order(order, viewer)})

        # ---------------- agent
        if p == "/api/agent/summary" and method == "GET":
            agent = self.require_agent()
            if not agent:
                return
            quotes = db.list_quotes(agent_id=agent["id"], limit=100)
            orders = db.list_orders(agent_id=agent["id"], limit=100)
            _engine = QuoteEngine(db)
            safe_quotes = [_engine.present(q, "agent") for q in quotes]
            month = time.strftime("%Y-%m")
            month_orders = [o for o in orders if str(o.get("created_at", "")).startswith(month)]
            profit = sum(_num((o.get("totals") or {}).get("agent_profit")) for o in month_orders)
            gmv = sum(_num((o.get("totals") or {}).get("retail")) for o in month_orders)
            return self.ok({
                "quotes": len(quotes),
                "orders": len(orders),
                "month_orders": len(month_orders),
                "month_gmv": round(gmv, 2),
                "month_profit": round(profit, 2),
                "recent_quotes": safe_quotes[:6],
                "recent_orders": [present_order(o, "agent") for o in orders[:6]],
                "agent": self.public_user(agent),
            })

        if p == "/api/agent/quotes" and method == "GET":
            agent = self.require_agent()
            if not agent:
                return
            quotes = db.list_quotes(agent_id=agent["id"], status=self.query.get("status", ""), q=self.query.get("q", ""))
            _engine = QuoteEngine(db)
            return self.ok({"quotes": [_engine.present(q, "agent") for q in quotes]})

        if p == "/api/agent/orders" and method == "GET":
            agent = self.require_agent()
            if not agent:
                return
            orders = db.list_orders(agent_id=agent["id"], status=self.query.get("status", ""), q=self.query.get("q", ""))
            return self.ok({"orders": [present_order(o, "agent") for o in orders]})

        if p == "/api/agent/profile" and method == "PATCH":
            agent = self.require_agent()
            if not agent:
                return
            body = self.body_json()
            upd = {"id": agent["id"]}
            if "default_markup" in body:
                upd["default_markup"] = max(0, min(1.5, _num(body["default_markup"])))
            if body.get("company"):
                upd["company"] = str(body["company"])[:80]
            if body.get("name"):
                upd["name"] = str(body["name"])[:40]
            if body.get("password"):
                if len(str(body["password"])) < 6:
                    return self.fail("新密码至少 6 位", 400)
                upd["password"] = str(body["password"])
            user = db.save_user(upd)
            return self.ok({"user": self.public_user(user)})

        # ---------------- admin
        if p.startswith("/api/admin/"):
            admin = self.require_admin()
            if not admin:
                return
            return self.handle_admin(method, p)

        return self.fail("接口不存在", 404)

    # --------------------------------------------------------------- quote API
    def _agent_context(self, body: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], float, str]:
        db = self.db
        agent = None
        viewer = "customer"
        markup = None
        if self.current_user and self.current_user.get("role") == "agent":
            agent = self.current_user
            viewer = "agent"
            if body.get("markup") is not None:
                markup = max(0, min(1.5, _num(body.get("markup"))))
            else:
                markup = _num(agent.get("default_markup"), 0.28)
        elif self.current_user and self.current_user.get("role") == "admin":
            viewer = "admin"
            code = str(body.get("agent_code") or "").strip()
            if code:
                agent = db.user_by_agent_code(code)
            if body.get("markup") is not None:
                markup = max(0, min(1.5, _num(body.get("markup"))))
            else:
                markup = _num(agent.get("default_markup"), 0.28) if agent else _num(self.db.setting("direct_markup"), 0.35)
        else:
            code = str(body.get("agent_code") or "").strip()
            agent = db.user_by_agent_code(code) if code else None
            if agent:
                markup = _num(agent.get("default_markup"), 0.28)
        return agent, (markup if markup is not None else _num(self.db.setting("direct_markup"), 0.35)), viewer

    def _get_product_or_fail(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pid = str(body.get("product_id") or body.get("productId") or "")
        product = self.db.get_product(pid)
        if not product:
            self.fail("商品不存在", 404)
            return None
        if product.get("status") != "active" and not (self.current_user and self.current_user.get("role") == "admin"):
            self.fail("商品未上架", 403)
            return None
        return product

    def api_quote_preview(self):
        body = self.body_json()
        product = self._get_product_or_fail(body)
        if not product:
            return
        agent, markup, viewer = self._agent_context(body)
        engine = QuoteEngine(self.db)
        cfg = body.get("config") or {}
        quote = None
        if (product.get("pricing_mode") or "nonstandard") != "standard" and (product.get("source_ids") or []):
            comp = engine.compare_sources(product, cfg, agent=agent, markup=markup)
            rec = comp.get("recommended") or {}
            fac = engine.factories.get(rec.get("id")) if rec else None
            if fac:
                quote = engine.quote(product, cfg, agent=agent, viewer=viewer, markup=markup, factory=fac)
            else:
                quote = comp.get("base")
        if quote is None:
            quote = engine.quote(product, cfg, agent=agent, viewer=viewer, markup=markup)
        return self.ok({"quote": engine.present(quote, viewer)})

    def api_quote_table(self):
        body = self.body_json()
        product = self._get_product_or_fail(body)
        if not product:
            return
        agent, markup, viewer = self._agent_context(body)
        engine = QuoteEngine(self.db)
        table = engine.price_table(product, body.get("config") or {}, agent, markup, body.get("quantities"))
        if viewer == "customer":
            for row in table["rows"]:
                row.pop("unit_agent", None)
                row.pop("agent", None)
        return self.ok({"table": table})

    def api_quote_create(self):
        body = self.body_json()
        product = self._get_product_or_fail(body)
        if not product:
            return
        customer = body.get("customer") or {}
        name = str(customer.get("name") or "").strip()
        phone = _clean_phone(customer.get("phone", ""))
        if not name:
            return self.fail("请填写联系人姓名", 400)
        if not _valid_phone(phone):
            return self.fail("请填写正确的手机号", 400)
        agent, markup, viewer = self._agent_context(body)
        engine = QuoteEngine(self.db)
        quote = engine.quote(product, body.get("config") or {}, agent=agent, viewer="admin", markup=markup)
        no = _quote_no(self.db)
        valid_days = _int(self.db.setting("quote_valid_days"), 15)
        valid_until = time.strftime("%Y-%m-%d", time.localtime(time.time() + valid_days * 86400)) + " 23:59:59"
        quote["no"] = no
        quote["status"] = "active"
        quote["valid_until"] = valid_until
        quote["customer"] = {
            "name": name[:40],
            "phone": phone,
            "company": str(customer.get("company") or "")[:80],
            "address": str(customer.get("address") or "")[:200],
        }
        quote["agent_id"] = (agent or {}).get("id")
        quote["agent_code"] = (agent or {}).get("agent_code")
        quote["source"] = str(body.get("source") or "")
        quote["note"] = str(body.get("note") or "")[:500]
        self.db.save_quote(no, quote, valid_until)
        view = engine.present(quote, viewer if viewer != "admin" else "admin")
        view["url"] = "/#/quote/" + no
        return self.ok({"quote": view, "no": no, "url": "/#/quote/" + no})

    # --------------------------------------------------------------- order API
    def api_order_create(self):
        body = self.body_json()
        quote_no = str(body.get("quote_no") or "").strip()
        quote = self.db.get_quote(quote_no)
        if not quote:
            return self.fail("报价单不存在，请重新报价", 404)
        quote = _expire_quote(self.db, quote)
        if quote.get("status") == "converted":
            return self.fail("该报价单已下过单，请到订单中心查看", 409)
        if quote.get("status") != "active":
            return self.fail("报价单已失效，请重新报价", 409)

        customer = body.get("customer") or quote.get("customer") or {}
        name = str(customer.get("name") or "").strip()
        phone = _clean_phone(customer.get("phone", ""))
        address = str(customer.get("address") or "").strip()
        if not name or not _valid_phone(phone):
            return self.fail("请填写联系人与手机号", 400)
        if not address:
            return self.fail("请填写收货地址", 400)

        no = _order_no(self.db)
        order = json.loads(json.dumps(quote, ensure_ascii=False))
        order["no"] = no
        order["quote_no"] = quote_no
        order["created_at"] = now_str()
        order["updated_at"] = now_str()
        order["status"] = "pending"
        order["payment_status"] = "unpaid"
        order["customer"] = {
            "name": name[:40],
            "phone": phone,
            "company": str(customer.get("company") or "")[:80],
            "address": address[:300],
            "email": str(customer.get("email") or "")[:80],
            "invoice": str(customer.get("invoice") or "")[:80],
        }
        order["customer_note"] = str(body.get("note") or quote.get("note") or "")[:500]
        order["admin_note"] = ""
        order["logistics_note"] = ""
        order["status_history"] = [{"status": "pending", "at": now_str(), "note": "客户提交订单"}]
        order.pop("url", None)
        self.db.save_order(no, order)
        if order.get("mode") == "overprint":
            pid = (order.get("product") or {}).get("id")
            prod = self.db.get_product(pid) if pid else None
            if prod and prod.get("stock"):
                prod["stock"]["stock_qty"] = max(0, _int(prod["stock"].get("stock_qty"), 0) - _int(order.get("qty"), 0))
                self.db.save_product(prod)
        quote["status"] = "converted"
        quote["order_no"] = no
        self.db.update_quote_data(quote_no, quote)
        viewer = _viewer_for_order(self, order)
        return self.ok({"order": present_order(order, viewer), "no": no})

    # -------------------------------------------------------------- admin API
    def handle_admin(self, method: str, p: str):
        db = self.db

        if p == "/api/admin/summary" and method == "GET":
            stats = db.analytics()
            agents = db.list_agents()
            stats["agents"] = len(agents)
            stats["products"] = len(db.list_products(include_inactive=True))
            stats["recent_quotes"] = db.list_quotes(limit=6)
            stats["recent_orders"] = db.list_orders(limit=6)
            stats["agent_rows"] = [
                {"name": a.get("name"), "code": a.get("agent_code"), "company": a.get("company")}
                for a in agents
            ]
            return self.ok(stats)

        # categories
        if p == "/api/admin/categories" and method == "GET":
            return self.ok({"categories": db.admin_categories()})

        if p == "/api/admin/categories" and method == "POST":
            body = self.body_json()
            item = body.get("category") or body
            if not str(item.get("name") or "").strip():
                return self.fail("请填写类目名称", 400)
            if not item.get("id"):
                item["id"] = new_id("cat-", 8)
            if item.get("parent_id") == item.get("id"):
                return self.fail("上级类目不能选择自己", 400)
            saved = db.save_category(item)
            return self.ok({"category": saved})

        m = re.match(r"^/api/admin/categories/([^/]+)$", p)
        if m and method == "DELETE":
            ok, msg = db.delete_category(m.group(1))
            if not ok:
                return self.fail(msg, 409)
            return self.ok({"deleted": m.group(1)})

        # factories / quote sources
        if p == "/api/admin/factories" and method == "GET":
            return self.ok({"factories": db.admin_factories()})

        if p == "/api/admin/factories" and method == "POST":
            body = self.body_json()
            item = body.get("factory") or body
            if not str(item.get("name") or "").strip():
                return self.fail("请填写工厂名称", 400)
            if not item.get("id"):
                item["id"] = new_id("fac-", 8)
            saved = db.save_factory(item)
            return self.ok({"factory": saved})

        m = re.match(r"^/api/admin/factories/([^/]+)$", p)
        if m and method == "DELETE":
            ok, msg = db.delete_factory(m.group(1))
            if not ok:
                return self.fail(msg, 409)
            return self.ok({"deleted": m.group(1)})

        # products
        if p == "/api/admin/products" and method == "GET":
            products = db.list_products(include_inactive=True)
            engine = QuoteEngine(db)
            return self.ok({"products": [presenters.admin_product(engine, x) for x in products]})

        if p == "/api/admin/products" and method == "POST":
            body = self.body_json()
            draft = body.get("product") or body
            draft.setdefault("status", body.get("status") or "draft")
            errs = self._validate_product(draft, active=(draft.get("status") == "active"))
            if errs:
                return self.fail("；".join(errs), 400)
            if draft.get("status") == "active" and (draft.get("pricing_mode") or "nonstandard") != "standard":
                engine = QuoteEngine(db)
                try:
                    engine.quote(draft, engine.default_config(draft), agent=None, viewer="admin")
                except EngineError as e:
                    return self.fail("发布前试算未通过：%s。请检查材料、设备、必选工艺与数量配置。" % e, 400)
                except Exception as e:
                    return self.fail("发布前试算未通过：%s" % e, 400)
            product = db.save_product(draft)
            engine = QuoteEngine(db)
            return self.ok({"product": presenters.admin_product(engine, product)})

        if p == "/api/admin/products/export" and method == "GET":
            products = db.list_products(include_inactive=True)
            return self.download_json({
                "schema": "yxd.product.v1",
                "exported_at": now_str(),
                "site": {"name": db.setting("site_name", "印小单")},
                "products": [_export_product(x) for x in products],
            }, "yxd-products.json")

        m = re.match(r"^/api/admin/products/([^/]+)/export$", p)
        if m and method == "GET":
            product = db.get_product(m.group(1))
            if not product:
                return self.fail("商品不存在", 404)
            return self.download_json({
                "schema": "yxd.product.v1",
                "exported_at": now_str(),
                "products": [_export_product(product)],
            }, "yxd-product-%s.json" % m.group(1))

        m = re.match(r"^/api/admin/products/([^/]+)$", p)
        if m and method == "GET":
            product = db.get_product(m.group(1))
            if not product:
                return self.fail("商品不存在", 404)
            engine = QuoteEngine(db)
            return self.ok({"product": presenters.admin_product(engine, product)})

        m = re.match(r"^/api/admin/products/([^/]+)/status$", p)
        if m and method == "PATCH":
            body = self.body_json()
            status = str(body.get("status") or "")
            if status not in ("active", "draft", "disabled"):
                return self.fail("状态不合法", 400)
            if status == "active":
                product = db.get_product(m.group(1))
                if not product:
                    return self.fail("商品不存在", 404)
                errs = self._validate_product(product, active=True)
                if errs:
                    return self.fail("上架前检查未通过：%s" % "；".join(errs), 400)
                engine = QuoteEngine(db)
                try:
                    if (product.get("pricing_mode") or "nonstandard") != "standard":
                        engine.quote(product, engine.default_config(product), agent=None, viewer="admin")
                except EngineError as e:
                    return self.fail("上架前试算未通过：%s" % e, 400)
            db.set_product_status(m.group(1), status)
            return self.ok({"id": m.group(1), "status": status})

        m = re.match(r"^/api/admin/products/([^/]+)$", p)
        if m and method == "DELETE":
            db.set_product_status(m.group(1), "disabled")
            return self.ok({"id": m.group(1), "status": "disabled"})

        if p == "/api/admin/quote-compare" and method == "POST":
            body = self.body_json()
            product = db.get_product(str(body.get("product_id") or ""))
            if not product:
                return self.fail("商品不存在", 404)
            if (product.get("pricing_mode") or "nonstandard") == "standard":
                return self.ok({"standard": True, "product": presenters.admin_product(QuoteEngine(db), product)})
            engine = QuoteEngine(db)
            try:
                comp = engine.compare_sources(product, body.get("config") or {}, agent=None, markup=0)
            except EngineError as e:
                return self.fail(str(e), 400)
            rec = comp.get("recommended") or {}
            recq = None
            if rec:
                fac = engine.factories.get(rec.get("id"))
                try:
                    q = engine.quote(product, body.get("config") or {}, agent=None, viewer="admin", markup=0, factory=fac)
                    recq = engine.present(q, "admin")
                except EngineError:
                    recq = None
            return self.ok({
                "quote": engine.present(comp["base"], "admin"),
                "sources": comp.get("sources") or [],
                "recommended": rec,
                "recommended_quote": recq,
            })

        if p == "/api/admin/product-preview" and method == "POST":
            body = self.body_json()
            draft = body.get("draft") or body.get("product") or {}
            engine = QuoteEngine(db)
            result = engine.technical_preview(draft, body.get("dims"), body.get("material_id"), body.get("qty"))
            return self.ok(result)

        # quotes
        if p == "/api/admin/quotes" and method == "GET":
            quotes = db.list_quotes(agent_id=self.query.get("agent_id", ""), status=self.query.get("status", ""), q=self.query.get("q", ""))
            return self.ok({"quotes": quotes})

        m = re.match(r"^/api/admin/quotes/([^/]+)$", p)
        if m and method == "PATCH":
            body = self.body_json()
            status = str(body.get("status") or "")
            if status not in ("active", "converted", "expired", "closed"):
                return self.fail("状态不合法", 400)
            db.set_quote_status(m.group(1), status)
            quote = db.get_quote(m.group(1))
            return self.ok({"quote": quote})

        # orders
        if p == "/api/admin/orders" and method == "GET":
            orders = db.list_orders(agent_id=self.query.get("agent_id", ""), status=self.query.get("status", ""), q=self.query.get("q", ""))
            return self.ok({"orders": orders})

        m = re.match(r"^/api/admin/orders/([^/]+)$", p)
        if m and method == "GET":
            order = db.get_order(m.group(1))
            if not order:
                return self.fail("订单不存在", 404)
            return self.ok({"order": order})

        m = re.match(r"^/api/admin/orders/([^/]+)$", p)
        if m and method == "PATCH":
            body = self.body_json()
            status = body.get("status")
            payment = body.get("payment_status")
            if status is not None and status not in ("pending", "confirmed", "producing", "shipped", "completed", "cancelled"):
                return self.fail("订单状态不合法", 400)
            if payment is not None and payment not in ("unpaid", "deposit", "paid"):
                return self.fail("付款状态不合法", 400)
            order = db.get_order(m.group(1))
            if not order:
                return self.fail("订单不存在", 404)
            kwargs = {}
            if status is not None:
                kwargs["status"] = status
                hist = order.get("status_history") or []
                hist.append({"status": status, "at": now_str(), "note": str(body.get("status_note") or "")[:200]})
                order["status_history"] = hist
            if payment is not None:
                kwargs["payment_status"] = payment
            if "admin_note" in body:
                kwargs["admin_note"] = str(body.get("admin_note") or "")[:500]
            if "logistics_note" in body:
                kwargs["logistics_note"] = str(body.get("logistics_note") or "")[:500]
            # 先更新状态历史，再写库
            if "status_history" in order:
                with db.conn() as c:
                    c.execute("UPDATE orders SET data=? WHERE no=?", (json.dumps(order, ensure_ascii=False), m.group(1)))
            db.update_order(m.group(1), **kwargs)
            return self.ok({"order": db.get_order(m.group(1))})

        if p == "/api/admin/export/orders.csv" and method == "GET":
            return self.export_orders_csv()

        # agents
        if p == "/api/admin/agents" and method == "GET":
            agents = db.list_agents()
            out = []
            for a in agents:
                quotes = db.list_quotes(agent_id=a["id"], limit=500)
                orders = db.list_orders(agent_id=a["id"], limit=500)
                out.append({
                    "id": a["id"], "name": a["name"], "company": a["company"], "phone": a["phone"],
                    "agent_code": a["agent_code"], "default_markup": a["default_markup"], "enabled": a["enabled"],
                    "quotes": len(quotes), "orders": len(orders),
                    "gmv": round(sum(_num((o.get("totals") or {}).get("retail")) for o in orders), 2),
                    "profit": round(sum(_num((o.get("totals") or {}).get("agent_profit")) for o in orders), 2),
                    "created_at": a.get("created_at"),
                })
            return self.ok({"agents": out})

        if p == "/api/admin/agents" and method == "POST":
            body = self.body_json()
            name = str(body.get("name") or "").strip()
            phone = _clean_phone(body.get("phone", ""))
            code = str(body.get("agent_code") or "").strip().upper()
            if not name or not _valid_phone(phone):
                return self.fail("请填写代理商名称与手机号", 400)
            if not code:
                code = "A" + str(int(time.time()))[-4:]
            existing = db.user_by_agent_code(code)
            if existing:
                return self.fail("代理编码已存在", 409)
            if db.user_by_login(phone):
                return self.fail("手机号已注册", 409)
            user = db.save_user({
                "role": "agent", "username": phone, "phone": phone, "name": name,
                "company": str(body.get("company") or "")[:80], "agent_code": code,
                "password": str(body.get("password") or "agent123"),
                "default_markup": max(0, min(1.5, _num(body.get("default_markup"), 0.28))),
                "enabled": 1,
            })
            return self.ok({"agent": self.public_user(user), "password": str(body.get("password") or "agent123")})

        m = re.match(r"^/api/admin/agents/([^/]+)$", p)
        if m and method == "PATCH":
            body = self.body_json()
            user = db.user_by_id(m.group(1))
            if not user or user.get("role") != "agent":
                return self.fail("代理商不存在", 404)
            upd = {"id": user["id"]}
            for k in ("name", "company"):
                if k in body:
                    upd[k] = str(body[k])[:80]
            if "default_markup" in body:
                upd["default_markup"] = max(0, min(1.5, _num(body["default_markup"])))
            if "enabled" in body:
                upd["enabled"] = 1 if body["enabled"] else 0
            if body.get("password"):
                upd["password"] = str(body["password"])
            if body.get("phone"):
                phone = _clean_phone(body["phone"])
                if not _valid_phone(phone):
                    return self.fail("手机号不正确", 400)
                upd["phone"] = phone
                upd["username"] = phone
            u = db.save_user(upd)
            return self.ok({"agent": self.public_user(u)})

        # libraries
        if p == "/api/admin/libraries" and method == "GET":
            return self.ok({
                "materials": db.list_library("materials"),
                "presses": db.list_library("presses"),
                "sheets": db.list_library("sheets"),
                "processes": db.list_library("processes"),
                "packagings": db.list_library("packagings"),
                "factories": db.list_factories(),
                "algorithms": algorithms.list_algorithms(),
                "structures": formulas.list_structures(),
                "categories": db.categories(),
                "logistics_defaults": {
                    "mode": "home", "provider": "统一配送",
                    "warehouse": db.setting("warehouse", "杭州中心仓"),
                    "base_fee": db.setting("shipping_base", 10),
                    "per_kg": db.setting("shipping_per_kg", 1.8),
                    "free_over": db.setting("free_shipping_over", 3000),
                    "lead_days": 1, "included": True,
                    "note": db.setting("delivery_note", "全国送货上门"),
                },
            })

        m = re.match(r"^/api/admin/libraries/([a-z]+)$", p)
        if m and m.group(1) in ("materials", "presses", "sheets", "processes", "packagings") and method == "GET":
            return self.ok({"items": db.list_library(m.group(1))})

        m = re.match(r"^/api/admin/libraries/([a-z]+)$", p)
        if m and m.group(1) in ("materials", "presses", "sheets", "processes", "packagings") and method == "POST":
            body = self.body_json()
            item = body.get("item") or body
            item = dict(item)
            if not item.get("id"):
                item["id"] = new_id("lib-", 10)
            if not item.get("name"):
                return self.fail("请填写名称", 400)
            item.setdefault("enabled", 1)
            saved = db.save_library(m.group(1), item)
            return self.ok({"item": saved})

        m = re.match(r"^/api/admin/libraries/([a-z]+)/([^/]+)$", p)
        if m and m.group(1) in ("materials", "presses", "sheets", "processes", "packagings") and method == "DELETE":
            table, item_id = m.group(1), m.group(2)
            used = self._library_in_use(table, item_id)
            if used:
                return self.fail("该资料正被商品使用，不能删除：%s" % "、".join(used[:3]), 409)
            db.delete_library(table, item_id)
            return self.ok({"deleted": item_id})

        # settings
        if p == "/api/admin/settings" and method == "GET":
            s = db.settings()
            s.pop("session_secret", None)
            return self.ok({"settings": s})

        if p == "/api/admin/settings" and method == "PATCH":
            body = self.body_json()
            allowed = {
                "site_name", "site_slogan", "service_phone", "warehouse", "platform_margin", "direct_markup",
                "default_agent_markup", "tax_rate", "overhead_rate", "loss_rate", "shipping_base",
                "shipping_per_kg", "free_shipping_over", "min_order_total", "quote_valid_days",
                "delivery_note", "quote_note", "payment_note",
                "integration_key",
            }
            vals = {}
            for k, v in body.items():
                if k not in allowed:
                    continue
                if k in ("site_name", "site_slogan", "service_phone", "warehouse", "delivery_note", "quote_note", "payment_note", "integration_key"):
                    vals[k] = str(v)[:500]
                elif k == "quote_valid_days":
                    vals[k] = max(1, min(90, _int(v, 15)))
                else:
                    vals[k] = max(0, _num(v))
            db.save_settings(vals)
            return self.ok({"settings": {k: v for k, v in db.settings().items() if k != "session_secret"}})

        if p == "/api/admin/password" and method == "POST":
            body = self.body_json()
            user = self.current_user
            if not verify_password(str(body.get("current") or ""), user.get("password_hash", "")):
                return self.fail("当前密码不正确", 400)
            new = str(body.get("new") or "")
            if len(new) < 6:
                return self.fail("新密码至少 6 位", 400)
            db.save_user({"id": user["id"], "password": new})
            return self.ok({"changed": True})

        if p == "/api/admin/upload" and method == "POST":
            return self.api_upload()

        return self.fail("接口不存在", 404)

    def _validate_product(self, draft: Dict[str, Any], active: bool = False) -> List[str]:
        errs = []
        if not str(draft.get("name") or "").strip():
            errs.append("请填写商品名称")
        if not active:
            return errs
        pricing_mode = draft.get("pricing_mode") or "nonstandard"
        if pricing_mode == "standard":
            if not draft.get("category"):
                errs.append("请选择商品类目")
            if _num(draft.get("standard_price"), 0) <= 0:
                errs.append("标准定价必须大于 0")
            if not str(draft.get("unit") or "").strip():
                errs.append("请填写计价单位")
            return errs
        if draft.get("kind") not in ("custom", "overprint"):
            errs.append("商品类型必须是全定制或成品加印")
        if draft.get("kind") == "custom":
            if not draft.get("structure") or draft.get("structure") not in formulas.STRUCTURES:
                errs.append("请选择盒型/展开公式")
            if not draft.get("materials"):
                errs.append("请至少选择一种材料")
            if not (draft.get("processes") or {}).get("required"):
                errs.append("请至少配置一种必选工艺")
            q = draft.get("quantity") or {}
            if _int(q.get("min"), 0) < 1:
                errs.append("起订量必须大于 0")
        else:
            if not draft.get("stock"):
                errs.append("成品加印商品需要配置现货规格")
            if not draft.get("overprint_methods"):
                errs.append("请至少配置一种加印工艺")
        if not draft.get("modes"):
            errs.append("请至少选择一种销售模式")
        if not draft.get("packagings"):
            errs.append("请至少选择一种包装方式")
        return errs

    def _library_in_use(self, table: str, item_id: str) -> List[str]:
        products = self.db.list_products(include_inactive=True)
        hits = []
        for p in products:
            blob = json.dumps(p, ensure_ascii=False)
            if item_id in blob:
                hits.append(p.get("name", p.get("id")))
        return hits

    def api_upload(self):
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            return self.fail("请使用文件上传", 400)
        length = _int(self.headers.get("Content-Length"), 0)
        if length > MAX_BODY:
            return self.fail("文件不能超过 8MB", 400)
        try:
            payload = self.rfile.read(length)
            msg = email.message_from_bytes(
                ("Content-Type: %s\r\nMIME-Version: 1.0\r\n\r\n" % ctype).encode("utf-8") + payload,
                policy=policy.default,
            )
            if not msg.is_multipart():
                return self.fail("上传格式不正确", 400)
            filename = ""
            raw = b""
            for part in msg.iter_parts():
                if part.get_param("name", header="content-disposition") == "file":
                    filename = part.get_filename() or ""
                    raw = part.get_payload(decode=True) or b""
                    break
        except Exception as e:
            return self.fail("上传解析失败：%s" % e, 400)
        if not filename:
            return self.fail("缺少文件字段", 400)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
            return self.fail("仅支持 png / jpg / webp / gif / svg", 400)
        if not raw:
            return self.fail("文件为空", 400)
        if len(raw) > MAX_BODY:
            return self.fail("文件不能超过 8MB", 400)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        name = uuid.uuid4().hex + ext
        with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
            f.write(raw)
        return self.ok({"url": "/uploads/" + name, "name": filename, "size": len(raw)})

    def export_orders_csv(self):
        orders = self.db.list_orders(limit=10000)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["订单号", "下单时间", "状态", "付款", "客户", "电话", "公司", "商品", "数量", "零售价", "代理价", "成本", "渠道", "备注"])
        for o in orders:
            t = o.get("totals") or {}
            w.writerow([
                o.get("no"), o.get("created_at"), STATUS_NAMES.get(o.get("status"), o.get("status")),
                PAYMENT_NAMES.get(o.get("payment_status"), o.get("payment_status")),
                (o.get("customer") or {}).get("name"), (o.get("customer") or {}).get("phone"),
                (o.get("customer") or {}).get("company"), (o.get("product") or {}).get("name"),
                o.get("qty"), t.get("retail"), t.get("agent"), t.get("cost"),
                (o.get("agent") or {}).get("name") or "官方直营", o.get("customer_note", ""),
            ])
        data = "\ufeff" + buf.getvalue()
        raw = data.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="orders.csv"')
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def make_server(host: str = "127.0.0.1", port: int = 8787, db_path: str = DB_PATH) -> MallServer:
    db = Database(db_path)
    db.init()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    return MallServer((host, port), Handler, db)


def main():
    port = int(os.environ.get("PORT") or CONFIG.get("port") or 8787)
    host = os.environ.get("HOST") or CONFIG.get("host") or "127.0.0.1"
    server = make_server(host, port, DB_PATH)
    print("")
    print("  印小单 · 非标计价引擎（内部接口模式）")
    print("  监听  http://%s:%d/internal/pricing/*" % (host, port))
    print("  说明  旧 /api/* 与静态页已下线，页面统一由 ERP 提供")
    print("  数据  %s" % DB_PATH)
    print("  配置  %s%s" % (CONFIG_FILE, "" if os.path.isfile(CONFIG_FILE) else "（未找到，使用默认值）"))
    print("")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()

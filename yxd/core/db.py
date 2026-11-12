# -*- coding: utf-8 -*-
"""SQLite 数据层：资料库、商品、报价、订单、用户、参数。"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import catalog
from .security import hash_password, new_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  role TEXT NOT NULL,
  username TEXT UNIQUE,
  phone TEXT,
  name TEXT,
  company TEXT,
  agent_code TEXT UNIQUE,
  password_hash TEXT,
  default_markup REAL DEFAULT 0.28,
  enabled INTEGER DEFAULT 1,
  data TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS categories (
  id TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  sort INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS factories (
  id TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  enabled INTEGER DEFAULT 1,
  sort INTEGER DEFAULT 0,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS materials (
  id TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  enabled INTEGER DEFAULT 1,
  sort INTEGER DEFAULT 0,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS presses (
  id TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  enabled INTEGER DEFAULT 1,
  sort INTEGER DEFAULT 0,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS sheets (
  id TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  enabled INTEGER DEFAULT 1,
  sort INTEGER DEFAULT 0,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS processes (
  id TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  enabled INTEGER DEFAULT 1,
  sort INTEGER DEFAULT 0,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS packagings (
  id TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  enabled INTEGER DEFAULT 1,
  sort INTEGER DEFAULT 0,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  status TEXT DEFAULT 'draft',
  category TEXT,
  kind TEXT,
  sort INTEGER DEFAULT 0,
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS quotes (
  no TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  agent_id TEXT,
  agent_code TEXT,
  customer_name TEXT,
  customer_phone TEXT,
  product_id TEXT,
  product_name TEXT,
  qty INTEGER,
  cost_total REAL,
  agent_total REAL,
  retail_total REAL,
  status TEXT,
  created_at TEXT,
  valid_until TEXT
);
CREATE TABLE IF NOT EXISTS orders (
  no TEXT PRIMARY KEY,
  quote_no TEXT,
  data TEXT NOT NULL,
  agent_id TEXT,
  customer_name TEXT,
  customer_phone TEXT,
  product_name TEXT,
  qty INTEGER,
  cost_total REAL,
  retail_total REAL,
  status TEXT,
  payment_status TEXT DEFAULT 'unpaid',
  created_at TEXT,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_quotes_created ON quotes(created_at);
CREATE INDEX IF NOT EXISTS idx_quotes_agent ON quotes(agent_id);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_agent ON orders(agent_id);
CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(customer_phone);
"""


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


class Database:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=20)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    # ------------------------------------------------------------------ init
    def init(self) -> None:
        with self.conn() as c:
            c.executescript(SCHEMA)
        self.seed()

    def seed(self) -> None:
        with self.conn() as c:
            if c.execute("SELECT COUNT(*) n FROM settings").fetchone()["n"] == 0:
                for k, v in catalog.DEFAULT_SETTINGS.items():
                    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (k, _json(v)))
                c.execute(
                    "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                    ("session_secret", _json(new_id("s", 40))),
                )
            if c.execute("SELECT COUNT(*) n FROM categories").fetchone()["n"] == 0:
                for item in catalog.CATEGORIES:
                    c.execute(
                        "INSERT OR REPLACE INTO categories(id,data,sort) VALUES(?,?,?)",
                        (item["id"], _json(item), item.get("sort", 0)),
                    )
            for table, items in (
                ("factories", catalog.FACTORIES),
                ("materials", catalog.MATERIALS),
                ("presses", catalog.PRESSES),
                ("sheets", catalog.SHEETS),
                ("processes", catalog.PROCESSES),
                ("packagings", catalog.PACKAGINGS),
            ):
                if c.execute("SELECT COUNT(*) n FROM %s" % table).fetchone()["n"] == 0:
                    for item in items:
                        c.execute(
                            "INSERT OR REPLACE INTO %s(id,data,enabled,sort,updated_at) VALUES(?,?,?,?,?)" % table,
                            (item["id"], _json(item), int(item.get("enabled", 1)), int(item.get("sort", 0)), now_str()),
                        )
            if c.execute("SELECT COUNT(*) n FROM products").fetchone()["n"] == 0:
                for item in catalog.PRODUCTS:
                    c.execute(
                        "INSERT OR REPLACE INTO products(id,data,status,category,kind,sort,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                        (
                            item["id"], _json(item), item.get("status", "active"), item.get("category", ""),
                            item.get("kind", "custom"), int(item.get("sort", 0)), now_str(), now_str(),
                        ),
                    )
            if c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"] == 0:
                for u in catalog.DEFAULT_USERS:
                    c.execute(
                        "INSERT INTO users(id,role,username,phone,name,company,agent_code,password_hash,default_markup,enabled,data,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            u["id"], u["role"], u["username"], u["phone"], u["name"], u.get("company", ""),
                            u.get("agent_code", ""), hash_password(u["password"]), float(u.get("default_markup", 0)),
                            int(u.get("enabled", 1)), "{}", now_str(),
                        ),
                    )

    # -------------------------------------------------------------- settings
    def settings(self) -> Dict[str, Any]:
        with self.conn() as c:
            rows = c.execute("SELECT key,value FROM settings").fetchall()
        out = {}
        for r in rows:
            try:
                out[r["key"]] = json.loads(r["value"])
            except Exception:
                out[r["key"]] = r["value"]
        return out

    def setting(self, key: str, default: Any = None) -> Any:
        with self.conn() as c:
            row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]

    def save_settings(self, values: Dict[str, Any]) -> None:
        with self.conn() as c:
            for k, v in values.items():
                c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (k, _json(v)))

    def session_secret(self) -> str:
        s = self.setting("session_secret")
        if not s:
            s = new_id("s", 40)
            self.save_settings({"session_secret": s})
        return str(s)

    # ------------------------------------------------------------- libraries
    def list_library(self, table: str, only_enabled: bool = False) -> List[Dict[str, Any]]:
        if table not in ("materials", "presses", "sheets", "processes", "packagings"):
            raise ValueError("bad table")
        sql = "SELECT data FROM %s" % table
        if only_enabled and table != "sheets":
            sql += " WHERE enabled=1"
        sql += " ORDER BY sort, id"
        with self.conn() as c:
            rows = c.execute(sql).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def get_library(self, table: str, item_id: str) -> Optional[Dict[str, Any]]:
        if table not in ("materials", "presses", "sheets", "processes", "packagings"):
            raise ValueError("bad table")
        with self.conn() as c:
            row = c.execute("SELECT data FROM %s WHERE id=?" % table, (item_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    def save_library(self, table: str, item: Dict[str, Any]) -> Dict[str, Any]:
        if table not in ("materials", "presses", "sheets", "processes", "packagings"):
            raise ValueError("bad table")
        item = dict(item)
        item.setdefault("id", new_id("lib-", 8))
        with self.conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO %s(id,data,enabled,sort,updated_at) VALUES(?,?,?,?,?)" % table,
                (item["id"], _json(item), int(item.get("enabled", 1)), int(item.get("sort", 0)), now_str()),
            )
        return item

    def delete_library(self, table: str, item_id: str) -> None:
        if table not in ("materials", "presses", "sheets", "processes", "packagings"):
            raise ValueError("bad table")
        with self.conn() as c:
            c.execute("DELETE FROM %s WHERE id=?" % table, (item_id,))

    def list_factories(self, include_disabled: bool = True) -> List[Dict[str, Any]]:
        sql = "SELECT data FROM factories"
        if not include_disabled:
            sql += " WHERE enabled=1"
        sql += " ORDER BY sort,id"
        with self.conn() as c:
            rows = c.execute(sql).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def get_factory(self, fid: str) -> Optional[Dict[str, Any]]:
        with self.conn() as c:
            row = c.execute("SELECT data FROM factories WHERE id=?", (fid,)).fetchone()
        return json.loads(row["data"]) if row else None

    def save_factory(self, item: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(item or {})
        data.setdefault("id", new_id("fac-", 8))
        data.setdefault("name", "未命名工厂")
        data.setdefault("type", "other")
        data.setdefault("price_factor", 1.0)
        data.setdefault("fixed_fee", 0)
        data.setdefault("lead_days", 0)
        data.setdefault("note", "")
        data.setdefault("enabled", 1)
        data.setdefault("sort", 0)
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO factories(id,data,enabled,sort,updated_at) VALUES(?,?,?,?,?)",
                      (data["id"], _json(data), int(data.get("enabled", 1)), int(data.get("sort", 0)), now_str()))
        return data

    def delete_factory(self, fid: str) -> Tuple[bool, str]:
        presses = [p for p in self.list_library("presses") if p.get("factory_id") == fid]
        if presses:
            return False, "还有 %d 台设备归属该工厂，请先调整设备" % len(presses)
        with self.conn() as c:
            rows = c.execute("SELECT data FROM products").fetchall()
        used = []
        for r in rows:
            p = json.loads(r["data"])
            if fid in (p.get("source_ids") or []):
                used.append(p.get("name") or p.get("id"))
        if used:
            return False, "还有商品引用该工厂：%s" % "、".join(used[:3])
        with self.conn() as c:
            c.execute("DELETE FROM factories WHERE id=?", (fid,))
        return True, ""

    def admin_factories(self) -> List[Dict[str, Any]]:
        facts = self.list_factories()
        presses = self.list_library("presses")
        products = self.list_products(include_inactive=True)
        for f in facts:
            f["press_count"] = sum(1 for p in presses if p.get("factory_id") == f["id"])
            f["product_count"] = sum(1 for p in products if f["id"] in (p.get("source_ids") or []))
        return facts

    def categories(self) -> List[Dict[str, Any]]:
        with self.conn() as c:
            rows = c.execute("SELECT data FROM categories ORDER BY sort,id").fetchall()
        out = []
        for r in rows:
            item = json.loads(r["data"])
            item.setdefault("code", str(item.get("id", "")).upper())
            item.setdefault("parent_id", "")
            item.setdefault("enabled", 1)
            item.setdefault("pricing_default", "nonstandard")
            out.append(item)
        return out

    def admin_categories(self) -> List[Dict[str, Any]]:
        cats = self.categories()
        products = self.list_products(include_inactive=True)
        counts: Dict[str, int] = {}
        for p in products:
            counts[p.get("category", "")] = counts.get(p.get("category", ""), 0) + 1
        for c in cats:
            c["product_count"] = counts.get(c["id"], 0)
        return cats

    def save_category(self, item: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(item or {})
        data.setdefault("id", new_id("cat-", 8))
        data.setdefault("code", str(data["id"]).upper())
        data.setdefault("name", "未命名类目")
        data.setdefault("parent_id", "")
        data.setdefault("desc", "")
        data.setdefault("image", "")
        data.setdefault("sort", 0)
        data.setdefault("enabled", 1)
        data.setdefault("pricing_default", "nonstandard")
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO categories(id,data,sort) VALUES(?,?,?)",
                      (data["id"], _json(data), int(data.get("sort", 0))))
        return data

    def delete_category(self, cat_id: str) -> Tuple[bool, str]:
        with self.conn() as c:
            n = c.execute("SELECT COUNT(*) n FROM products WHERE category=?", (cat_id,)).fetchone()["n"]
            if n:
                return False, "该类目下还有 %d 个商品，不能删除" % n
            c.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        return True, ""

    # -------------------------------------------------------------- products
    def list_products(self, include_inactive: bool = False, category: str = "", kind: str = "", q: str = "") -> List[Dict[str, Any]]:
        sql = "SELECT data,status FROM products WHERE 1=1"
        args: List[Any] = []
        if not include_inactive:
            sql += " AND status='active'"
        if category:
            sql += " AND category=?"
            args.append(category)
        if kind:
            sql += " AND kind=?"
            args.append(kind)
        if q:
            sql += " AND data LIKE ?"
            args.append("%" + q + "%")
        sql += " ORDER BY sort, id"
        with self.conn() as c:
            rows = c.execute(sql, args).fetchall()
        out = []
        for r in rows:
            item = json.loads(r["data"])
            item["status"] = r["status"]
            item.setdefault("pricing_mode", "nonstandard")
            out.append(item)
        return out

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        with self.conn() as c:
            row = c.execute("SELECT data,status FROM products WHERE id=?", (product_id,)).fetchone()
        if not row:
            return None
        item = json.loads(row["data"])
        item["status"] = row["status"]
        item.setdefault("pricing_mode", "nonstandard")
        return item

    def save_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        item = dict(product)
        if not item.get("id"):
            item["id"] = new_id("p-", 8)
        item.setdefault("pricing_mode", "nonstandard")
        status = item.get("status") or "draft"
        item["status"] = status
        item.setdefault("created_at", now_str())
        item["updated_at"] = now_str()
        with self.conn() as c:
            exists = c.execute("SELECT id FROM products WHERE id=?", (item["id"],)).fetchone()
            if exists:
                c.execute(
                    "UPDATE products SET data=?,status=?,category=?,kind=?,sort=?,updated_at=? WHERE id=?",
                    (
                        _json(item), status, item.get("category", ""), item.get("kind", "custom"),
                        int(item.get("sort", 0)), now_str(), item["id"],
                    ),
                )
            else:
                c.execute(
                    "INSERT INTO products(id,data,status,category,kind,sort,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        item["id"], _json(item), status, item.get("category", ""), item.get("kind", "custom"),
                        int(item.get("sort", 0)), item.get("created_at", now_str()), now_str(),
                    ),
                )
        return item

    def set_product_status(self, product_id: str, status: str) -> None:
        with self.conn() as c:
            row = c.execute("SELECT data FROM products WHERE id=?", (product_id,)).fetchone()
            if not row:
                return
            item = json.loads(row["data"])
            item["status"] = status
            c.execute("UPDATE products SET data=?,status=?,updated_at=? WHERE id=?", (_json(item), status, now_str(), product_id))

    # ------------------------------------------------------------------ users
    def user_by_id(self, uid: str) -> Optional[Dict[str, Any]]:
        with self.conn() as c:
            row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else None

    def user_by_login(self, login: str) -> Optional[Dict[str, Any]]:
        with self.conn() as c:
            row = c.execute("SELECT * FROM users WHERE username=? OR phone=?", (login, login)).fetchone()
        return dict(row) if row else None

    def user_by_agent_code(self, code: str) -> Optional[Dict[str, Any]]:
        if not code:
            return None
        with self.conn() as c:
            row = c.execute("SELECT * FROM users WHERE agent_code=? AND role='agent' AND enabled=1", (code,)).fetchone()
        return dict(row) if row else None

    def list_agents(self) -> List[Dict[str, Any]]:
        with self.conn() as c:
            rows = c.execute("SELECT * FROM users WHERE role='agent' ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def save_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        item = dict(user)
        item.setdefault("id", new_id("u-", 8))
        now = now_str()
        with self.conn() as c:
            row = c.execute("SELECT * FROM users WHERE id=?", (item["id"],)).fetchone()
            if row:
                fields = []
                args: List[Any] = []
                for k in ("role", "username", "phone", "name", "company", "agent_code", "default_markup", "enabled"):
                    if k in item:
                        fields.append("%s=?" % k)
                        args.append(item[k])
                if item.get("password"):
                    fields.append("password_hash=?")
                    args.append(hash_password(item["password"]))
                if fields:
                    args.append(item["id"])
                    c.execute("UPDATE users SET %s WHERE id=?" % ",".join(fields), args)
            else:
                c.execute(
                    "INSERT INTO users(id,role,username,phone,name,company,agent_code,password_hash,default_markup,enabled,data,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        item["id"], item.get("role", "agent"), item.get("username", item.get("phone", "")),
                        item.get("phone", ""), item.get("name", ""), item.get("company", ""),
                        item.get("agent_code", ""), hash_password(item.get("password", "123456")),
                        float(item.get("default_markup", 0.28)), int(item.get("enabled", 1)), "{}", now,
                    ),
                )
        return self.user_by_id(item["id"]) or item

    # ---------------------------------------------------------------- quotes
    def save_quote(self, no: str, data: Dict[str, Any], valid_until: str) -> None:
        with self.conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO quotes(no,data,agent_id,agent_code,customer_name,customer_phone,product_id,product_name,qty,cost_total,agent_total,retail_total,status,created_at,valid_until) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    no, _json(data), data.get("agent_id"), data.get("agent_code"),
                    (data.get("customer") or {}).get("name", ""), (data.get("customer") or {}).get("phone", ""),
                    (data.get("product") or {}).get("id", ""), (data.get("product") or {}).get("name", ""),
                    int(data.get("qty", 0)), float(data.get("totals", {}).get("cost", 0)),
                    float(data.get("totals", {}).get("agent", 0)), float(data.get("totals", {}).get("retail", 0)),
                    data.get("status", "active"), data.get("created_at", now_str()), valid_until,
                ),
            )

    def get_quote(self, no: str) -> Optional[Dict[str, Any]]:
        with self.conn() as c:
            row = c.execute("SELECT data FROM quotes WHERE no=?", (no,)).fetchone()
        return json.loads(row["data"]) if row else None

    def update_quote_data(self, no: str, data: Dict[str, Any]) -> None:
        with self.conn() as c:
            row = c.execute("SELECT data FROM quotes WHERE no=?", (no,)).fetchone()
            if not row:
                return
            c.execute(
                "UPDATE quotes SET data=?,status=?,retail_total=?,agent_total=?,cost_total=? WHERE no=?",
                (
                    _json(data), data.get("status", "active"), float(data.get("totals", {}).get("retail", 0)),
                    float(data.get("totals", {}).get("agent", 0)), float(data.get("totals", {}).get("cost", 0)), no,
                ),
            )

    def set_quote_status(self, no: str, status: str) -> None:
        with self.conn() as c:
            row = c.execute("SELECT data FROM quotes WHERE no=?", (no,)).fetchone()
            if not row:
                return
            data = json.loads(row["data"])
            data["status"] = status
            c.execute("UPDATE quotes SET data=?,status=? WHERE no=?", (_json(data), status, no))

    def list_quotes(self, agent_id: str = "", status: str = "", q: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT data FROM quotes WHERE 1=1"
        args: List[Any] = []
        if agent_id:
            sql += " AND agent_id=?"
            args.append(agent_id)
        if status:
            sql += " AND status=?"
            args.append(status)
        if q:
            sql += " AND (no LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ? OR product_name LIKE ?)"
            args += ["%" + q + "%"] * 4
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self.conn() as c:
            rows = c.execute(sql, args).fetchall()
        return [json.loads(r["data"]) for r in rows]

    # ---------------------------------------------------------------- orders
    def save_order(self, no: str, data: Dict[str, Any]) -> None:
        with self.conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO orders(no,quote_no,data,agent_id,customer_name,customer_phone,product_name,qty,cost_total,retail_total,status,payment_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    no, data.get("quote_no"), _json(data), data.get("agent_id"),
                    (data.get("customer") or {}).get("name", ""), (data.get("customer") or {}).get("phone", ""),
                    (data.get("product") or {}).get("name", ""), int(data.get("qty", 0)),
                    float(data.get("totals", {}).get("cost", 0)), float(data.get("totals", {}).get("retail", 0)),
                    data.get("status", "pending"), data.get("payment_status", "unpaid"),
                    data.get("created_at", now_str()), now_str(),
                ),
            )

    def get_order(self, no: str) -> Optional[Dict[str, Any]]:
        with self.conn() as c:
            row = c.execute("SELECT data FROM orders WHERE no=?", (no,)).fetchone()
        return json.loads(row["data"]) if row else None

    def update_order(self, no: str, **kwargs) -> None:
        with self.conn() as c:
            row = c.execute("SELECT data FROM orders WHERE no=?", (no,)).fetchone()
            if not row:
                return
            data = json.loads(row["data"])
            for k in ("status", "payment_status", "admin_note", "logistics_note"):
                if k in kwargs:
                    data[k] = kwargs[k]
            data["updated_at"] = now_str()
            c.execute(
                "UPDATE orders SET data=?,status=?,payment_status=?,updated_at=? WHERE no=?",
                (_json(data), data.get("status", "pending"), data.get("payment_status", "unpaid"), now_str(), no),
            )

    def list_orders(self, agent_id: str = "", status: str = "", q: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT data FROM orders WHERE 1=1"
        args: List[Any] = []
        if agent_id:
            sql += " AND agent_id=?"
            args.append(agent_id)
        if status:
            sql += " AND status=?"
            args.append(status)
        if q:
            sql += " AND (no LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ? OR product_name LIKE ?)"
            args += ["%" + q + "%"] * 4
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self.conn() as c:
            rows = c.execute(sql, args).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def orders_by_phone(self, phone: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT data FROM orders WHERE customer_phone=? ORDER BY created_at DESC LIMIT ?",
                (phone, limit),
            ).fetchall()
        return [json.loads(r["data"]) for r in rows]

    # -------------------------------------------------------------- analytics
    def analytics(self) -> Dict[str, Any]:
        today = time.strftime("%Y-%m-%d")
        month = time.strftime("%Y-%m")
        with self.conn() as c:
            q_today = c.execute("SELECT COUNT(*) n FROM quotes WHERE substr(created_at,1,10)=?", (today,)).fetchone()["n"]
            o_today = c.execute("SELECT COUNT(*) n FROM orders WHERE substr(created_at,1,10)=?", (today,)).fetchone()["n"]
            pending = c.execute("SELECT COUNT(*) n FROM orders WHERE status IN ('pending','confirmed','producing')").fetchone()["n"]
            gmv = c.execute("SELECT COALESCE(SUM(retail_total),0) s FROM orders WHERE status!='cancelled' AND substr(created_at,1,7)=?", (month,)).fetchone()["s"]
            cost = c.execute("SELECT COALESCE(SUM(cost_total),0) s FROM orders WHERE status!='cancelled' AND substr(created_at,1,7)=?", (month,)).fetchone()["s"]
            all_orders = c.execute("SELECT COUNT(*) n, COALESCE(SUM(retail_total),0) s FROM orders WHERE status!='cancelled'").fetchone()
            converted = c.execute("SELECT COUNT(*) n FROM quotes WHERE status='converted'").fetchone()["n"]
            total_quotes = c.execute("SELECT COUNT(*) n FROM quotes").fetchone()["n"]
            by_status = c.execute("SELECT status, COUNT(*) n FROM orders GROUP BY status").fetchall()
            by_product = c.execute(
                "SELECT product_name, COUNT(*) n, COALESCE(SUM(retail_total),0) s FROM orders WHERE status!='cancelled' GROUP BY product_name ORDER BY s DESC LIMIT 6"
            ).fetchall()
            last7 = c.execute(
                "SELECT substr(created_at,1,10) d, COUNT(*) n, COALESCE(SUM(retail_total),0) s FROM orders WHERE created_at>=date('now','-6 day') GROUP BY d ORDER BY d"
            ).fetchall()
        return {
            "quotes_today": q_today,
            "orders_today": o_today,
            "pending_orders": pending,
            "month_gmv": round(float(gmv or 0), 2),
            "month_cost": round(float(cost or 0), 2),
            "month_profit": round(float(gmv or 0) - float(cost or 0), 2),
            "order_count": int(all_orders["n"] or 0),
            "order_total": round(float(all_orders["s"] or 0), 2),
            "conversion": round((converted / total_quotes) if total_quotes else 0, 3),
            "by_status": [dict(r) for r in by_status],
            "by_product": [dict(r) for r in by_product],
            "last7": [dict(r) for r in last7],
        }

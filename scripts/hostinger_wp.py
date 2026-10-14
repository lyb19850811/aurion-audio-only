#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hostinger 共享主机 WordPress 管理工具（REST API，无需 SSH）。

通过 WordPress REST API 管理页面/文章/菜单/产品。

认证：
  - 页面/文章/菜单：WordPress 应用密码（Basic Auth：用户名 + 应用密码）
  - 产品（WooCommerce）：Consumer Key + Consumer Secret（Basic Auth）

配置：复制 .env.hostinger.example 为 .env.hostinger 并填写。

用法示例：
  python3 scripts/hostinger_wp.py page list
  python3 scripts/hostinger_wp.py page create --title "FAQ" --slug faq --content content/faq.html
  python3 scripts/hostinger_wp.py page update faq --content content/faq.html
  python3 scripts/hostinger_wp.py menu list
  python3 scripts/hostinger_wp.py menu add-custom "外部连接" "#" --parent-id 33
  python3 scripts/hostinger_wp.py product list
  python3 scripts/hostinger_wp.py product create --name "Aurion A1" --price 199
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parent.parent

ENV_KEYS = ("WP_URL", "WP_USER", "WP_APP_PASSWORD", "WC_CONSUMER_KEY", "WC_CONSUMER_SECRET")


def load_cfg():
    """从 .env.hostinger 读取配置，环境变量可覆盖。"""
    cfg = {}
    env_file = BASE_DIR / ".env.hostinger"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    for k in ENV_KEYS:
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


def basic_auth(user, pwd):
    return "Basic " + base64.b64encode(f"{user}:{pwd}".encode()).decode()


def request(cfg, path, method="GET", data=None, auth_type="wp"):
    """发 REST 请求，返回 (status_code, parsed_json)。"""
    url = cfg["WP_URL"].rstrip("/") + path
    headers = {"Accept": "application/json"}
    if auth_type == "wp":
        headers["Authorization"] = basic_auth(cfg.get("WP_USER", ""), cfg.get("WP_APP_PASSWORD", ""))
    else:  # wc
        headers["Authorization"] = basic_auth(cfg.get("WC_CONSUMER_KEY", ""), cfg.get("WC_CONSUMER_SECRET", ""))
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode() or "null"
            return resp.status, json.loads(raw)
    except HTTPError as e:
        return e.code, {"error": e.read().decode()[:500]}
    except URLError as e:
        return 0, {"error": str(e)}


def read_content(src):
    """--content 传文件路径则读文件；否则当作 HTML 字符串本身。"""
    p = Path(src)
    if not p.is_absolute():
        p = BASE_DIR / p
    return p.read_text() if p.exists() else src


def find_page(cfg, slug):
    """按 slug 找页面，返回 (id, ...) 或 (None, None)。"""
    code, resp = request(cfg, f"/wp-json/wp/v2/pages?slug={slug}&status=publish,draft,future,private")
    if code == 200 and resp:
        return resp[0]["id"], resp[0]
    return None, None


def print_item(item, fields=("id", "title", "slug", "status")):
    line = "  ".join(f"{f}={item.get(f)}" for f in fields)
    print(line)


# ---------- 页面 ----------

def cmd_page_list(cfg, args):
    code, resp = request(cfg, "/wp-json/wp/v2/pages?per_page=100&status=publish,draft,future,private")
    if code != 200:
        print(f"失败 {code}: {resp.get('error')}", file=sys.stderr)
        return 1
    for it in resp:
        print_item(it, ("id", "slug", "status"))
        print(f"        {it.get('title', {}).get('rendered', '')}")
    return 0


def cmd_page_create(cfg, args):
    data = {"title": args.title, "status": args.status}
    if args.slug:
        data["slug"] = args.slug
    if args.content:
        data["content"] = read_content(args.content)
    code, resp = request(cfg, "/wp-json/wp/v2/pages", "POST", data)
    if code in (200, 201):
        print(f"已创建页面 id={resp['id']} slug={resp['slug']}")
        return 0
    print(f"失败 {code}: {resp.get('error')}", file=sys.stderr)
    return 1


def cmd_page_update(cfg, args):
    pid, _ = find_page(cfg, args.slug)
    if not pid:
        print(f"未找到页面 slug={args.slug}", file=sys.stderr)
        return 1
    data = {}
    if args.title:
        data["title"] = args.title
    if args.content:
        data["content"] = read_content(args.content)
    if args.status:
        data["status"] = args.status
    code, resp = request(cfg, f"/wp-json/wp/v2/pages/{pid}", "POST", data)
    if code == 200:
        print(f"已更新页面 id={pid}")
        return 0
    print(f"失败 {code}: {resp.get('error')}", file=sys.stderr)
    return 1


def cmd_page_delete(cfg, args):
    pid, _ = find_page(cfg, args.slug)
    if not pid:
        print(f"未找到页面 slug={args.slug}", file=sys.stderr)
        return 1
    code, resp = request(cfg, f"/wp-json/wp/v2/pages/{pid}", "DELETE")
    if code == 200:
        print(f"已删除页面 id={pid}")
        return 0
    print(f"失败 {code}: {resp.get('error')}", file=sys.stderr)
    return 1


# ---------- 文章 ----------

def cmd_post_list(cfg, args):
    code, resp = request(cfg, "/wp-json/wp/v2/posts?per_page=100&status=publish,draft,future,private")
    if code != 200:
        print(f"失败 {code}: {resp.get('error')}", file=sys.stderr)
        return 1
    for it in resp:
        print_item(it, ("id", "slug", "status"))
        print(f"        {it.get('title', {}).get('rendered', '')}")
    return 0


def cmd_post_create(cfg, args):
    data = {"title": args.title, "status": args.status}
    if args.slug:
        data["slug"] = args.slug
    if args.content:
        data["content"] = read_content(args.content)
    code, resp = request(cfg, "/wp-json/wp/v2/posts", "POST", data)
    if code in (200, 201):
        print(f"已创建文章 id={resp['id']} slug={resp['slug']}")
        return 0
    print(f"失败 {code}: {resp.get('error')}", file=sys.stderr)
    return 1


# ---------- 菜单 ----------

def cmd_menu_list(cfg, args):
    code, resp = request(cfg, "/wp-json/wp/v2/menus?per_page=100")
    if code != 200:
        print(f"失败 {code}: {resp.get('error')}", file=sys.stderr)
        return 1
    for it in resp:
        print(f"id={it['id']}  name={it['name']}  slug={it['slug']}")
    return 0


def cmd_menu_items(cfg, args):
    code, resp = request(cfg, f"/wp-json/wp/v2/menu-items?menus={args.menu_id}&per_page=100")
    if code != 200:
        print(f"失败 {code}: {resp.get('error')}", file=sys.stderr)
        return 1
    for it in resp:
        parent = it.get("parent", 0)
        url = it.get("url", "")
        print(f"id={it['id']}  title={it['title']['rendered'] if isinstance(it.get('title'), dict) else it.get('title')}  url={url}  parent={parent}")
    return 0


def cmd_menu_add_custom(cfg, args):
    data = {"title": args.title, "url": args.url, "menus": args.menu_id, "status": "publish"}
    if args.parent_id:
        data["parent"] = int(args.parent_id)
    code, resp = request(cfg, "/wp-json/wp/v2/menu-items", "POST", data)
    if code in (200, 201):
        print(f"已添加菜单项 id={resp['id']}")
        return 0
    print(f"失败 {code}: {resp.get('error')}", file=sys.stderr)
    return 1


# ---------- 产品（WooCommerce） ----------

def cmd_product_list(cfg, args):
    code, resp = request(cfg, "/wp-json/wc/v3/products?per_page=100", auth_type="wc")
    if code != 200:
        print(f"失败 {code}: {resp.get('error')}", file=sys.stderr)
        return 1
    for it in resp:
        print(f"id={it['id']}  name={it['name']}  price={it.get('price')}  status={it['status']}")
    return 0


def cmd_product_create(cfg, args):
    data = {"name": args.name, "type": args.type, "status": "publish"}
    if args.price:
        data["regular_price"] = args.price
    if args.description:
        data["description"] = args.description
    code, resp = request(cfg, "/wp-json/wc/v3/products", "POST", data, auth_type="wc")
    if code in (200, 201):
        print(f"已创建产品 id={resp['id']}")
        return 0
    print(f"失败 {code}: {resp.get('error')}", file=sys.stderr)
    return 1


def build_parser():
    p = argparse.ArgumentParser(description="Hostinger WordPress REST API 管理工具")
    sub = p.add_subparsers(dest="cmd", required=True)

    pg = sub.add_parser("page", help="页面管理")
    pgsub = pg.add_subparsers(dest="sub", required=True)
    pgsub.add_parser("list", help="列出页面")
    pg_create = pgsub.add_parser("create", help="创建页面")
    pg_create.add_argument("--title", required=True)
    pg_create.add_argument("--slug")
    pg_create.add_argument("--content", help="内容文件路径或 HTML 字符串")
    pg_create.add_argument("--status", default="publish")
    pg_update = pgsub.add_parser("update", help="按 slug 更新页面")
    pg_update.add_argument("slug")
    pg_update.add_argument("--title")
    pg_update.add_argument("--content")
    pg_update.add_argument("--status")
    pg_delete = pgsub.add_parser("delete", help="按 slug 删除页面")
    pg_delete.add_argument("slug")

    po = sub.add_parser("post", help="文章管理")
    posub = po.add_subparsers(dest="sub", required=True)
    posub.add_parser("list", help="列出文章")
    po_create = posub.add_parser("create", help="创建文章")
    po_create.add_argument("--title", required=True)
    po_create.add_argument("--slug")
    po_create.add_argument("--content")
    po_create.add_argument("--status", default="publish")

    mn = sub.add_parser("menu", help="菜单管理")
    mnsub = mn.add_subparsers(dest="sub", required=True)
    mnsub.add_parser("list", help="列出菜单")
    mn_items = mnsub.add_parser("items", help="列出某菜单的菜单项")
    mn_items.add_argument("menu_id")
    mn_add = mnsub.add_parser("add-custom", help="添加自定义链接菜单项")
    mn_add.add_argument("title")
    mn_add.add_argument("url")
    mn_add.add_argument("--menu-id", type=int, required=True, help="菜单 ID（menu list 查看）")
    mn_add.add_argument("--parent-id", type=int, help="父级菜单项 ID（做成下拉）")

    pr = sub.add_parser("product", help="产品管理（WooCommerce）")
    prsub = pr.add_subparsers(dest="sub", required=True)
    prsub.add_parser("list", help="列出产品")
    pr_create = prsub.add_parser("create", help="创建产品")
    pr_create.add_argument("--name", required=True)
    pr_create.add_argument("--price")
    pr_create.add_argument("--type", default="simple")
    pr_create.add_argument("--description")
    return p


def main():
    args = build_parser().parse_args()
    cfg = load_cfg()
    if not cfg.get("WP_URL"):
        print("错误：未配置 WP_URL。请复制 .env.hostinger.example 为 .env.hostinger 并填写。", file=sys.stderr)
        sys.exit(1)
    handler = {
        ("page", "list"): cmd_page_list,
        ("page", "create"): cmd_page_create,
        ("page", "update"): cmd_page_update,
        ("page", "delete"): cmd_page_delete,
        ("post", "list"): cmd_post_list,
        ("post", "create"): cmd_post_create,
        ("menu", "list"): cmd_menu_list,
        ("menu", "items"): cmd_menu_items,
        ("menu", "add-custom"): cmd_menu_add_custom,
        ("product", "list"): cmd_product_list,
        ("product", "create"): cmd_product_create,
    }.get((args.cmd, args.sub))
    if not handler:
        print("未知命令", file=sys.stderr)
        sys.exit(1)
    sys.exit(handler(cfg, args))


if __name__ == "__main__":
    main()

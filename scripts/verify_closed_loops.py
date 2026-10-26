"""验证两条核心闭环：

A. 未审核群聊结论不进索引 → 审核发布后被引用 → 撤销后停止引用
B. 草稿编辑 → 确认 → 标记人工已回复（含「改后需重新确认」约束）
"""

import http.client
import re
import sys
from urllib.parse import urlencode

HOST, PORT = "127.0.0.1", 8000


def call(method, path, body=None, cookie=None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=20)
    headers = {"Accept": "text/html"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urlencode(body)
    if cookie:
        headers["Cookie"] = cookie
    conn.request(method, path, data, headers)
    res = conn.getresponse()
    text = res.read().decode("utf-8", "replace")
    ck = res.getheader("set-cookie")
    conn.close()
    return {"status": res.status, "location": res.getheader("location"), "html": text,
            "cookie": ck.split(";")[0] if ck else cookie}


def login(username):
    r = call("POST", "/login", {"username": username, "password": "Demo-Only-2026!"})
    if r["status"] != 303:
        sys.exit(f"登录失败 {username}: {r['status']}")
    return r["cookie"]


def latest_block(cookie, cid):
    """只取最新一条草稿的区块。列表按创建时间倒序，所以第一个草稿块就是最新。"""
    r = call("GET", f"/c/{cid}", cookie=cookie)
    html = r["html"]
    blocks = re.split(r'(?=<div class="card mb-3" id="draft-)', html)
    blocks = [b for b in blocks if b.startswith('<div class="card mb-3" id="draft-')]
    return re.sub(r"<[^>]+>", " ", blocks[0]) if blocks else ""


def citations(cookie, cid):
    text = latest_block(cookie, cid)
    return [c.strip() for c in re.findall(r"\n\s*([^\n]+?)\s*\n\s*(?:可外发|仅内部)", text)]


def draft_id(cookie, cid):
    r = call("GET", f"/c/{cid}", cookie=cookie)
    m = re.search(r'id="draft-([^"]+)"', r["html"])
    return m.group(1) if m else None


def new_draft_citations(cookie, cid, question):
    """提问后返回最新草稿的引用，避免把历史草稿混进来。"""
    ask(cookie, cid, question)
    return citations(cookie, cid)


def ask(cookie, cid, question):
    r = call("POST", f"/c/{cid}/ask", {"question": question}, cookie)
    return r["status"]


def pending_knowledge_id(cookie):
    r = call("GET", "/knowledge", cookie=cookie)
    m = re.search(r'action="/knowledge/([^/"]+)/publish"', r["html"])
    return m.group(1) if m else None


print("=" * 66)
print("闭环 A：群聊候选知识 —— 审核前 / 发布后 / 撤销后")
print("=" * 66)

staff = login("staff-a")
reviewer = login("reviewer")

Q = "DataPilot 3.2 备份任务显示成功但对象找不到，应该查什么？"

ask(staff, "conv-a-backup", Q)
before = citations(staff, "conv-a-backup")
print(f"\n[审核前] 引用来源：{before}")

kid = pending_knowledge_id(reviewer)
if not kid:
    sys.exit("未找到待审核候选知识")
print(f"[待审核] 候选知识 ID：{kid}")

r = call("GET", "/knowledge", cookie=reviewer)
content = re.search(r'<textarea class="form-control" name="content" rows="5">(.*?)</textarea>', r["html"], re.S)
content = content.group(1) if content else ""
verification = "演示审核：已核对 DEMO-42 工单，确认为客户查看了错误 prefix"

r = call("POST", f"/knowledge/{kid}/publish",
         {"content": content, "lower": "3.2", "upper": "3.2",
          "verification": verification, "public_approved": "false",
          "expected_revision": ""}, reviewer)
print(f"[发布]   HTTP {r['status']}")

ask(staff, "conv-a-backup", Q)
after = citations(staff, "conv-a-backup")
print(f"[发布后] 引用来源：{after}")

stale_draft = draft_id(staff, "conv-a-backup")

r = call("POST", f"/knowledge/{kid}/revoke", cookie=reviewer)
print(f"[撤销]   HTTP {r['status']}")

after_revoke = new_draft_citations(staff, "conv-a-backup", Q)
print(f"[撤销后] 新草稿引用来源：{after_revoke}")
print(f"         新答案已不再引用该知识 = {'已验证方案' not in ''.join(after_revoke)}")

r = call("GET", f"/c/conv-a-backup", cookie=staff)
revision = re.search(r'name="revision" value="(\d+)"', r["html"]).group(1)
r = call("POST", f"/drafts/{stale_draft}/confirm", {"revision": revision}, staff)
print(f"[拦截]   引用已撤销证据的旧草稿，确认请求 HTTP {r['status']}"
      f"（期望 409，即不允许带着失效证据发出）")

print(f"\n判定：审核前不含群聊结论={'已验证方案' not in ''.join(before)}；"
      f"发布后含={'已验证方案' in ''.join(after)}；"
      f"撤销后新答案不再引用={'已验证方案' not in ''.join(after_revoke)}")

print()
print("=" * 66)
print("闭环 B：编辑 → 确认 → 标记人工已回复")
print("=" * 66)

staff = login("staff-a")
r = call("GET", "/c/conv-b-alert", cookie=staff)
print(f"[提问]   HTTP {ask(staff, 'conv-b-alert', 'DataPilot 3.1 告警通知该怎么配置接收组？')}")

r = call("GET", "/c/conv-b-alert", cookie=staff)
did = re.search(r'id="draft-([^"]+)"', r["html"]).group(1)
revision = re.search(r'name="revision" value="(\d+)"', r["html"]).group(1)
edited = re.search(r'<textarea class="form-control mb-2" name="text" rows="6">(.*?)</textarea>', r["html"], re.S).group(1)
print(f"[草稿]   {did} 第 {revision} 版，长度 {len(edited)}")

r = call("POST", f"/drafts/{did}/edit", {"text": edited + "\n补充：请先确认接收组成员有效。", "revision": revision}, staff)
print(f"[编辑]   HTTP {r['status']}（编辑后 confirmed_hash 已失效，需重新确认）")

r = call("GET", "/c/conv-b-alert", cookie=staff)
revision2 = re.search(r'name="revision" value="(\d+)"', r["html"]).group(1)
r = call("POST", f"/drafts/{did}/confirm", {"revision": revision2}, staff)
print(f"[确认]   HTTP {r['status']}（revision={revision2}）")

r = call("GET", "/c/conv-b-alert", cookie=staff)
if r["html"].count('已确认') :
    print("[确认]   页面已出现「已确认」标记")
action = re.search(r'name="action_id" value="([^"]+)"', r["html"])
if not action:
    sys.exit("未生成回复动作，无法继续标记已回复")
r = call("POST", f"/drafts/{did}/sent", {"action_id": action.group(1)}, staff)
print(f"[标记]   HTTP {r['status']}")

r = call("GET", "/c/conv-b-alert", cookie=staff)
print(f"[结果]   页面出现「已标记人工回复」= {'已标记人工回复' in r['html']}")

r = call("GET", "/audits", cookie=staff)
rows = re.findall(r'<span class="badge badge-soft">([^<]+)</span>', r["html"])
print(f"[留痕]   审计动作序列：{rows}")

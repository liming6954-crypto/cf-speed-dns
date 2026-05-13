import os
import requests
import re
import traceback

# ==================== 环境变量 ====================
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")       # Cloudflare API Token
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")           # 072503.xyz 的 Zone ID
TG_CHAT_ID = os.environ.get("TG_CHAT_ID") or os.environ.get("TG_USER_ID")  # Telegram 通知的 Chat ID
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")       # Telegram Bot Token
DOMAIN_ROOT = "072503.xyz"                           # 主域名

# ==================== 配置区 ====================

# 不受脚本管理的 DNS 记录名（小写），不会被删除/修改
# 这些记录由手动管理或 Cloudflare 自动生成，脚本跳过
PROTECTED_NAMES = {
    "072503.xyz",                              # 根域 CNAME → Pages 项目
    "origin.072503.xyz",                       # SaaS Fallback Origin（橙色云，代理回源）
    "custom-hostname-fallback.072503.xyz",     # SaaS Fallback 辅助记录（橙色云）
}

# 需要开启代理（橙色云）的 A 记录名（小写）
# 不在此集合中的 A 记录默认为 DNS-only（灰云）
PROXIED_A_NAMES = {
    "custom-hostname-fallback.072503.xyz",     # SaaS 需要代理才能正常回源
}

# 优选IP的A记录
# 格式：(子域名, ipTop.html返回的IP索引)
# ipTop.html 只返回2条IP，索引0和1
A_RECORDS = [
    ("dns.072503.xyz",  0),                         # 优选IP入口1（IP[0]）
    ("dns.072503.xyz",  1),                         # 优选IP入口2（IP[1]）
    ("custom-hostname-fallback.072503.xyz", 0),     # SaaS fallback辅助，跟随优选IP[0]
]

# 直接CNAME记录（不走IP-tag模式，不需要Custom Hostname）
# 目标域名IP变化时自动跟随，无需脚本干预
DIRECT_CNAME_RECORDS = [
    ("dns1.072503.xyz", "saas.sin.fan"),   # 备用解析，拿到不同的CF IP
    ("dns2.072503.xyz", "saas.sin.fan"),   # 备用解析，拿到不同的CF IP
]

# IP-tag CNAME记录（需要Custom Hostname，IP变化时脚本自动同步）
# 格式：(标签, 优选域名, ipTop.html返回的IP索引)
# 脚本会生成记录名如：172-64-52-136.cf1.072503.xyz → www.visa.cn
# 并自动注册为 Custom Hostname，SaaS 接管流量
CNAME_RECORDS = [
    ("cf1", "www.visa.cn",      0),        # 优选域名1，用IP[0]
    ("cf1", "www.visa.cn",      1),        # 优选域名1，用IP[1]（同tag双IP）
    ("cf2", "store.ubi.com",    0),        # 优选域名2，用IP[0]
    ("cf3", "www.shopify.com",  1),        # 优选域名3，用IP[1]
    ("cf4", "mfa.gov.ua",       1),        # 优选域名4，用IP[1]
    ("cf5", "saas.sin.fan",     0),        # 优选域名5，用IP[0]
    ("cf6", "cf.877774.xyz",    0),        # 三网自适应，用IP[0]
    ("cf7", "asia.877774.xyz",  1),        # 亚洲优选，用IP[1]
    ("cf8", "eur.877774.xyz",   0),        # 欧洲优选，用IP[0]
    ("cf9", "na.877774.xyz",    1),        # 美洲优选，用IP[1]
]

# DNS记录总数上限（Cloudflare免费版最多200条，设50留余量）
MAX_TOTAL_RECORDS = 50

# ==================== API 基础 ====================
BASE_URL = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
HEADERS = {
    "Authorization": f"Bearer {CF_API_TOKEN}",
    "Content-Type": "application/json"
}

# ==================== Telegram 通知 ====================
def send_telegram(message):
    """发送 Telegram 通知，脚本运行结果推送到指定聊天"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("未配置TG通知")
        return
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.post(url, data=data, timeout=15)
        if resp.status_code == 200:
            print("Telegram通知发送成功")
        else:
            print("Telegram通知失败")
            print(resp.text)
    except Exception:
        traceback.print_exc()

# ==================== 工具函数 ====================
def is_valid_ipv4(ip):
    """验证是否为合法 IPv4 地址"""
    try:
        parts = ip.split(".")
        return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
    except Exception:
        return False

def ip_to_dash(ip):
    """IP地址中的点替换为横杠，用于生成子域名"""
    # 例：172.64.52.136 → 172-64-52-136
    return ip.replace(".", "-")

def cname_record_name(ip, cf_tag):
    """生成 IP-tag 格式的 CNAME 记录名"""
    # 例：172-64-52-136.cf1.072503.xyz
    return f"{ip_to_dash(ip)}.{cf_tag}.{DOMAIN_ROOT}"
def get_cf_speed_test_ip():
    urls = ["https://ip.164746.xyz/ipTop.html"]
    all_ips = []
    for url in urls:
        try:
            print(f"获取优选IP: {url}")
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', r.text)
            for ip in ips:
                if is_valid_ipv4(ip) and ip not in all_ips:
                    all_ips.append(ip)
            if all_ips:
                break
        except Exception:
            print(f"获取优选IP失败: {url}")
            traceback.print_exc()
    print(f"获取到 {len(all_ips)} 个优选IP")
    return all_ips

def get_existing_records():
    all_records = []
    page = 1
    try:
        while True:
            resp = requests.get(BASE_URL, headers=HEADERS, params={"per_page": 100, "page": page}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                print("Cloudflare API失败")
                print(data)
                return all_records
            records = data.get("result", [])
            all_records.extend(records)
            total_pages = data.get("result_info", {}).get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
    except Exception:
        print("获取DNS记录失败")
        traceback.print_exc()
    return all_records

def create_record(record_type, name, content, proxied=False):
    try:
        data = {"type": record_type, "name": name, "content": content, "ttl": 60, "proxied": proxied}
        resp = requests.post(BASE_URL, headers=HEADERS, json=data, timeout=15)
        result = resp.json()
        if result.get("success"):
            print(f"创建 {record_type} {name} -> {content} (proxied={proxied})")
            return True
        print(result)
        return False
    except Exception:
        traceback.print_exc()
        return False

def update_record(record_id, record_type, name, content, proxied=False):
    try:
        url = f"{BASE_URL}/{record_id}"
        data = {"type": record_type, "name": name, "content": content, "ttl": 60, "proxied": proxied}
        resp = requests.put(url, headers=HEADERS, json=data, timeout=15)
        result = resp.json()
        if result.get("success"):
            print(f"更新 {record_type} {name} -> {content} (proxied={proxied})")
            return True
        print(result)
        return False
    except Exception:
        traceback.print_exc()
        return False

def delete_record(record_id):
    try:
        url = f"{BASE_URL}/{record_id}"
        resp = requests.delete(url, headers=HEADERS, timeout=15)
        result = resp.json()
        if result.get("success"):
            print(f"删除记录 {record_id}")
            return True
        print(result)
        return False
    except Exception:
        traceback.print_exc()
        return False
CH_BASE_URL = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/custom_hostnames"

def get_custom_hostnames():
    all_ch = []
    page = 1
    try:
        while True:
            resp = requests.get(CH_BASE_URL, headers=HEADERS, params={"per_page": 50, "page": page}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                print("获取Custom Hostname失败")
                print(data)
                return all_ch
            results = data.get("result", [])
            all_ch.extend(results)
            total_pages = data.get("result_info", {}).get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
    except Exception:
        print("获取Custom Hostname异常")
        traceback.print_exc()
    return all_ch

def create_custom_hostname(hostname):
    try:
        data = {"hostname": hostname, "ssl": {"method": "http", "type": "dv", "wildcard": False}}
        resp = requests.post(CH_BASE_URL, headers=HEADERS, json=data, timeout=15)
        result = resp.json()
        if result.get("success"):
            print(f"创建 Custom Hostname: {hostname}")
            return True
        print(f"创建 Custom Hostname 失败: {hostname}")
        print(result)
        return False
    except Exception:
        traceback.print_exc()
        return False

def delete_custom_hostname(ch_id, hostname=""):
    try:
        url = f"{CH_BASE_URL}/{ch_id}"
        resp = requests.delete(url, headers=HEADERS, timeout=15)
        result = resp.json()
        if result.get("success"):
            print(f"删除 Custom Hostname: {hostname} ({ch_id})")
            return True
        print(f"删除 Custom Hostname 失败: {ch_id}")
        print(result)
        return False
    except Exception:
        traceback.print_exc()
        return False
def main():
    tg_results = []
    if not CF_API_TOKEN:
        print("缺少环境变量 CF_API_TOKEN")
        return
    if not CF_ZONE_ID:
        print("缺少环境变量 CF_ZONE_ID")
        return

    # 1. 获取优选IP
    ips = get_cf_speed_test_ip()
    if not ips:
        msg = "未获取到优选IP"
        print(msg)
        send_telegram(msg)
        return

    # 2. 获取现有 DNS 记录
    existing = get_existing_records()
    existing_a_map = {}
    for r in existing:
        if r["type"] == "A":
            key = (r["name"].lower(), r["content"])
            existing_a_map[key] = r
    existing_cname_map = {}
    for r in existing:
        if r["type"] == "CNAME":
            existing_cname_map[r["name"].lower()] = r

    # 3. 获取现有 Custom Hostname
    ch_list = get_custom_hostnames()
    ch_map = {}
    for ch in ch_list:
        ch_map[ch["hostname"].lower()] = ch

    updated_count = 0
    current_total_records = len(existing)

    # ==================== A 记录处理 ====================
    print("\n========== A记录 ==========\n")

    desired_a = []
    for domain, ip_index in A_RECORDS:
        ip = ips[ip_index % len(ips)]
        desired_a.append((domain.lower(), ip))

    existing_a_set = set(existing_a_map.keys())
    desired_a_set = set(desired_a)
    existing_a_by_name = {}
    for (name, ip), r in existing_a_map.items():
        existing_a_by_name.setdefault(name, []).append(r)

    for domain_lower, ip in desired_a:
        proxied = domain_lower in PROXIED_A_NAMES
        if (domain_lower, ip) in existing_a_set:
            existing_r = existing_a_map[(domain_lower, ip)]
            if existing_r.get("proxied") != proxied:
                success = update_record(existing_r["id"], "A", domain_lower, ip, proxied=proxied)
                if success:
                    updated_count += 1
                    tg_results.append(f"更新A代理状态\n{domain_lower}\nproxied={proxied}")
            else:
                print(f"跳过 A {domain_lower} -> {ip}")
                tg_results.append(f"跳过A\n{domain_lower}\n{ip}")
            continue
        same_name_records = existing_a_by_name.get(domain_lower, [])
        if same_name_records:
            record_to_update = None
            for r in same_name_records:
                if (domain_lower, r["content"]) not in desired_a_set:
                    record_to_update = r
                    break
            if record_to_update:
                success = update_record(record_to_update["id"], "A", domain_lower, ip, proxied=proxied)
                if success:
                    old_key = (domain_lower, record_to_update["content"])
                    existing_a_map.pop(old_key, None)
                    existing_a_set.discard(old_key)
                    new_key = (domain_lower, ip)
                    existing_a_set.add(new_key)
                    same_name_records.remove(record_to_update)
                    new_record = {"id": record_to_update["id"], "type": "A", "name": domain_lower, "content": ip, "proxied": proxied}
                    same_name_records.append(new_record)
                    existing_a_map[new_key] = new_record
                    updated_count += 1
                    tg_results.append(f"更新A\n{domain_lower}\n-> {ip}")
        else:
            if current_total_records >= MAX_TOTAL_RECORDS:
                print(f"DNS记录达到上限 跳过 {domain_lower}")
                tg_results.append(f"DNS记录达到上限\n{domain_lower}")
                continue
            success = create_record("A", domain_lower, ip, proxied=proxied)
            if success:
                current_total_records += 1
                updated_count += 1
                existing_a_set.add((domain_lower, ip))
                new_record = {"id": "new", "type": "A", "name": domain_lower, "content": ip, "proxied": proxied}
                existing_a_by_name.setdefault(domain_lower, []).append(new_record)
                existing_a_map[(domain_lower, ip)] = new_record
                tg_results.append(f"创建A\n{domain_lower}\n-> {ip}")
    # ==================== 直接 CNAME 处理 ====================
    print("\n========== 直接CNAME ==========\n")

    for name, target in DIRECT_CNAME_RECORDS:
        name_lower = name.lower()
        existing_record = existing_cname_map.get(name_lower)
        if existing_record:
            if existing_record["content"].lower() == target.lower():
                print(f"跳过 CNAME {name_lower} -> {target}")
                tg_results.append(f"跳过CNAME\n{name_lower}")
            else:
                success = update_record(existing_record["id"], "CNAME", existing_record["name"], target)
                if success:
                    updated_count += 1
                    tg_results.append(f"更新CNAME\n{name_lower}\n-> {target}")
        else:
            same_name_a = existing_a_by_name.get(name_lower, [])
            if same_name_a:
                for r in same_name_a:
                    if delete_record(r["id"]):
                        existing_a_map.pop((name_lower, r["content"]), None)
                        current_total_records -= 1
                        updated_count += 1
                        tg_results.append(f"删除A记录\n{name_lower}\n{r['content']}")
            if current_total_records >= MAX_TOTAL_RECORDS:
                print(f"DNS记录达到上限 跳过 {name_lower}")
                tg_results.append(f"DNS记录达到上限\n{name_lower}")
                continue
            success = create_record("CNAME", name_lower, target)
            if success:
                current_total_records += 1
                updated_count += 1
                existing_cname_map[name_lower] = {"id": "new", "type": "CNAME", "name": name_lower, "content": target}
                tg_results.append(f"创建CNAME\n{name_lower}\n-> {target}")
    # ==================== CNAME + Custom Hostname 处理 ====================
    print("\n========== CNAME + Custom Hostname ==========\n")

    desired_cname = []
    for cf_tag, target, ip_index in CNAME_RECORDS:
        ip = ips[ip_index % len(ips)]
        expected_name = cname_record_name(ip, cf_tag).lower()
        desired_cname.append((expected_name, target, cf_tag, ip))

    desired_cname_names = {name for name, _, _, _ in desired_cname}
    desired_cname_hostnames = set()
    for expected_name, target, cf_tag, ip in desired_cname:
        desired_cname_hostnames.add(expected_name)

    existing_cname_by_tag = {}
    for name_lower, r in existing_cname_map.items():
        for tag in {t for _, _, t, _ in desired_cname}:
            suffix = f".{tag}.{DOMAIN_ROOT}".lower()
            if name_lower.endswith(suffix):
                existing_cname_by_tag.setdefault(tag, []).append(r)
                break

    for expected_name, target, cf_tag, ip in desired_cname:
        existing_record = existing_cname_map.get(expected_name)
        if existing_record:
            if existing_record["content"].lower() == target.lower():
                print(f"跳过 CNAME {expected_name}")
                tg_results.append(f"跳过CNAME\n{expected_name}")
                if expected_name not in ch_map:
                    if create_custom_hostname(expected_name):
                        updated_count += 1
                        tg_results.append(f"创建CH\n{expected_name}")
            else:
                success = update_record(existing_record["id"], "CNAME", existing_record["name"], target)
                if success:
                    updated_count += 1
                    tg_results.append(f"更新CNAME\n{expected_name}\n-> {target}")
                if expected_name not in ch_map:
                    if create_custom_hostname(expected_name):
                        updated_count += 1
                        tg_results.append(f"创建CH\n{expected_name}")
        else:
            old_records = existing_cname_by_tag.get(cf_tag, [])
            old_to_remove = None
            for r in old_records:
                if r["name"].lower() not in desired_cname_names:
                    old_to_remove = r
                    break
            if old_to_remove:
                old_name = old_to_remove["name"].lower()
                print(f"IP变化，重建CNAME: {old_name} -> {expected_name}")
                old_ch = ch_map.get(old_name)
                if old_ch:
                    if delete_custom_hostname(old_ch["id"], old_name):
                        ch_map.pop(old_name, None)
                        updated_count += 1
                        tg_results.append(f"删除CH\n{old_name}")
                if delete_record(old_to_remove["id"]):
                    existing_cname_map.pop(old_name, None)
                success = create_record("CNAME", expected_name, target)
                if success:
                    updated_count += 1
                    existing_cname_map[expected_name] = {"id": "new", "type": "CNAME", "name": expected_name, "content": target}
                    old_records.remove(old_to_remove)
                    old_records.append({"id": "new", "type": "CNAME", "name": expected_name, "content": target})
                    tg_results.append(f"重建CNAME\n{expected_name}\n-> {target}")
                if create_custom_hostname(expected_name):
                    updated_count += 1
                    tg_results.append(f"创建CH\n{expected_name}")
            else:
                if current_total_records >= MAX_TOTAL_RECORDS:
                    print(f"DNS记录达到上限 跳过 {expected_name}")
                    tg_results.append(f"DNS记录达到上限\n{expected_name}")
                    continue
                success = create_record("CNAME", expected_name, target)
                if success:
                    current_total_records += 1
                    updated_count += 1
                    existing_cname_map[expected_name] = {"id": "new", "type": "CNAME", "name": expected_name, "content": target}
                    existing_cname_by_tag.setdefault(cf_tag, []).append({"id": "new", "type": "CNAME", "name": expected_name, "content": target})
                    tg_results.append(f"创建CNAME\n{expected_name}\n-> {target}")
                if create_custom_hostname(expected_name):
                    updated_count += 1
                    tg_results.append(f"创建CH\n{expected_name}")
    # ==================== 清理孤立 Custom Hostname ====================
    print("\n========== 清理孤立 Custom Hostname ==========\n")

    for ch_hostname, ch in list(ch_map.items()):
        if ch_hostname in PROTECTED_NAMES:
            continue
        is_cf_tag = any(
            ch_hostname.endswith(f".{tag}.{DOMAIN_ROOT}".lower())
            for tag in {t for _, _, t, _ in CNAME_RECORDS}
        )
        if is_cf_tag and ch_hostname not in desired_cname_hostnames:
            print(f"清理孤立CH: {ch_hostname}")
            if delete_custom_hostname(ch["id"], ch_hostname):
                updated_count += 1
                tg_results.append(f"清理孤立CH\n{ch_hostname}")

    # ==================== 结果汇总 ====================
    print("\n==============================")
    print(f"更新数量: {updated_count}")
    print(f"当前DNS记录数: {current_total_records}")
    print("==============================")

    try:
        if tg_results:
            message = (
                f"DNS自动更新完成\n\n"
                f"域名: {DOMAIN_ROOT}\n"
                f"更新数量: {updated_count}\n"
                f"当前DNS记录数: {current_total_records}\n\n"
                + "\n\n".join(tg_results[:20])
            )
        else:
            message = f"DNS检查完成\n\n{DOMAIN_ROOT}\n无需更新"
        if len(message) > 4000:
            chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for chunk in chunks:
                send_telegram(chunk)
        else:
            send_telegram(message)
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()

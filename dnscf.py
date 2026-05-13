```python
import os
import requests
import re
import traceback

CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID") or os.environ.get("TG_USER_ID")
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
DOMAIN_ROOT = "072503.xyz"
MAX_TOTAL_RECORDS = 10
MAX_A_RECORDS = 4

A_RECORDS = [
    ("dns.072503.xyz", 0),
    ("dns.072503.xyz", 1),
    ("dns1.072503.xyz", 0),
    ("dns2.072503.xyz", 1),
]

CNAME_RECORDS = [
    ("cf1", "www.visa.cn",    0),
    ("cf1", "www.visa.cn",    1),
    ("cf2", "store.ubi.com",  0),
    ("cf3", "www.shopify.com", 1),
    ("cf4", "mfa.gov.ua",     1),
    ("cf5", "saas.sin.fan",   0),
]

BASE_URL = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
HEADERS = {
    "Authorization": f"Bearer {CF_API_TOKEN}",
    "Content-Type": "application/json"
}


def send_telegram(message):
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


def is_valid_ipv4(ip):
    try:
        parts = ip.split(".")
        return (
            len(parts) == 4
            and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
        )
    except Exception:
        return False


def get_cf_speed_test_ip():
    url = "https://ip.164746.xyz/ipTop.html"
    all_ips = []
    try:
        print(f"获取优选IP: {url}")
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', r.text)
        for ip in ips:
            if is_valid_ipv4(ip) and ip not in all_ips:
                all_ips.append(ip)
    except Exception:
        print("获取优选IP失败")
        traceback.print_exc()
    print(f"获取到 {len(all_ips)} 个优选IP")
    return all_ips


def get_existing_records():
    all_records = []
    page = 1
    try:
        while True:
            resp = requests.get(
                BASE_URL,
                headers=HEADERS,
                params={"per_page": 100, "page": page},
                timeout=15
            )
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
        data = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": 60,
            "proxied": proxied
        }
        resp = requests.post(BASE_URL, headers=HEADERS, json=data, timeout=15)
        result = resp.json()
        if result.get("success"):
            print(f"创建 {record_type} {name} -> {content}")
            return True
        print(result)
        return False
    except Exception:
        traceback.print_exc()
        return False


def update_record(record_id, record_type, name, content, proxied=False):
    try:
        url = f"{BASE_URL}/{record_id}"
        data = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": 60,
            "proxied": proxied
        }
        resp = requests.put(url, headers=HEADERS, json=data, timeout=15)
        result = resp.json()
        if result.get("success"):
            print(f"更新 {record_type} {name} -> {content}")
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


def ip_to_dash(ip):
    return ip.replace(".", "-")


def cname_record_name(ip, cf_tag):
    return f"{ip_to_dash(ip)}.{cf_tag}.{DOMAIN_ROOT}"


def main():
    tg_results = []
    if not CF_API_TOKEN:
        print("缺少环境变量 CF_API_TOKEN")
        return
    if not CF_ZONE_ID:
        print("缺少环境变量 CF_ZONE_ID")
        return
    ips = get_cf_speed_test_ip()
    if not ips:
        msg = "未获取到优选IP"
        print(msg)
        send_telegram(msg)
        return
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
    updated_count = 0
    current_total_records = len(existing)
    current_a_records = len([r for r in existing if r["type"] == "A"])
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
        if (domain_lower, ip) in existing_a_set:
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
                success = update_record(record_to_update["id"], "A", domain_lower, ip)
                if success:
                    old_key = (domain_lower, record_to_update["content"])
                    existing_a_map.pop(old_key, None)
                    existing_a_set.discard(old_key)
                    new_key = (domain_lower, ip)
                    existing_a_set.add(new_key)
                    same_name_records.remove(record_to_update)
                    new_record = {"id": record_to_update["id"], "type": "A", "name": domain_lower, "content": ip}
                    same_name_records.append(new_record)
                    existing_a_map[new_key] = new_record
                    updated_count += 1
                    tg_results.append(f"更新A\n{domain_lower}\n-> {ip}")
            else:
                if current_a_records < MAX_A_RECORDS and current_total_records < MAX_TOTAL_RECORDS:
                    success = create_record("A", domain_lower, ip)
                    if success:
                        current_a_records += 1
                        current_total_records += 1
                        updated_count += 1
                        existing_a_set.add((domain_lower, ip))
                        tg_results.append(f"创建A\n{domain_lower}\n-> {ip}")
                else:
                    print(f"记录达到上限 跳过 {domain_lower}")
                    tg_results.append(f"记录达到上限\n{domain_lower}")
        else:
            if current_a_records >= MAX_A_RECORDS:
                print(f"A记录达到上限 跳过 {domain_lower}")
                tg_results.append(f"A记录达到上限\n{domain_lower}")
                continue
            if current_total_records >= MAX_TOTAL_RECORDS:
                print(f"DNS记录达到上限 跳过 {domain_lower}")
                tg_results.append(f"DNS记录达到上限\n{domain_lower}")
                continue
            success = create_record("A", domain_lower, ip)
            if success:
                current_a_records += 1
                current_total_records += 1
                updated_count += 1
                existing_a_set.add((domain_lower, ip))
                new_record = {"id": "new", "type": "A", "name": domain_lower, "content": ip}
                existing_a_by_name.setdefault(domain_lower, []).append(new_record)
                existing_a_map[(domain_lower, ip)] = new_record
                tg_results.append(f"创建A\n{domain_lower}\n-> {ip}")
    print("\n========== CNAME ==========\n")
    desired_cname = []
    for cf_tag, target, ip_index in CNAME_RECORDS:
        ip = ips[ip_index % len(ips)]
        expected_name = cname_record_name(ip, cf_tag).lower()
        desired_cname.append((expected_name, target, cf_tag, ip))
    desired_cname_names = {name for name, _, _, _ in desired_cname}
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
            else:
                success = update_record(existing_record["id"], "CNAME", existing_record["name"], target)
                if success:
                    updated_count += 1
                    tg_results.append(f"更新CNAME\n{expected_name}\n-> {target}")
        else:
            old_records = existing_cname_by_tag.get(cf_tag, [])
            old_to_remove = None
            for r in old_records:
                if r["name"].lower() not in desired_cname_names:
                    old_to_remove = r
                    break
            if old_to_remove:
                print(f"IP变化，重建CNAME: {old_to_remove['name']} -> {expected_name}")
                if delete_record(old_to_remove["id"]):
                    success = create_record("CNAME", expected_name, target)
                    if success:
                        existing_cname_map.pop(old_to_remove["name"].lower(), None)
                        existing_cname_map[expected_name] = {"id": "new", "type": "CNAME", "name": expected_name, "content": target}
                        old_records.remove(old_to_remove)
                        old_records.append({"id": "new", "type": "CNAME", "name": expected_name, "content": target})
                        updated_count += 1
                        tg_results.append(f"重建CNAME\n{expected_name}\n-> {target}")
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
```

与原始代码唯一的区别就是 `CNAME_RECORDS` 多了一行 `("cf5", "saas.sin.fan", 0)`，其他完全不变。

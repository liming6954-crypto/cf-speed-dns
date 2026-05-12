import os
import requests
import re
import traceback

# ==================== 配置 ====================
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
DOMAIN_ROOT = "072503.xyz"
SUBDOMAIN_PREFIX = "dns"
MAX_RECORDS = 10  # 限制更新/创建的数量

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")

HEADERS = {'Authorization': f'Bearer {CF_API_TOKEN}', 'Content-Type': 'application/json'}

def get_cf_speed_test_ip():
    """获取 IP 列表"""
    sources = [
        'https://164746.xyz',
        'https://090227.xyz',
        'https://090227.xyz',
        'https://090227.xyz',
    ]
    all_ips = []
    for url in sources:
        try:
            r = requests.get(url, timeout=15)
            ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', r.text)
            for ip in ips:
                if ip not in all_ips: all_ips.append(ip)
        except: pass
    return all_ips

def get_existing_records():
    """获取已存在的 DNS 记录"""
    try:
        url = f"https://cloudflare.com{CF_ZONE_ID}/dns_records?type=A&per_page=100"
        resp = requests.get(url, headers=HEADERS, timeout=20).json()
        records = {}
        for r in resp.get('result', []):
            name = r.get('name', '').lower()
            records[name] = {'id': r['id'], 'content': r.get('content')}
        return records
    except:
        return {}

def create_dns_record(name, ip):
    """【补全】创建解析"""
    url = f"https://cloudflare.com{CF_ZONE_ID}/dns_records"
    data = {"type": "A", "name": name, "content": ip, "ttl": 60, "proxied": False}
    resp = requests.post(url, headers=HEADERS, json=data, timeout=20)
    return resp.status_code == 200

def update_dns_record(record_id, name, ip):
    """【补全】更新解析"""
    url = f"https://cloudflare.com{CF_ZONE_ID}/dns_records/{record_id}"
    data = {"type": "A", "name": name, "content": ip, "ttl": 60, "proxied": False}
    resp = requests.put(url, headers=HEADERS, json=data, timeout=20)
    return resp.status_code == 200

def main():
    ips = get_cf_speed_test_ip()
    if not ips:
        print("获取 IP 失败")
        return

    existing = get_existing_records()
    results = []

    # 严格限制在 MAX_RECORDS 数量
    for i in range(MAX_RECORDS):
        # 匹配 dns1.072503.xyz, dns2...
        subdomain = f"{SUBDOMAIN_PREFIX}{i+1}.{DOMAIN_ROOT}".lower()
        ip = ips[i % len(ips)] # 如果IP不够，循环取用

        if subdomain in existing:
            # 记录存在 -> 检查是否需要更新
            record = existing[subdomain]
            if record['content'] != ip:
                if update_dns_record(record['id'], subdomain, ip):
                    results.append(f"✅ 更新 {subdomain} -> {ip}")
                else:
                    results.append(f"❌ 更新失败 {subdomain}")
            else:
                print(f"跳过 {subdomain} (IP未变)")
        else:
            # 记录不存在 -> 创建
            if create_dns_record(subdomain, ip):
                results.append(f"🆕 创建 {subdomain} -> {ip}")
            else:
                results.append(f"❌ 创建失败 {subdomain}")

    # 推送通知
    if results and TG_BOT_TOKEN and TG_USER_ID:
        text = f"🚀 <b>CF DNS 自动更新</b>\n\n" + "\n".join(results)
        requests.post(f"https://telegram.org{TG_BOT_TOKEN}/sendMessage", 
                      json={"chat_id": TG_USER_ID, "text": text, "parse_mode": "HTML"})

    print("\n".join(results) if results else "没有记录需要变更")

if __name__ == '__main__':
    main()

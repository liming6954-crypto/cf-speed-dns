import os, requests, re, traceback

# ==================== 配置 ====================
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
DOMAIN_ROOT = "072503.xyz"
SUBDOMAIN_PREFIX = "dns"
MAX_RECORDS = 10 

HEADERS = {'Authorization': f'Bearer {CF_API_TOKEN}', 'Content-Type': 'application/json'}

def get_cf_speed_test_ip():
    sources = ['https://164746.xyz', 'https://090227.xyz']
    all_ips = []
    for url in sources:
        try:
            r = requests.get(url, timeout=10)
            ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', r.text)
            for ip in ips:
                if ip not in all_ips: all_ips.append(ip)
        except: pass
    return all_ips

def get_existing_records():
    """获取现有记录并返回字典"""
    url = f"https://cloudflare.com{CF_ZONE_ID}/dns_records?type=A&per_page=100"
    try:
        resp = requests.get(url, headers=HEADERS).json()
        return {r['name'].lower(): {'id': r['id'], 'content': r['content']} for r in resp.get('result', [])}
    except: return {}

def create_dns_record(name, ip):
    """【修复 NameError】创建函数"""
    url = f"https://cloudflare.com{CF_ZONE_ID}/dns_records"
    data = {"type": "A", "name": name, "content": ip, "ttl": 60, "proxied": False}
    return requests.post(url, headers=HEADERS, json=data).status_code == 200

def update_dns_record(record_id, name, ip):
    """更新函数"""
    url = f"https://cloudflare.com{CF_ZONE_ID}/dns_records/{record_id}"
    data = {"type": "A", "name": name, "content": ip, "ttl": 60, "proxied": False}
    return requests.put(url, headers=HEADERS, json=data).status_code == 200

def main():
    ips = get_cf_speed_test_ip()
    if not ips: return
    
    existing = get_existing_records()
    results = []

    # 严格限制 10 条
    for i in range(MAX_RECORDS):
        subdomain = f"{SUBDOMAIN_PREFIX}{i+1}.{DOMAIN_ROOT}".lower()
        ip = ips[i % len(ips)]

        if subdomain in existing:
            # 存在则更新
            record = existing[subdomain]
            if record['content'] != ip:
                if update_dns_record(record['id'], subdomain, ip):
                    results.append(f"✅ 更新 {subdomain}")
            else:
                print(f"跳过 {subdomain}")
        else:
            # 不存在则创建
            if create_dns_record(subdomain, ip):
                results.append(f"🆕 创建 {subdomain}")

    # TG 推送逻辑 (保持你原有的即可)
    print("\n".join(results) if results else "无需变更")

if __name__ == '__main__':
    main()

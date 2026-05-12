#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
import traceback

# ==================== 配置 ====================
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
DOMAIN_ROOT = "0725.xyz"

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

def get_cf_speed_test_ip():
    sources = ['https://ip.164746.xyz/ipTop.html',]
    for url in sources:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                text = r.text.strip()
                if text:
                    print(f"获取到 IP: {text}")
                    return text
        except Exception as e:
            print(f"{url} 失败: {e}")
    return None


def get_dns_record_by_name(target):
    """智能匹配记录（解决最常见的问题）"""
    short_name = target.split('.')[0]          # dns1
    full_name = target.rstrip('.')             # dns1.0725.xyz
    candidates = [short_name, full_name, full_name + '.']

    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records?type=A"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        
        if resp.status_code != 200:
            print(f"API 查询失败: {resp.status_code}")
            return None

        for r in resp.json().get('result', []):
            api_name = r.get('name', '').rstrip('.')
            if api_name in candidates or api_name.lower() == short_name.lower():
                print(f"✅ 匹配成功！API名称: '{api_name}' | 更新目标: '{target}'")
                return {'id': r['id'], 'content': r.get('content')}
        
        print(f"❌ 未匹配到记录: {target} (尝试过 {candidates})")
        return None
    except Exception as e:
        print(f"查询异常: {e}")
        traceback.print_exc()
        return None


def update_dns_record(name, new_ip):
    record = get_dns_record_by_name(name)
    if not record:
        return f"ip:{new_ip} 解析 {name} 失败 (记录不存在)"

    if record['content'] == new_ip:
        return f"ip:{new_ip} 解析 {name} 跳过 (已是最新)"

    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record['id']}"
        data = {
            "type": "A",
            "name": name,           # 这里用你传入的名称
            "content": new_ip,
            "ttl": 60,
            "proxied": False
        }
        resp = requests.put(url, headers=HEADERS, json=data, timeout=20)
        
        if resp.status_code == 200:
            return f"ip:{new_ip} 解析 {name} 成功"
        else:
            return f"ip:{new_ip} 解析 {name} 失败"
    except Exception:
        traceback.print_exc()
        return f"ip:{new_ip} 解析 {name} 失败"


def main():
    ip_str = get_cf_speed_test_ip()
    if not ip_str:
        print("❌ 获取 IP 失败")
        return

    ip_list = [ip.strip() for ip in ip_str.split(',') if ip.strip()]
    print(f"共 {len(ip_list)} 个 IP\n")

    results = []
    for i, ip in enumerate(ip_list):
        name = f"dns{i+1}.{DOMAIN_ROOT}"
        result = update_dns_record(name, ip)
        results.append(result)
        print(result)

    print("\n=== 更新完成 ===")


if __name__ == '__main__':
    main()

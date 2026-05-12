#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
import traceback

# ==================== 配置 ====================
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")

DOMAIN_ROOT = "072503.xyz"        # ← 已修改为你的域名
SUBDOMAIN_PREFIX = "dns"          # dns1、dns2、dns3...

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}


def get_cf_speed_test_ip():
    sources = ['https://ip.164746.xyz/ipTop.html', 'https://ip.164746.xyz']
    for url in sources:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                text = r.text.strip()
                if text:
                    print(f"✅ 获取到 IP: {text}")
                    return text
        except Exception as e:
            print(f"{url} 获取失败: {e}")
    return None


def get_all_matching_records():
    """获取所有 dns 开头的记录"""
    print("🔍 正在搜索 dns 开头的记录...\n")
    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records?type=A"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        
        if resp.status_code != 200:
            print(f"API 查询失败: {resp.status_code}")
            return []

        records = []
        for r in resp.json().get('result', []):
            name = r.get('name', '').rstrip('.')
            if name.startswith(SUBDOMAIN_PREFIX):   # 匹配 dns1、dns2、dns3...
                ip = r.get('content', '')
                print(f"找到记录: {name}  →  当前IP: {ip}")
                records.append({
                    'id': r['id'],
                    'name': name,
                    'content': ip
                })
        
        return sorted(records, key=lambda x: x['name'])
    except Exception as e:
        print("获取记录异常:", e)
        traceback.print_exc()
        return []


def update_dns_record(record, new_ip):
    """执行更新"""
    old_ip = record.get('content', '')

    if old_ip == new_ip:
        return f"ip:{new_ip} 解析 {record['name']} 跳过 (已是最新)"

    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record['id']}"
        data = {
            "type": "A",
            "name": record['name'],
            "content": new_ip,
            "ttl": 60,
            "proxied": False
        }

        resp = requests.put(url, headers=HEADERS, json=data, timeout=20)

        if resp.status_code == 200:
            return f"ip:{new_ip} 解析 {record['name']} 成功"
        else:
            return f"ip:{new_ip} 解析 {record['name']} 失败"
    except Exception:
        traceback.print_exc()
        return f"ip:{new_ip} 解析 {record['name']} 失败"


def main():
    ip_str = get_cf_speed_test_ip()
    if not ip_str:
        print("❌ 获取 IP 失败")
        return

    ip_list = [ip.strip() for ip in ip_str.split(',') if ip.strip()]
    print(f"共获取到 {len(ip_list)} 个 IP\n")

    records = get_all_matching_records()
    print(f"\n共找到 {len(records)} 条可更新记录\n")

    if not records:
        print(f"❌ 未找到任何以 {SUBDOMAIN_PREFIX} 开头的记录")
        print("请确认你在 Cloudflare 中创建了 dns1.072503.xyz、dns2.072503.xyz 等记录")
        return

    results = []
    for i in range(min(len(ip_list), len(records))):
        res = update_dns_record(records[i], ip_list[i])
        results.append(res)
        print(res)

    print("\n=== 更新完成 ===")


if __name__ == '__main__':
    main()

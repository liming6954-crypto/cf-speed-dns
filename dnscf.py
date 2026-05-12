#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
import traceback

# ==================== 配置 ====================
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")

DOMAIN_ROOT = "0725.xyz"          # 你的根域名
SUBDOMAIN_PREFIX = "dns"          # dns1、dns2、dns3...

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}


def get_cf_speed_test_ip():
    """获取优选 IP"""
    sources = ['https://ip.164746.xyz/ipTop.html',]
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
    """获取所有 dns 开头的 A 记录"""
    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records?type=A"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        
        if resp.status_code != 200:
            print(f"API 查询失败: {resp.status_code}")
            return []

        records = []
        for r in resp.json().get('result', []):
            name = r.get('name', '').rstrip('.')
            if name.startswith(SUBDOMAIN_PREFIX) and DOMAIN_ROOT in name:
                records.append({
                    'id': r['id'],
                    'name': name,
                    'content': r.get('content')
                })
                print(f"找到记录: {name} → {r.get('content')}")
        
        return sorted(records, key=lambda x: x['name'])  # 按名称排序 dns1, dns2...
    except Exception as e:
        print("获取记录异常:", e)
        traceback.print_exc()
        return []


def update_dns_record(record, new_ip):
    """更新单条记录"""
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
    print(f"共获取 {len(ip_list)} 个优选 IP\n")

    # 获取 Cloudflare 中所有 dnsX.0725.xyz 记录
    records = get_all_matching_records()
    print(f"\n共找到 {len(records)} 条可更新记录\n")

    if not records:
        print("❌ 未找到任何 dns 开头的记录，请先在 Cloudflare 手动创建")
        return

    results = []
    update_count = min(len(ip_list), len(records))

    for i in range(update_count):
        result = update_dns_record(records[i], ip_list[i])
        results.append(result)
        print(result)

    # 如果 IP 比记录多，提示
    if len(ip_list) > len(records):
        print(f"\n提示：获取到 {len(ip_list)} 个IP，但只更新了 {len(records)} 条记录（可继续创建更多 dnsX 记录）")

    print("\n=== 更新完成 ===")


if __name__ == '__main__':
    main()

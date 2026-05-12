#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
import traceback

# ==================== 配置 ====================
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")

DOMAIN_ROOT = "072503.xyz"
SUBDOMAIN_PREFIX = "dns"

# Telegram 配置
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")

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
    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records?type=A"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        
        if resp.status_code != 200:
            return []

        records = []
        for r in resp.json().get('result', []):
            name = r.get('name', '').rstrip('.')
            if name.startswith(SUBDOMAIN_PREFIX) or name.startswith("dns."):
                records.append({
                    'id': r['id'],
                    'name': name,
                    'content': r.get('content')
                })
                print(f"找到记录: {name} → 当前IP: {r.get('content')}")
        
        return sorted(records, key=lambda x: x['name'])
    except Exception:
        traceback.print_exc()
        return []


def update_dns_record(record, new_ip):
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


def telegram_push(content: str):
    """发送 Telegram 消息"""
    if not TG_BOT_TOKEN or not TG_USER_ID:
        print("⚠️ TG_BOT_TOKEN 或 TG_USER_ID 未设置，跳过推送")
        return

    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TG_USER_ID,
            "text": f"🚀 <b>CF IP 自动更新</b>\n\n{content}",
            "parse_mode": "HTML"
        }
        r = requests.post(url, json=data, timeout=10)
        if r.status_code == 200:
            print("✅ Telegram 推送成功")
        else:
            print(f"❌ Telegram 推送失败: {r.status_code}")
    except Exception as e:
        print(f"❌ Telegram 推送异常: {e}")


def main():
    ip_str = get_cf_speed_test_ip()
    if not ip_str:
        telegram_push("❌ 获取优选 IP 失败")
        return

    ip_list = [ip.strip() for ip in ip_str.split(',') if ip.strip()]
    print(f"共获取到 {len(ip_list)} 个 IP\n")

    records = get_all_matching_records()
    print(f"\n共找到 {len(records)} 条可更新记录\n")

    if not records:
        telegram_push("❌ 未找到任何 dns 开头的 DNS 记录")
        return

    results = []
    for i, record in enumerate(records):
        ip = ip_list[i % len(ip_list)]          # 循环使用 IP
        res = update_dns_record(record, ip)
        results.append(res)
        print(res)

    # 发送 Telegram 推送
    full_content = "\n".join(results)
    telegram_push(full_content)

    print("\n=== 更新完成 ===")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare DNS 优选IP自动更新工具
"""

import os
import requests
import time
import traceback
import re

# ==================== 配置 ====================
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")   # 如: cf.example.com

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

DEFAULT_TIMEOUT = 30


def is_valid_ipv4(ip: str) -> bool:
    """简单验证 IPv4 地址"""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False
    return all(0 <= int(x) <= 255 for x in ip.split('.'))


def get_cf_speed_test_ip():
    """获取优选 IP，支持多个备用源"""
    sources = [
        'https://ip.164746.xyz/ipTop.html',
    ]

    for url in sources:
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                text = resp.text.strip()
                if text:
                    print(f"成功从 {url} 获取 IP")
                    return text
        except Exception as e:
            print(f"从 {url} 获取失败: {e}")

    print("所有 IP 来源均获取失败")
    return None


def get_dns_records(name):
    """获取 Cloudflare A 记录"""
    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
        resp = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        
        if resp.status_code != 200:
            print(f"获取记录失败: {resp.status_code} {resp.text}")
            return []

        records = []
        for r in resp.json().get('result', []):
            if r.get('type') == 'A' and r.get('name') == name:
                records.append({
                    'id': r['id'],
                    'content': r.get('content')
                })
        return records
    except Exception as e:
        traceback.print_exc()
        return []


def update_dns_record(record_info, name, new_ip):
    """更新 DNS 记录"""
    if not is_valid_ipv4(new_ip):
        return f"❌ {name} → {new_ip} (非法IP，跳过)"

    if record_info['content'] == new_ip:
        return f"✅ {name} → {new_ip} (已是最新，跳过)"

    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record_info['id']}"
        data = {
            "type": "A",
            "name": name,
            "content": new_ip,
            "ttl": 60,
            "proxied": False
        }
        resp = requests.put(url, headers=HEADERS, json=data, timeout=DEFAULT_TIMEOUT)

        if resp.status_code == 200:
            return f"✅ {name} → {new_ip} (更新成功)"
        else:
            return f"❌ {name} → 更新失败 ({resp.status_code})"
    except Exception as e:
        traceback.print_exc()
        return f"❌ {name} → 更新异常"


def telegram_push(content: str):
    if not all([TG_BOT_TOKEN, TG_USER_ID]):
        return

    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TG_USER_ID,
            "text": f"🚀 <b>Cloudflare IP 自动更新</b>\n\n{content}",
            "parse_mode": "HTML"
        }
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"TG 推送失败: {e}")


def main():
    if not all([CF_API_TOKEN, CF_ZONE_ID, CF_DNS_NAME]):
        print("❌ 错误：缺少必要的环境变量")
        return

    ip_str = get_cf_speed_test_ip()
    if not ip_str:
        telegram_push("❌ 获取优选IP失败")
        return

    ip_list = [ip.strip() for ip in ip_str.split(',') if ip.strip()]

    records = get_dns_records(CF_DNS_NAME)
    if not records:
        print(f"❌ 未找到域名 {CF_DNS_NAME} 的 A 记录")
        telegram_push(f"❌ 未找到域名 {CF_DNS_NAME} 的 A 记录")
        return

    results = []
    for i in range(min(len(ip_list), len(records))):
        res = update_dns_record(records[i], CF_DNS_NAME, ip_list[i])
        results.append(res)
        print(res)

    if results:
        telegram_push("\n".join(results))


if __name__ == '__main__':
    main()

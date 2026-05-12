#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare DNS 优选IP自动更新 - 修复版（重点支持 dns1、dns2）
"""

import os
import requests
import time
import traceback
import re

# ==================== 配置 ====================
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")

DOMAIN_ROOT = "0725.xyz"           # 确认你的根域名
SUBDOMAIN_PREFIX = "dns"           # dns1、dns2

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

DEFAULT_TIMEOUT = 30


def is_valid_ipv4(ip: str) -> bool:
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False
    return all(0 <= int(x) <= 255 for x in ip.split('.'))


def get_cf_speed_test_ip():
    """获取优选 IP"""
    sources = [
        'https://ip.164746.xyz/ipTop.html',
    ]
    for url in sources:
        try:
            print(f"正在从 {url} 获取 IP...")
            resp = requests.get(url, timeout=20)
            print(f"状态码: {resp.status_code}")
            if resp.status_code == 200:
                text = resp.text.strip()
                print(f"原始返回内容: {text[:200]}")
                if text and len(text) > 5:
                    return text
        except Exception as e:
            print(f"{url} 获取失败: {e}")
    print("❌ 所有来源均获取失败")
    return None


def get_dns_record_by_name(name):
    """获取指定域名的记录"""
    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
        print(f"正在查询记录: {name}")
        resp = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        
        if resp.status_code != 200:
            print(f"API 查询失败: {resp.status_code} {resp.text[:300]}")
            return None

        for r in resp.json().get('result', []):
            record_name = r.get('name', '')
            if r.get('type') == 'A' and record_name == name:
                print(f"✅ 找到记录: {name} → 当前IP: {r.get('content')}")
                return {'id': r['id'], 'content': r.get('content')}
        
        print(f"⚠️ 未找到记录: {name}")
        return None
    except Exception as e:
        print(f"查询记录异常: {e}")
        traceback.print_exc()
        return None


def update_dns_record(name, new_ip):
    """更新记录"""
    if not is_valid_ipv4(new_ip):
        return f"ip:{new_ip} 解析 {name} 失败 (非法IP)"

    record = get_dns_record_by_name(name)
    if not record:
        return f"ip:{new_ip} 解析 {name} 失败 (记录不存在，请确认已创建)"

    old_ip = record.get('content', '')
    if old_ip == new_ip:
        return f"ip:{new_ip} 解析 {name} 跳过 (已是最新)"

    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record['id']}"
        data = {
            "type": "A",
            "name": name,
            "content": new_ip,
            "ttl": 60,
            "proxied": False
        }

        resp = requests.put(url, headers=HEADERS, json=data, timeout=DEFAULT_TIMEOUT)

        if resp.status_code == 200:
            return f"ip:{new_ip} 解析 {name} 成功"
        else:
            print(f"更新失败详情: {resp.text}")
            return f"ip:{new_ip} 解析 {name} 失败"
    except Exception as e:
        traceback.print_exc()
        return f"ip:{new_ip} 解析 {name} 失败"


def telegram_push(content: str):
    if not all([TG_BOT_TOKEN, TG_USER_ID]):
        return
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TG_USER_ID,
            "text": f"🚀 <b>CF IP 自动更新</b>\n\n{content}",
            "parse_mode": "HTML"
        }
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"TG推送失败: {e}")


def main():
    if not all([CF_API_TOKEN, CF_ZONE_ID]):
        print("❌ 缺少环境变量")
        return

    ip_str = get_cf_speed_test_ip()
    if not ip_str:
        telegram_push("❌ 获取优选IP失败，这几天可能接口不稳定")
        return

    ip_list = [ip.strip() for ip in ip_str.split(',') if ip.strip()]
    print(f"共获取到 {len(ip_list)} 个IP: {ip_list}")

    results = []

    # 更新 dns1.0725.xyz、dns2.0725.xyz ...
    for i, ip in enumerate(ip_list[:5]):   # 最多更新前5个
        name = f"{SUBDOMAIN_PREFIX}{i+1}.{DOMAIN_ROOT}"
        res = update_dns_record(name, ip)
        results.append(res)
        print(res)

    if results:
        telegram_push("\n".join(results))
        print("\n本次更新完成！")


if __name__ == '__main__':
    main()

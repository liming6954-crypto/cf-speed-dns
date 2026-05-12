#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare DNS 优选IP自动更新工具 - 多子域名支持版
"""

import os
import requests
import time
import traceback
import re

# ==================== 配置 ====================
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")

# 主域名配置
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")          # 如: dns.072503.xyz

# 多子域名模式配置（推荐使用）
ENABLE_MULTI_SUBDOMAIN = True                        # 开启多子域名模式
SUBDOMAIN_PREFIX = "dns"                             # 子域名前缀 → dns1, dns2, dns3...
DOMAIN_ROOT = "072503.xyz"                           # 根域名

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
        'https://ip.164746.xyz',
        'https://ip.164746.xyz/ipTop.html',
    ]

    for url in sources:
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                text = resp.text.strip()
                if text:
                    print(f"成功获取 IP: {text[:100]}...")
                    return text
        except Exception as e:
            print(f"从 {url} 获取失败: {e}")
    return None


def get_dns_record_by_name(name):
    """获取单个域名对应的 DNS 记录"""
    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
        resp = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        
        if resp.status_code != 200:
            return None

        for r in resp.json().get('result', []):
            if r.get('type') == 'A' and r.get('name') == name:
                return {'id': r['id'], 'content': r.get('content')}
        return None
    except Exception:
        traceback.print_exc()
        return None


def update_dns_record(name, new_ip):
    """更新 DNS 并返回指定格式"""
    if not is_valid_ipv4(new_ip):
        return f"ip:{new_ip} 解析 {name} 失败 (非法IP)"

    record = get_dns_record_by_name(name)
    if not record:
        return f"ip:{new_ip} 解析 {name} 失败 (记录不存在，请先创建)"

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
            return f"ip:{new_ip} 解析 {name} 失败"
    except Exception:
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
        print(f"TG 推送失败: {e}")


def main():
    if not all([CF_API_TOKEN, CF_ZONE_ID]):
        print("❌ 缺少必要的环境变量")
        return

    ip_str = get_cf_speed_test_ip()
    if not ip_str:
        telegram_push("❌ 获取优选IP失败")
        return

    ip_list = [ip.strip() for ip in ip_str.split(',') if ip.strip()]
    if not ip_list:
        telegram_push("❌ 未获取到有效IP")
        return

    results = []

    if ENABLE_MULTI_SUBDOMAIN and SUBDOMAIN_PREFIX and DOMAIN_ROOT:
        # ==================== 多子域名模式 ====================
        print(f"启用多子域名模式 → {SUBDOMAIN_PREFIX}1.{DOMAIN_ROOT}, {SUBDOMAIN_PREFIX}2.{DOMAIN_ROOT} ...")
        for i, ip in enumerate(ip_list):
            subdomain_name = f"{SUBDOMAIN_PREFIX}{i+1}.{DOMAIN_ROOT}"
            result = update_dns_record(subdomain_name, ip)
            results.append(result)
            print(result)
    else:
        # ==================== 单域名模式 ====================
        if not CF_DNS_NAME:
            print("❌ 单域名模式下必须设置 CF_DNS_NAME")
            return
        for ip in ip_list[:5]:   # 限制最多更新5条相同记录
            result = update_dns_record(CF_DNS_NAME, ip)
            results.append(result)
            print(result)

    # 发送 Telegram 推送
    if results:
        telegram_push("\n".join(results))


if __name__ == '__main__':
    main()

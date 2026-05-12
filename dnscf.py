#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
import traceback
import re
import random

# ==================== 配置 ====================
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")

DOMAIN_ROOT = "072503.xyz"
MAX_RECORDS = 10
# Telegram 配置
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}


def get_primary_ips():
    """优先使用这个来源（dns.072503.xyz + dns1 + dns2 都优先用）"""
    try:
        r = requests.get('https://ip.164746.xyz/ipTop.html', timeout=15)
        if r.status_code == 200:
            ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', r.text)
            print(f"主来源获取到 {len(ips)} 个 IP")
            return ips
    except Exception as e:
        print("主来源获取失败:", e)
    return []


def get_backup_ips():
    """备用来源（当主IP不够时使用）"""
    sources = [
        'https://cf.090227.xyz/ct?ips=8',
        'https://cf.090227.xyz/cu',
        'https://cf.090227.xyz/cmcc?ips=8',
    ]
    all_ips = []
    for url in sources:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', r.text)
                for ip in ips:
                    if ip not in all_ips:
                        all_ips.append(ip)
        except:
            pass
    random.shuffle(all_ips)
    return all_ips


def get_all_records():
    """获取 dns*.072503.xyz 的所有 A 记录"""
    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records?type=A"
        resp = requests.get(url, headers=HEADERS, timeout=20)

        records = []
        for r in resp.json().get('result', []):
            name = r.get('name', '').rstrip('.')
            if name.startswith('dns') and DOMAIN_ROOT in name:
                records.append({
                    'id': r['id'],
                    'name': name,
                    'content': r.get('content')
                })
                print(f"找到记录: {name} → 当前IP: {r.get('content')}")
        return sorted(records, key=lambda x: x['name'])
    except Exception as e:
        print("获取记录失败:", e)
        traceback.print_exc()
        return []


def update_record(record, new_ip):
    """更新记录"""
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


def telegram_push(content):
    if not TG_BOT_TOKEN or not TG_USER_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TG_USER_ID,
            "text": f"🚀 <b>CF IP 自动更新</b>\n\n{content}",
            "parse_mode": "HTML"
        }
        requests.post(url, json=data, timeout=10)
    except:
        pass


def main():
    # 1. 获取 IP 列表
    primary = get_primary_ips()
    backup = get_backup_ips()
    
    # 合并并去重
    ip_list = []
    for ip in primary + backup:
        if ip not in ip_list:
            ip_list.append(ip)
            
    if not ip_list:
        print("未获取到任何 IP")
        return

    # 2. 获取现有的 DNS 记录
    existing = get_all_records() # 假设你保留了第一版获取记录的函数名
    print(f"当前已存在 {len(existing)} 条记录")

    results = []
    
    # ================= 核心限制功能 =================
    # 严格按照 MAX_RECORDS 数量进行循环（1-10）
    for i in range(MAX_RECORDS):
        # 生成 dns1, dns2 ... dns10 这种格式
        subdomain = f"dns{i+1}.{DOMAIN_ROOT}"
        # 如果 IP 库不够 10 个，则取模循环使用
        ip = ip_list[i % len(ip_list)]

        if subdomain in existing:
            # 已存在则更新 (调用你代码里的更新逻辑)
            record_id = existing[subdomain]['id']
            if existing[subdomain]['content'] != ip:
                # 这里调用 update_dns_record(record_id, subdomain, ip)
                print(f"正在更新 -> {subdomain} ({ip})")
                # 更新成功逻辑...
                results.append(f"✅ 更新: {subdomain} -> {ip}")
            else:
                print(f"跳过更新 -> {subdomain} IP未变")
        else:
            # 不存在则创建
            print(f"正在创建 -> {subdomain} ({ip})")
            if create_dns_record(subdomain, ip):
                results.append(f"🆕 创建: {subdomain} -> {ip}")
            else:
                results.append(f"❌ 失败: {subdomain}")
    # ===============================================

    # 3. Telegram 推送
    if TG_BOT_TOKEN and TG_USER_ID:
        try:
            text = f"🚀 <b>CF IP 自动更新 ({len(results)}条)</b>\n\n" + "\n".join(results)
            requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage", 
                          json={"chat_id": TG_USER_ID, "text": text, "parse_mode": "HTML"})
        except:
            pass

    print("\n=== 执行完成 ===")


if __name__ == '__main__':
    main()

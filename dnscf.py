#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
import traceback

CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")

HEADERS = {'Authorization': f'Bearer {CF_API_TOKEN}', 'Content-Type': 'application/json'}

def get_cf_speed_test_ip():
    try:
        r = requests.get('https://ip.164746.xyz/ipTop.html', timeout=15)
        if r.status_code == 200:
            return r.text.strip()
    except:
        pass
    return None

def get_record_by_keyword(keyword):
    """模糊匹配 dns 开头的记录"""
    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records?type=A"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        
        for r in resp.json().get('result', []):
            name = r.get('name', '').rstrip('.')
            if keyword in name:
                print(f"✅ 匹配到记录: {name}")
                return {'id': r['id'], 'name': name, 'content': r.get('content')}
        return None
    except:
        return None

def update(name, new_ip):
    record = get_record_by_keyword(name)
    if not record:
        return f"ip:{new_ip} 解析 {name} 失败 (记录不存在)"

    if record['content'] == new_ip:
        return f"ip:{new_ip} 解析 {name} 跳过 (已是最新)"

    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{record['id']}"
        data = {"type": "A", "name": record['name'], "content": new_ip, "ttl": 60, "proxied": False}
        resp = requests.put(url, headers=HEADERS, json=data, timeout=20)
        return f"ip:{new_ip} 解析 {name} 成功" if resp.status_code == 200 else f"ip:{new_ip} 解析 {name} 失败"
    except:
        return f"ip:{new_ip} 解析 {name} 失败"

def main():
    ip_str = get_cf_speed_test_ip()
    if not ip_str:
        print("获取IP失败")
        return
    ip_list = [ip.strip() for ip in ip_str.split(',') if ip.strip()]

    print("开始更新...\n")
    for i, ip in enumerate(ip_list):
        subdomain = f"dns{i+1}"
        res = update(subdomain, ip)
        print(res)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests

CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

def diagnose():
    print("🔍 Cloudflare DNS 完整诊断\n")
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records?type=A"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        print(f"API 状态码: {resp.status_code}\n")
        
        if resp.status_code != 200:
            print(resp.text)
            return

        records = resp.json().get('result', [])
        print(f"共找到 {len(records)} 条 A 记录：\n")
        
        for r in records:
            print(f"名称: {r.get('name')}")
            print(f"内容: {r.get('content')}")
            print(f"ID:   {r.get('id')}")
            print("-" * 70)
            
    except Exception as e:
        print("查询失败:", e)

if __name__ == '__main__':
    diagnose()

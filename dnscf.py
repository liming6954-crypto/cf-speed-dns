#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
import traceback

CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

def diagnose_dns_records():
    print("🔍 开始诊断 Cloudflare DNS 记录...\n")
    
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records?type=A"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        print(f"API 状态码: {resp.status_code}")
        
        if resp.status_code != 200:
            print("❌ API 调用失败:")
            print(resp.text)
            return

        records = resp.json().get('result', [])
        print(f"✅ 共找到 {len(records)} 条 A 记录\n")
        
        for r in records:
            print(f"名称: {r.get('name')}")
            print(f"内容: {r.get('content')}")
            print(f"类型: {r.get('type')}  |  Proxied: {r.get('proxied')}")
            print("-" * 60)
            
    except Exception as e:
        print("❌ 查询异常:")
        traceback.print_exc()

if __name__ == '__main__':
    if not all([CF_API_TOKEN, CF_ZONE_ID]):
        print("❌ 环境变量未设置")
    else:
        diagnose_dns_records()

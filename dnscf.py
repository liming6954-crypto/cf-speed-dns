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

def full_diagnose():
    print("🔍 Cloudflare DNS 完整记录诊断\n")
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records?type=A"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        print(f"API 返回状态码: {resp.status_code}\n")
        
        if resp.status_code != 200:
            print("错误信息:")
            print(resp.text)
            return

        records = resp.json().get('result', [])
        print(f"总共找到 {len(records)} 条 A 记录：\n")
        
        dns_records = []
        for r in records:
            name = r.get('name', '')
            content = r.get('content', '')
            print(f"名称: {name}")
            print(f"内容: {content}")
            print(f"记录ID: {r.get('id')}")
            print("-" * 60)
            
            if 'dns' in name.lower():
                dns_records.append((name, content))
        
        print("\n=== 包含 dns 的记录 ===")
        for name, content in dns_records:
            print(f"{name}  →  {content}")
            
    except Exception as e:
        print("查询异常:", e)

if __name__ == '__main__':
    full_diagnose()

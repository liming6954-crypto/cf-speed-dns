#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import traceback
import time
import os
import requests

# API 配置
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_USER_ID = os.environ.get("TG_USER_ID")

HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}
DEFAULT_TIMEOUT = 30

def get_cf_speed_test_ip(timeout=10, max_retries=5):
    for attempt in range(max_retries):
        try:
            response = requests.get('https://164746.xyz', timeout=timeout)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"获取 IP 失败: {e}")
    return None

def get_dns_records(name):
    records = []
    url = f'https://cloudflare.com{CF_ZONE_ID}/dns_records'
    try:
        response = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            result = response.json().get('result', [])
            for record in result:
                if record.get('name') == name and record.get('type') == 'A':
                    records.append({'id': record['id'], 'content': record.get('content', '')})
    except Exception as e:
        print(f'获取 DNS 记录异常: {e}')
    return records

def update_dns_record(record_info, name, cf_ip):
    record_id = record_info['id']
    current_ip = record_info.get('content', '')
    if current_ip == cf_ip:
        return f"☁️ {name}: {cf_ip} (已最新)"
    url = f'https://cloudflare.com{CF_ZONE_ID}/dns_records/{record_id}'
    data = {'type': 'A', 'name': name, 'content': cf_ip}
    try:
        response = requests.put(url, headers=HEADERS, json=data, timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            return f"✅ {name}: {cf_ip} (更新成功)"
        return f"❌ {name}: 更新失败"
    except Exception:
        return f"❌ {name}: 异常"

def telegram_push(content):
    if not TG_BOT_TOKEN or not TG_USER_ID:
        print("未配置 TG 推送")
        return
    url = f"https://telegram.org{TG_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TG_USER_ID,
        "text": f"🚀 <b>CF IP 自动更新</b>\n\n{content}",
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=data, timeout=DEFAULT_TIMEOUT)
        print(f"TG 推送状态: {r.status_code}")
    except Exception as e:
        print(f"TG 推送异常: {e}")

def main():
    # 检查必要的环境变量
    if not all([CF_API_TOKEN, CF_ZONE_ID, CF_DNS_NAME]):
        print("错误: 缺少必要变量")
        return

    # 获取最新优选 IP
    ip_str = get_cf_speed_test_ip()
    if not ip_str:
        return

    ip_list = [ip.strip() for ip in ip_str.split(',') if ip.strip()]
    
    # 获取 DNS 记录
    dns_records = get_dns_records(CF_DNS_NAME)
    if not dns_records:
        print(f"未找到 {CF_DNS_NAME} 的记录")
        return

    # 这里的缩进必须和上面对齐，全部包含在 main() 函数里
    results = []
    ip_list = ip_list[:len(dns_records)]
    for i, ip in enumerate(ip_list):
        res = update_dns_record(dns_records[i], CF_DNS_NAME, ip)
        results.append(res)

    if results:
        telegram_push('\n'.join(results))

if __name__ == '__main__':
    main()

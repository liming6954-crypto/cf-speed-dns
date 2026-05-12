import os
import requests
import re
import traceback

# =========================================================
# 配置
# =========================================================

CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

DOMAIN_ROOT = "072503.xyz"

# 最大更新数量（A + CNAME）
MAX_TOTAL_UPDATES = 10

# A记录
A_RECORDS = [
    "dns.072503.xyz",
    "dns1.072503.xyz",
    "dns2.072503.xyz"
]

# CNAME记录
CNAME_TARGETS = {
    "cf1.072503.xyz": "www.visa.cn",
    "cf2.072503.xyz": "store.ubi.com",
    "cf3.072503.xyz": "www.shopify.com",
    "cf4.072503.xyz": "mfa.gov.ua"
}

# Cloudflare API
BASE_URL = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"

HEADERS = {
    "Authorization": f"Bearer {CF_API_TOKEN}",
    "Content-Type": "application/json"
}

# =========================================================
# Telegram通知
# =========================================================

def send_telegram(message):

    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("未配置TG通知")
        return

    try:

        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

        data = {
            "chat_id": TG_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }

        requests.post(
            url,
            data=data,
            timeout=15
        )

    except Exception:
        traceback.print_exc()


# =========================================================
# IP检测
# =========================================================

def is_valid_ipv4(ip):

    try:

        parts = ip.split(".")

        return (
            len(parts) == 4 and
            all(
                p.isdigit() and 0 <= int(p) <= 255
                for p in parts
            )
        )

    except:
        return False


def get_cf_speed_test_ip():

    url = "https://ip.164746.xyz/ipTop.html"

    all_ips = []

    try:

        print(f"获取优选IP: {url}")

        r = requests.get(
            url,
            timeout=15
        )

        r.raise_for_status()

        ips = re.findall(
            r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
            r.text
        )

        for ip in ips:

            if is_valid_ipv4(ip):

                if ip not in all_ips:
                    all_ips.append(ip)

    except Exception:

        print("获取优选IP失败")
        traceback.print_exc()

    print(f"获取到 {len(all_ips)} 个优选IP")

    return all_ips


# =========================================================
# Cloudflare DNS
# =========================================================

def get_existing_records():

    try:

        resp = requests.get(
            BASE_URL,
            headers=HEADERS,
            params={
                "per_page": 100
            },
            timeout=15
        )

        resp.raise_for_status()

        data = resp.json()

        if not data.get("success"):

            print("Cloudflare API失败")
            print(data)

            return {}

        records = {}

        for r in data.get("result", []):

            key = f"{r['type']}:{r['name'].lower()}"

            records[key] = {
                "id": r["id"],
                "content": r["content"],
                "type": r["type"]
            }

        return records

    except Exception:

        print("获取DNS记录失败")
        traceback.print_exc()

        return {}


def create_record(record_type, name, content):

    try:

        data = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": 60,
            "proxied": False
        }

        resp = requests.post(
            BASE_URL,
            headers=HEADERS,
            json=data,
            timeout=15
        )

        result = resp.json()

        if result.get("success"):

            print(f"🆕 创建 {record_type} {name} -> {content}")

            return True

        print(result)

        return False

    except Exception:

        traceback.print_exc()

        return False


def update_record(record_id, record_type, name, content):

    try:

        url = f"{BASE_URL}/{record_id}"

        data = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": 60,
            "proxied": False
        }

        resp = requests.put(
            url,
            headers=HEADERS,
            json=data,
            timeout=15
        )

        result = resp.json()

        if result.get("success"):

            print(f"✅ 更新 {record_type} {name} -> {content}")

            return True

        print(result)

        return False

    except Exception:

        traceback.print_exc()

        return False


# =========================================================
# 主程序
# =========================================================

def main():

    tg_results = []

    # 环境变量检查
    if not CF_API_TOKEN:
        print("缺少 CF_API_TOKEN")
        return

    if not CF_ZONE_ID:
        print("缺少 CF_ZONE_ID")
        return

    # 获取优选IP
    ips = get_cf_speed_test_ip()

    if not ips:

        msg = "❌ 未获取到优选IP"

        print(msg)

        send_telegram(msg)

        return

    # 获取DNS记录
    existing = get_existing_records()

    updated_count = 0

    # =====================================================
    # A记录
    # =====================================================

    print("\n========== A记录 ==========\n")

    for index, domain in enumerate(A_RECORDS):

        if updated_count >= MAX_TOTAL_UPDATES:
            break

        ip = ips[index % len(ips)]

        key = f"A:{domain.lower()}"

        # 已存在
        if key in existing:

            record = existing[key]

            # IP相同
            if record["content"] == ip:

                print(f"跳过 A {domain} -> {ip}")

                tg_results.append(
                    f"⏭ 跳过A\n{domain}\n{ip}"
                )

                continue

            # 更新
            success = update_record(
                record["id"],
                "A",
                domain,
                ip
            )

            if success:

                updated_count += 1

                tg_results.append(
                    f"✅ 更新A\n{domain}\n→ {ip}"
                )

        # 不存在
        else:

            success = create_record(
                "A",
                domain,
                ip
            )

            if success:

                updated_count += 1

                tg_results.append(
                    f"🆕 创建A\n{domain}\n→ {ip}"
                )

    # =====================================================
    # CNAME记录
    # =====================================================

    print("\n========== CNAME ==========\n")

    cname_ips = ips[:4]

    for index, (subdomain, target) in enumerate(CNAME_TARGETS.items()):

        if updated_count >= MAX_TOTAL_UPDATES:
            break

        ip_tag = cname_ips[index % len(cname_ips)].replace(".", "-")

        cname_name = f"{ip_tag}.{subdomain}"

        key = f"CNAME:{cname_name.lower()}"

        # 已存在
        if key in existing:

            record = existing[key]

            # 已相同
            if record["content"].lower() == target.lower():

                print(f"跳过 CNAME {cname_name}")

                tg_results.append(
                    f"⏭ 跳过CNAME\n{cname_name}"
                )

                continue

            # 更新
            success = update_record(
                record["id"],
                "CNAME",
                cname_name,
                target
            )

            if success:

                updated_count += 1

                tg_results.append(
                    f"✅ 更新CNAME\n{cname_name}\n→ {target}"
                )

        # 创建
        else:

            success = create_record(
                "CNAME",
                cname_name,
                target
            )

            if success:

                updated_count += 1

                tg_results.append(
                    f"🆕 创建CNAME\n{cname_name}\n→ {target}"
                )

    # =====================================================
    # 输出
    # =====================================================

    print("\n==============================")
    print(f"更新数量: {updated_count}")
    print("==============================")

    # =====================================================
    # Telegram通知
    # =====================================================

    try:

        if tg_results:

            message = (
                f"🌐 DNS自动更新完成\n\n"
                f"域名: {DOMAIN_ROOT}\n"
                f"更新数量: {updated_count}\n\n"
                + "\n\n".join(tg_results[:20])
            )

        else:

            message = (
                f"🌐 DNS检查完成\n\n"
                f"{DOMAIN_ROOT}\n"
                f"无需更新"
            )

        send_telegram(message)

    except Exception:

        traceback.print_exc()


# =========================================================
# 入口
# =========================================================

if __name__ == "__main__":

    main()

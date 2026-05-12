import os
import requests
import re
import traceback

# =========================================================
# 配置
# =========================================================

CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")

# 兼容 TG_CHAT_ID / TG_USER_ID
TG_CHAT_ID = os.environ.get("TG_CHAT_ID") or os.environ.get("TG_USER_ID")
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")

DOMAIN_ROOT = "072503.xyz"

# 最大DNS记录数量
MAX_TOTAL_RECORDS = 10

# 最大A记录数量
MAX_A_RECORDS = 4

# =========================================================
# A记录
# =========================================================
# (域名, 使用第几个优选IP)

A_RECORDS = [

    ("dns.072503.xyz", 0),
    ("dns.072503.xyz", 1),

    ("dns1.072503.xyz", 0),

    ("dns2.072503.xyz", 1),
]

# =========================================================
# CNAME记录
# =========================================================

CNAME_TARGETS = {
    "cf1.072503.xyz": "www.visa.cn",
    "cf2.072503.xyz": "store.ubi.com",
    "cf3.072503.xyz": "www.shopify.com",
    "cf4.072503.xyz": "mfa.gov.ua"
}

# =========================================================
# Cloudflare API
# =========================================================

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

        resp = requests.post(
            url,
            data=data,
            timeout=15
        )

        if resp.status_code == 200:
            print("Telegram通知发送成功")
        else:
            print("Telegram通知失败")
            print(resp.text)

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

            return []

        return data.get("result", [])

    except Exception:

        print("获取DNS记录失败")
        traceback.print_exc()

        return []


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

    if not CF_API_TOKEN:
        print("缺少 CF_API_TOKEN")
        return

    if not CF_ZONE_ID:
        print("缺少 CF_ZONE_ID")
        return

    # =====================================================
    # 获取优选IP
    # =====================================================

    ips = get_cf_speed_test_ip()

    if not ips:

        msg = "❌ 未获取到优选IP"

        print(msg)

        send_telegram(msg)

        return

    # =====================================================
    # 获取现有DNS
    # =====================================================

    existing = get_existing_records()

    updated_count = 0

    # 当前DNS总数
    current_total_records = len(existing)

    # 当前A记录数量
    current_a_records = len([
        r for r in existing
        if r["type"] == "A"
    ])

    # =====================================================
    # A记录
    # =====================================================

    print("\n========== A记录 ==========\n")

    for domain, ip_index in A_RECORDS:

        ip = ips[ip_index % len(ips)]

        found = False

        for record in existing:

            if record["type"] != "A":
                continue

            if (
                record["name"].lower() == domain.lower()
                and record["content"] == ip
            ):

                found = True

                print(f"跳过 A {domain} -> {ip}")

                tg_results.append(
                    f"⏭ 跳过A\n{domain}\n{ip}"
                )

                break

        # 不存在则创建
        if not found:

            # 超过A记录限制
            if current_a_records >= MAX_A_RECORDS:

                print(f"A记录达到上限 跳过 {domain}")

                tg_results.append(
                    f"⚠️ A记录达到上限\n{domain}"
                )

                continue

            # 超过总记录限制
            if current_total_records >= MAX_TOTAL_RECORDS:

                print(f"DNS总记录达到上限 跳过 {domain}")

                tg_results.append(
                    f"⚠️ DNS记录达到上限\n{domain}"
                )

                continue

            success = create_record(
                "A",
                domain,
                ip
            )

            if success:

                current_a_records += 1
                current_total_records += 1
                updated_count += 1

                tg_results.append(
                    f"🆕 创建A\n{domain}\n→ {ip}"
                )

    # =====================================================
    # CNAME记录
    # =====================================================

    print("\n========== CNAME ==========\n")

    for cname_name, target in CNAME_TARGETS.items():

        found = False

        for record in existing:

            if record["type"] != "CNAME":
                continue

            if (
                record["name"].lower() == cname_name.lower()
            ):

                found = True

                # 相同则跳过
                if record["content"].lower() == target.lower():

                    print(f"跳过 CNAME {cname_name}")

                    tg_results.append(
                        f"⏭ 跳过CNAME\n{cname_name}"
                    )

                else:

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

                break

        # 不存在则创建
        if not found:

            if current_total_records >= MAX_TOTAL_RECORDS:

                print(f"DNS总记录达到上限 跳过 {cname_name}")

                tg_results.append(
                    f"⚠️ DNS记录达到上限\n{cname_name}"
                )

                continue

            success = create_record(
                "CNAME",
                cname_name,
                target
            )

            if success:

                current_total_records += 1
                updated_count += 1

                tg_results.append(
                    f"🆕 创建CNAME\n{cname_name}\n→ {target}"
                )

    # =====================================================
    # 输出
    # =====================================================

    print("\n==============================")
    print(f"更新数量: {updated_count}")
    print(f"当前DNS记录数: {current_total_records}")
    print("==============================")

    # =====================================================
    # Telegram通知
    # =====================================================

    try:

        if tg_results:

            message = (
                f"🌐 DNS自动更新完成\n\n"
                f"域名: {DOMAIN_ROOT}\n"
                f"更新数量: {updated_count}\n"
                f"当前DNS记录数: {current_total_records}\n\n"
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

import os
import requests
import re
import traceback

# ==================== 环境变量 ====================
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")       # Cloudflare API Token
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")           # 072503.xyz 的 Zone ID
TG_CHAT_ID = os.environ.get("TG_CHAT_ID") or os.environ.get("TG_USER_ID")  # Telegram Chat ID
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")       # Telegram Bot Token
DOMAIN_ROOT = "072503.xyz"                           # 主域名

# ==================== 配置区 ====================

# 不受脚本管理的 DNS 记录名（小写），不会被删除/修改
PROTECTED_NAMES = {
    "072503.xyz",                              # 根域 CNAME → Pages 项目
    "origin.072503.xyz",                       # SaaS Fallback Origin（橙色云）
    "custom-hostname-fallback.072503.xyz",     # SaaS Fallback 辅助记录（橙色云）
}

# 需要开启代理（橙色云）的 A 记录名（小写）
PROXIED_A_NAMES = {
    "custom-hostname-fallback.072503.xyz",     # SaaS 需要代理才能正常回源
}

# 优选IP的A记录，格式：(子域名, ipTop.html返回的IP索引)
A_RECORDS = [
    # ip.164746.xyz 的IP（综合优选）
    ("dns.072503.xyz",  0),                         # 优选IP入口1（IP[0]）
    ("dns.072503.xyz",  1),                         # 优选IP入口2（IP[1]）
    ("custom-hostname-fallback.072503.xyz", 0),     # SaaS fallback辅助（IP[0]）

    ####################################反代 ip##################################
    # 电信优选IP
    ("ct.072503.xyz",  0),                          # 电信IP[0]
    ("ct.072503.xyz",  1),                          # 电信IP[1]
    ("ct.072503.xyz",  2),                          # 电信IP[2]

    # 联通优选IP
    ("cu.072503.xyz",  0),                          # 联通IP[0]
    ("cu.072503.xyz",  1),                          # 联通IP[1]
    ("cu.072503.xyz",  2),                          # 联通IP[2]

    # 移动优选IP
    ("cmcc.072503.xyz", 0),                         # 移动IP[0]
    ("cmcc.072503.xyz", 1),                         # 移动IP[1]
    ("cmcc.072503.xyz", 2),                         # 移动IP[2]

    # 反代IP
    ("proxy.072503.xyz", 0),                        # 反代IP[0]
    ("proxy.072503.xyz", 1),                        # 反代IP[1]
    ("proxy.072503.xyz", 2),                        # 反代IP[2]
    ######################################################################################
]

# 直接CNAME记录（不走SaaS，不需要Custom Hostname，IP自动跟随目标域名）
DIRECT_CNAME_RECORDS = [
    ("dns1.072503.xyz", "saas.sin.fan"),   # 备用解析
    ("dns2.072503.xyz", "saas.sin.fan"),   # 备用解析
]

# SaaS CNAME记录（需要Custom Hostname，记录名不含IP，IP变化时无需重建）
# 格式：(标签, 优选域名)，生成记录名如：cf1.072503.xyz → www.visa.cn
CNAME_RECORDS = [
    ("cf1", "www.visa.cn"),       # 优选域名1

    ####育碧(Ubisoft)官方商店域名，使用 CloudFlare CDN 服务。作为全球知名游戏厂商的商店域名，线路质量可靠，稳定性好。#########
    ("cf2", "store.ubi.com"),     # 优选域名2
    ##################################################################################################################


    ####全球知名电商建站平台 Shopify 官方域名，使用 CloudFlare 企业级 CDN。商业平台域名，线路质量优秀，全球节点覆盖广泛。#######
    ("cf3", "www.shopify.com"),   # 优选域名3
    ###################################################################################################################

    #####乌克兰外交部官方域名，采用 CloudFlare CDN 服务。作为政府官网，域名信誉度高，稳定性好，适合长期使用。###################
    ("cf4", "mfa.gov.ua"),        # 优选域名4
    ###################################################################################################################



    ###########################  MIYU维护 网址：https://saas.sin.fan/ #############################
    ("cf5", "saas.sin.fan"),      # 优选域名5
    ##############################################################################################


    ###########################   秋名山维护 网址: https://www.qmsdh.com/  #####################
    ("cf6", "cf.877774.xyz"),     # 三网自适应
    ###############################################################################################
    ("cf7", "asia.877774.xyz"),   # 亚洲优选
    ("cf8", "eur.877774.xyz"),    # 欧洲优选
    ("cf9", "na.877774.xyz"),     # 美洲优选
    ##############################################################################################


    ##############################  fishcpy维护 网址:  https://www.byoip.top/#############
    ("cf10", "cloudflare-dl.byoip.top"),      #一级域名
    ################################################################################################
    ("cf11", "cloudflare.19931110.xyz"),    #CloudFlare 单IPv4版    #全球加速   高可用    --#泛域名  
    ("cf12", "cf.cnae.top"),                 #CloudFlare 带IPv6版   #全球加速   双栈      --#泛域名 
    ("cf13", "edgeone.19931110.xyz"),        #EdgeOne CDN 优选服务   #Tencent 全球优化    --#泛域名 
    ("cf14", "netlify.19931110.xyz"),        #Netlify CDN 优选服务  #AWS  全球优化        --#泛域名 
    ("cf15", "vercel.19931110.xyz"),         #Vercel CDN 优选服务     #AWS    全球优化    --#泛域名 
    ###############################################################################################



    #############   WeTest.Vip维护   网址: https://www.wetest.vip/#########################################
    ("cf16", "cloudflare.182682.xyz"),    #IPV4&6 全网、移动、联通、电信 15IP/15分钟   CloudFlare官方IP优选
    ("cf17", "cloudfront.182682.xyz"),    #IPV4&6  全网、移动、联通、电信 15IP/15分钟   CloudFlare官方IP优选
    ("cf18", "edgeone.182682.xyz"),       #IPV4&6  全网、移动、联通、电信 15IP/15分钟   EdgeOne官方IP优选
    #####################################################################################################



    ############################# ktff维护  优质的优选域名##############################################
    ("cf19", "cf.tencentapp.cn"),
    ###################################################################################################


    ########    NexusMods 静态资源分发域名，全球最大的游戏MOD社区。采用 CloudFlare CDN，资源分发网络覆盖全球，访问稳定。##############
    ("cf20", "staticdelivery.nexusmods.com"),
    #####################################################################################################################


    #########################################   https://time.is 官方优选#######################################################
    ("cf21", "time.is"),
    ################################################################################################################


    ############################################    icook.hk#官方优选   #################################################
    ("cf22", "icook.hk"),
    ###################################################################################################################


    ############################################    icook.tw#官方优选   ################################################
    ("cf23", "icook.tw"),
    ######################################################################################################################
]

# DNS记录总数上限（免费版最多200条，设50留余量）
MAX_TOTAL_RECORDS = 50

# ==================== API 基础 ====================
BASE_URL = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
HEADERS = {
    "Authorization": f"Bearer {CF_API_TOKEN}",
    "Content-Type": "application/json"
}

# ==================== Telegram 通知 ====================

def send_telegram(message):
    """发送 Telegram 通知"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("未配置TG通知")
        return
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.post(url, data=data, timeout=15)
        if resp.status_code == 200:
            print("Telegram通知发送成功")
        else:
            print("Telegram通知失败")
            print(resp.text)
    except Exception:
        traceback.print_exc()

# ==================== 工具函数 ====================

def is_valid_ipv4(ip):
    """验证是否为合法 IPv4 地址"""
    try:
        parts = ip.split(".")
        return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
    except Exception:
        return False

# ==================== 优选 IP 获取 ====================

def get_cf_speed_test_ip():
    """从 ipTop.html 获取优选IP列表"""
    urls = ["https://ip.164746.xyz/ipTop.html"]
    all_ips = []
    for url in urls:
        try:
            print(f"获取优选IP: {url}")
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', r.text)
            for ip in ips:
                if is_valid_ipv4(ip) and ip not in all_ips:
                    all_ips.append(ip)
            if all_ips:
                break
        except Exception:
            print(f"获取优选IP失败: {url}")
            traceback.print_exc()
    print(f"获取到 {len(all_ips)} 个优选IP")
    return all_ips

def get_isp_ips(isp, count=6):
    """从 cf.090227.xyz 按运营商获取优选IP"""
    url = f"https://cf.090227.xyz/{isp}?ips={count}"
    ips = []
    try:
        print(f"获取{isp}优选IP: {url}")
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        for line in r.text.strip().splitlines():
            ip = line.split("#")[0].strip()
            if is_valid_ipv4(ip) and ip not in ips:
                ips.append(ip)
    except Exception:
        print(f"获取{isp}优选IP失败: {url}")
        traceback.print_exc()
    print(f"获取到 {len(ips)} 个{isp}优选IP")
    return ips


def get_bestproxy_ips(count=6):
    """从 ipdb.api.030101.xyz 获取反代IP"""
    url = f"https://ipdb.api.030101.xyz/?type=bestproxy&country=true"
    ips = []
    try:
        print(f"获取反代IP: {url}")
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        for line in r.text.strip().splitlines():
            ip = line.split("#")[0].strip()
            if is_valid_ipv4(ip) and ip not in ips:
                ips.append(ip)
                if len(ips) >= count:
                    break
    except Exception:
        print(f"获取反代IP失败: {url}")
        traceback.print_exc()
    print(f"获取到 {len(ips)} 个反代IP")
    return ips




# ==================== DNS 记录操作 ====================

def get_existing_records():
    """获取区域内所有 DNS 记录（自动翻页）"""
    all_records = []
    page = 1
    try:
        while True:
            resp = requests.get(BASE_URL, headers=HEADERS, params={"per_page": 100, "page": page}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                print("Cloudflare API失败")
                return all_records
            all_records.extend(data.get("result", []))
            if page >= data.get("result_info", {}).get("total_pages", 1):
                break
            page += 1
    except Exception:
        print("获取DNS记录失败")
        traceback.print_exc()
    return all_records

def create_record(record_type, name, content, proxied=False):
    """创建 DNS 记录"""
    try:
        data = {"type": record_type, "name": name, "content": content, "ttl": 60, "proxied": proxied}
        resp = requests.post(BASE_URL, headers=HEADERS, json=data, timeout=15)
        result = resp.json()
        if result.get("success"):
            print(f"创建 {record_type} {name} -> {content} (proxied={proxied})")
            return True
        print(result)
        return False
    except Exception:
        traceback.print_exc()
        return False

def update_record(record_id, record_type, name, content, proxied=False):
    """更新 DNS 记录"""
    try:
        url = f"{BASE_URL}/{record_id}"
        data = {"type": record_type, "name": name, "content": content, "ttl": 60, "proxied": proxied}
        resp = requests.put(url, headers=HEADERS, json=data, timeout=15)
        result = resp.json()
        if result.get("success"):
            print(f"更新 {record_type} {name} -> {content} (proxied={proxied})")
            return True
        print(result)
        return False
    except Exception:
        traceback.print_exc()
        return False

def delete_record(record_id):
    """删除 DNS 记录"""
    try:
        url = f"{BASE_URL}/{record_id}"
        resp = requests.delete(url, headers=HEADERS, timeout=15)
        result = resp.json()
        if result.get("success"):
            print(f"删除记录 {record_id}")
            return True
        print(result)
        return False
    except Exception:
        traceback.print_exc()
        return False
# ==================== Custom Hostname 操作 ====================

CH_BASE_URL = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/custom_hostnames"

def get_custom_hostnames():
    """获取所有 Custom Hostname（自动翻页）"""
    all_ch = []
    page = 1
    try:
        while True:
            resp = requests.get(CH_BASE_URL, headers=HEADERS, params={"per_page": 50, "page": page}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                print("获取Custom Hostname失败")
                return all_ch
            all_ch.extend(data.get("result", []))
            if page >= data.get("result_info", {}).get("total_pages", 1):
                break
            page += 1
    except Exception:
        print("获取Custom Hostname异常")
        traceback.print_exc()
    return all_ch

def create_custom_hostname(hostname):
    """创建 Custom Hostname（自动签发 DV 证书，HTTP DCV 验证）"""
    try:
        data = {"hostname": hostname, "ssl": {"method": "http", "type": "dv", "wildcard": False}}
        resp = requests.post(CH_BASE_URL, headers=HEADERS, json=data, timeout=15)
        result = resp.json()
        if result.get("success"):
            print(f"创建 Custom Hostname: {hostname}")
            return True
        print(f"创建 Custom Hostname 失败: {hostname}")
        print(result)
        return False
    except Exception:
        traceback.print_exc()
        return False

def delete_custom_hostname(ch_id, hostname=""):
    """删除 Custom Hostname"""
    try:
        url = f"{CH_BASE_URL}/{ch_id}"
        resp = requests.delete(url, headers=HEADERS, timeout=15)
        result = resp.json()
        if result.get("success"):
            print(f"删除 Custom Hostname: {hostname} ({ch_id})")
            return True
        print(f"删除 Custom Hostname 失败: {ch_id}")
        print(result)
        return False
    except Exception:
        traceback.print_exc()
        return False

def check_and_fix_custom_hostname(hostname, ch_data):
    """检查 Custom Hostname 的 SSL 状态，失败则重新验证"""
    ssl_status = ch_data.get("ssl", {}).get("status", "")
    ssl_method = ch_data.get("ssl", {}).get("method", "")

    if ssl_status == "active":
        print(f"SSL正常: {hostname}")
        return False

    print(f"SSL异常: {hostname} 状态={ssl_status} 方法={ssl_method}")

    # 重新验证 SSL
    if ssl_status in ("pending_validation", "validation_failed", "expired", "inactive"):
        try:
            url = f"{CH_BASE_URL}/{ch_data['id']}"
            data = {"ssl": {"method": "http", "type": "dv", "wildcard": False}}
            resp = requests.patch(url, headers=HEADERS, json=data, timeout=15)
            result = resp.json()
            if result.get("success"):
                print(f"重新验证SSL: {hostname}")
                return True
            else:
                print(f"重新验证SSL失败: {hostname}")
                print(result)
                return False
        except Exception:
            traceback.print_exc()
            return False
    return False


# ==================== 主逻辑 ====================

def main():
    tg_results = []
    if not CF_API_TOKEN:
        print("缺少环境变量 CF_API_TOKEN")
        return
    if not CF_ZONE_ID:
        print("缺少环境变量 CF_ZONE_ID")
        return

    # 1. 分别获取优选IP
    ips = get_cf_speed_test_ip()          # ip.164746.xyz 综合优选
    ct_ips = get_isp_ips("ct", 6)         # 电信优选
    cu_ips = get_isp_ips("cu", 6)         # 联通优选
    cmcc_ips = get_isp_ips("cmcc", 6)     # 移动优选
    proxy_ips = get_bestproxy_ips(6)      # 反代IP

    if not ips and not ct_ips and not cu_ips and not cmcc_ips and not proxy_ips:
        send_telegram("❌ 未获取到任何优选IP")
        return
    # 部分API失败时通知
    warnings = []
    if not ips:
        warnings.append("ip.164746.xyz 获取失败")
    if not ct_ips:
        warnings.append("电信优选IP获取失败")
    if not cu_ips:
        warnings.append("联通优选IP获取失败")
    if not cmcc_ips:
        warnings.append("移动优选IP获取失败")
    if not proxy_ips:
        warnings.append("反代IP获取失败")
    if warnings:
        print(f"警告: {', '.join(warnings)}")


    # 2. 获取现有 DNS 记录
    existing = get_existing_records()
    existing_a_map = {}
    for r in existing:
        if r["type"] == "A":
            existing_a_map[(r["name"].lower(), r["content"])] = r
    existing_cname_map = {}
    for r in existing:
        if r["type"] == "CNAME":
            existing_cname_map[r["name"].lower()] = r

    # 3. 获取现有 Custom Hostname
    ch_list = get_custom_hostnames()
    ch_map = {}
    for ch in ch_list:
        ch_map[ch["hostname"].lower()] = ch

    updated_count = 0
    current_total_records = len(existing)

    # ==================== A 记录处理 ====================
    print("\n========== A记录 ==========\n")

    desired_a = []
    for domain, ip_index in A_RECORDS:
        if domain.startswith("ct."):
            ip_list = ct_ips
        elif domain.startswith("cu."):
            ip_list = cu_ips
        elif domain.startswith("cmcc."):
            ip_list = cmcc_ips
        elif domain.startswith("proxy."):
            ip_list = proxy_ips
        else:
            ip_list = ips
        if ip_list:
            ip = ip_list[ip_index % len(ip_list)]
            desired_a.append((domain.lower(), ip))


    existing_a_set = set(existing_a_map.keys())
    desired_a_set = set(desired_a)
    existing_a_by_name = {}
    for (name, ip), r in existing_a_map.items():
        existing_a_by_name.setdefault(name, []).append(r)

    for domain_lower, ip in desired_a:
        proxied = domain_lower in PROXIED_A_NAMES
        if (domain_lower, ip) in existing_a_set:
            existing_r = existing_a_map[(domain_lower, ip)]
            if existing_r.get("proxied") != proxied:
                if update_record(existing_r["id"], "A", domain_lower, ip, proxied=proxied):
                    updated_count += 1
                    tg_results.append(f"更新A代理状态\n{domain_lower}\nproxied={proxied}")
            else:
                print(f"跳过 A {domain_lower} -> {ip}")
                tg_results.append(f"跳过A\n{domain_lower}\n{ip}")
            continue
        same_name_records = existing_a_by_name.get(domain_lower, [])
        if same_name_records:
            record_to_update = None
            for r in same_name_records:
                if (domain_lower, r["content"]) not in desired_a_set:
                    record_to_update = r
                    break
            if record_to_update:
                if update_record(record_to_update["id"], "A", domain_lower, ip, proxied=proxied):
                    old_key = (domain_lower, record_to_update["content"])
                    existing_a_map.pop(old_key, None)
                    existing_a_set.discard(old_key)
                    new_key = (domain_lower, ip)
                    existing_a_set.add(new_key)
                    same_name_records.remove(record_to_update)
                    new_record = {"id": record_to_update["id"], "type": "A", "name": domain_lower, "content": ip, "proxied": proxied}
                    same_name_records.append(new_record)
                    existing_a_map[new_key] = new_record
                    updated_count += 1
                    tg_results.append(f"更新A\n{domain_lower}\n-> {ip}")
        else:
            if current_total_records >= MAX_TOTAL_RECORDS:
                tg_results.append(f"DNS记录达到上限\n{domain_lower}")
                continue
            if create_record("A", domain_lower, ip, proxied=proxied):
                current_total_records += 1
                updated_count += 1
                existing_a_set.add((domain_lower, ip))

                # 注意：id="new" 是占位符，仅用于本轮循环的内存状态追踪，不会用于API调用
                new_record = {"id": "new", "type": "A", "name": domain_lower, "content": ip, "proxied": proxied}

                existing_a_by_name.setdefault(domain_lower, []).append(new_record)
                existing_a_map[(domain_lower, ip)] = new_record
                tg_results.append(f"创建A\n{domain_lower}\n-> {ip}")

    # ==================== 直接 CNAME 处理 ====================
    print("\n========== 直接CNAME ==========\n")

    for name, target in DIRECT_CNAME_RECORDS:
        name_lower = name.lower()
        existing_record = existing_cname_map.get(name_lower)
        if existing_record:
            if existing_record["content"].lower() == target.lower():
                print(f"跳过 CNAME {name_lower} -> {target}")
                tg_results.append(f"跳过CNAME\n{name_lower}")
            else:
                if update_record(existing_record["id"], "CNAME", existing_record["name"], target):
                    updated_count += 1
                    tg_results.append(f"更新CNAME\n{name_lower}\n-> {target}")
        else:
            same_name_a = existing_a_by_name.get(name_lower, [])
            if same_name_a:
                for r in same_name_a:
                    if delete_record(r["id"]):
                        existing_a_map.pop((name_lower, r["content"]), None)
                        current_total_records -= 1
                        updated_count += 1
                        tg_results.append(f"删除A记录\n{name_lower}\n{r['content']}")
            if current_total_records >= MAX_TOTAL_RECORDS:
                tg_results.append(f"DNS记录达到上限\n{name_lower}")
                continue
            if create_record("CNAME", name_lower, target):
                current_total_records += 1
                updated_count += 1
                existing_cname_map[name_lower] = {"id": "new", "type": "CNAME", "name": name_lower, "content": target}
                tg_results.append(f"创建CNAME\n{name_lower}\n-> {target}")

    # ==================== SaaS CNAME + Custom Hostname 处理 ====================
    print("\n========== SaaS CNAME + Custom Hostname ==========\n")

    desired_cname_names = set()

    for cf_tag, target in CNAME_RECORDS:
        cname_name = f"{cf_tag}.{DOMAIN_ROOT}".lower()
        desired_cname_names.add(cname_name)
        existing_record = existing_cname_map.get(cname_name)
        if existing_record:
            if existing_record["content"].lower() == target.lower():
                print(f"跳过 CNAME {cname_name} -> {target}")
                tg_results.append(f"跳过CNAME\n{cname_name}")
            else:
                if update_record(existing_record["id"], "CNAME", existing_record["name"], target):
                    updated_count += 1
                    tg_results.append(f"更新CNAME\n{cname_name}\n-> {target}")
        else:
            if current_total_records >= MAX_TOTAL_RECORDS:
                tg_results.append(f"DNS记录达到上限\n{cname_name}")
                continue
            if create_record("CNAME", cname_name, target):
                current_total_records += 1
                updated_count += 1
                existing_cname_map[cname_name] = {"id": "new", "type": "CNAME", "name": cname_name, "content": target}
                tg_results.append(f"创建CNAME\n{cname_name}\n-> {target}")

        # 确保 Custom Hostname 存在
        if cname_name not in ch_map:
            if create_custom_hostname(cname_name):
                updated_count += 1
                tg_results.append(f"创建CH\n{cname_name}")
        else:
            # 检查已有 Custom Hostname 的 SSL 状态
            ch_data = ch_map[cname_name]
            if check_and_fix_custom_hostname(cname_name, ch_data):
                updated_count += 1
                ssl_status = ch_data.get("ssl", {}).get("status", "unknown")
                tg_results.append(f"重新验证SSL\n{cname_name}\n状态: {ssl_status}")



    # ==================== 清理孤立 Custom Hostname ====================
    print("\n========== 清理孤立 Custom Hostname ==========\n")

    for ch_hostname, ch in list(ch_map.items()):
        if ch_hostname in PROTECTED_NAMES:
            continue
        is_cf_tag = any(ch_hostname == f"{tag}.{DOMAIN_ROOT}".lower() for tag, _ in CNAME_RECORDS)
        if is_cf_tag and ch_hostname not in desired_cname_names:
            print(f"清理孤立CH: {ch_hostname}")
            if delete_custom_hostname(ch["id"], ch_hostname):
                updated_count += 1
                tg_results.append(f"清理孤立CH\n{ch_hostname}")

    # ==================== 清理旧IP-tag CNAME（迁移用） ====================
    print("\n========== 清理旧IP-tag CNAME ==========\n")

    for name_lower, r in list(existing_cname_map.items()):
        old_pattern = re.compile(r'^\d+-\d+-\d+-\d+\.')
        if old_pattern.match(name_lower) and name_lower not in PROTECTED_NAMES:
            print(f"清理旧IP-tag CNAME: {name_lower}")
            if delete_record(r["id"]):
                updated_count += 1
                tg_results.append(f"清理旧CNAME\n{name_lower}")

    # ==================== 结果汇总 ====================
    print("\n==============================")
    print(f"更新数量: {updated_count}")
    print(f"当前DNS记录数: {current_total_records}")
    print("==============================")

    try:
        # 按类型分类统计
        created_a = [r for r in tg_results if r.startswith("创建A")]
        updated_a = [r for r in tg_results if r.startswith("更新A")]
        skipped_a = [r for r in tg_results if r.startswith("跳过A")]
        created_cname = [r for r in tg_results if r.startswith("创建CNAME")]
        updated_cname = [r for r in tg_results if r.startswith("更新CNAME")]
        skipped_cname = [r for r in tg_results if r.startswith("跳过CNAME")]
        created_ch = [r for r in tg_results if r.startswith("创建CH")]
        cleaned = [r for r in tg_results if r.startswith("清理")]
        deleted = [r for r in tg_results if r.startswith("删除")]
        warnings_list = [r for r in tg_results if r.startswith("DNS记录达到上限")]

        if not tg_results:
            message = f"✅ DNS检查完成\n\n<b>域名:</b> {DOMAIN_ROOT}\n<b>状态:</b> 无需更新"
        else:
            lines = []
            lines.append(f"🔄 <b>DNS自动更新完成</b>\n")
            lines.append(f"<b>域名:</b> {DOMAIN_ROOT}")
            lines.append(f"<b>更新数量:</b> {updated_count}")
            lines.append(f"<b>DNS记录数:</b> {current_total_records}\n")

            # IP来源信息
            lines.append("📡 <b>IP来源:</b>")
            if ips:
                lines.append(f"  综合: {ips[0]}")
            if ct_ips:
                lines.append(f"  电信: {', '.join(ct_ips[:2])}")
            if cu_ips:
                lines.append(f"  联通: {', '.join(cu_ips[:2])}")
            if cmcc_ips:
                lines.append(f"  移动: {', '.join(cmcc_ips[:2])}")
            if proxy_ips:
                lines.append(f"  反代: {', '.join(proxy_ips[:2])}")
            # A记录变更
            if created_a or updated_a:
                lines.append(f"\n🟢 <b>A记录变更 ({len(created_a) + len(updated_a)})</b>")
                for r in created_a:
                    parts = r.split("\n")
                    lines.append(f"  ➕ {' → '.join(parts[1:])}")
                for r in updated_a:
                    parts = r.split("\n")
                    lines.append(f"  ✏️ {' → '.join(parts[1:])}")

            # CNAME变更
            if created_cname or updated_cname:
                lines.append(f"\n🔵 <b>CNAME变更 ({len(created_cname) + len(updated_cname)})</b>")
                for r in created_cname:
                    parts = r.split("\n")
                    lines.append(f"  ➕ {' → '.join(parts[1:])}")
                for r in updated_cname:
                    parts = r.split("\n")
                    lines.append(f"  ✏️ {' → '.join(parts[1:])}")

            # Custom Hostname
            if created_ch:
                lines.append(f"\n🔒 <b>Custom Hostname ({len(created_ch)})</b>")
                for r in created_ch:
                    parts = r.split("\n")
                    lines.append(f"  ➕ {parts[-1]}")

            # SSL重新验证
            ssl_fixed = [r for r in tg_results if r.startswith("重新验证SSL")]
            if ssl_fixed:
                lines.append(f"\n🔐 <b>SSL重新验证 ({len(ssl_fixed)})</b>")
                for r in ssl_fixed:
                    parts = r.split("\n")
                    lines.append(f"  🔄 {parts[1]} ({parts[2] if len(parts) > 2 else ''})")


            # 清理
            if cleaned or deleted:
                lines.append(f"\n🗑️ <b>清理 ({len(cleaned) + len(deleted)})</b>")
                for r in cleaned + deleted:
                    parts = r.split("\n")
                    lines.append(f"  ❌ {parts[-1]}")

            # 警告
            if warnings_list:
                lines.append(f"\n⚠️ <b>警告 ({len(warnings_list)})</b>")
                for r in warnings_list:
                    parts = r.split("\n")
                    lines.append(f"  ⚠️ {parts[-1]}")

            # API失败警告
            if warnings:
                lines.append(f"\n⚠️ <b>API失败:</b>")
                for w in warnings:
                    lines.append(f"  ❌ {w}")

            # 跳过统计
            skip_count = len(skipped_a) + len(skipped_cname)
            if skip_count > 0:
                lines.append(f"\n⏭️ <b>跳过:</b> {skip_count}条（无变化）")

            message = "\n".join(lines)

        if len(message) > 4000:
            chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for chunk in chunks:
                send_telegram(chunk)
        else:
            send_telegram(message)
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()


##############################################################################
##curl  解析返回
##curl -s na.877774.xyz | grep -oE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' | sort -u
##############################################################################

import os
import re
import time
import logging
import requests
import subprocess
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(threadName)s: %(message)s',
    handlers=[logging.StreamHandler()]
)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
process_lock = threading.Lock()

def send_msg(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    for attempt in range(3):
        try:
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200: return True
        except Exception as e:
            logging.error(f"TG发送失败: {e}")
        time.sleep(1)
    return False

def clean_stock_code(raw_text):
    cleaned = raw_text.strip().upper()
    cleaned = re.sub(r'^(SH|SZ|HK|US)', '', cleaned)
    if re.match(r'^\d+$', cleaned):
        if len(cleaned) == 5: return cleaned
        elif len(cleaned) < 5: return cleaned.zfill(5)
        return cleaned
    if re.match(r'^[A-Z\.\-]+$', cleaned):
        return cleaned
    return None

def execute_analysis_pipeline(chat_id, stock_code):
    if not process_lock.acquire(blocking=False):
        send_msg(chat_id, "⚠️ **系统繁忙**：AI 军师目前正在处理上一只股票的量化矩阵，请在 1 分钟后重新发送。")
        return

    try:
        current_env = os.environ.copy()
        current_env["TELEGRAM_CHAT_ID"] = str(chat_id)
        
        logging.info(f"⚡ 正在下达最高霸权指令，强行穿透并覆盖缓存，全量分析股票: {stock_code}")
        
        # 【🎯 核心修正】：使用 --stocks 参数直接进行极端肉搏，碾碎任何本地 .env 配置文件的执念！
        result = subprocess.run(
            ["python", "main.py", "--stocks", stock_code],
            env=current_env,
            capture_output=True,
            text=True,
            timeout=180
        )
        
        if result.returncode == 0:
            send_msg(chat_id, f"✅ **【{stock_code}】智能诊断完成**\n实盘级深度分析长文报告已在上方送达。")
        else:
            logging.error(f"引擎报错: {result.stderr}")
            send_msg(chat_id, f"❌ **分析中止**：内部组件抓取该股数据异常，请检查代码是否存在或稍后重试。")
            
    except subprocess.TimeoutExpired:
        send_msg(chat_id, f"⏱️ **系统熔断**：【{stock_code}】数据源延迟超 3 分钟，已自动强制终止。")
    finally:
        process_lock.release()

def poll_updates():
    offset = 0
    logging.info("🚀 V3 金融级动态交互外壳已在新加坡完全掌权，开始拦截全盘信号...")
    while True:
        try:
            response = requests.get(f"{BASE_URL}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
            if response.status_code != 200:
                time.sleep(5)
                continue
            res = response.json()
            if not res.get("ok") or not res.get("result"): continue
                
            for update in res["result"]:
                offset = update["update_id"] + 1
                message = update.get("message")
                if not message or "text" not in message: continue
                
                chat_id = message["chat"]["id"]
                raw_text = message["text"].strip()
                
                if raw_text in ["/start", "/help"]:
                    send_msg(chat_id, "🧠 **全功能动态股票智能量化助理 V3 满血版上线！**\n\n现在您可以随时向我发送任何 **A股、美股、港股** 的股票代码，拒绝任何指令错乱。")
                    continue
                
                stock_code = clean_stock_code(raw_text)
                if not stock_code: continue
                
                send_msg(chat_id, f"🔍 **动态拦截成功**\n已锁定目标：`{stock_code}`\n正在穿透本地缓存，强制为您提取该股最新量化研报……")
                
                t = threading.Thread(target=execute_analysis_pipeline, args=(chat_id, stock_code), name=f"Task-{stock_code}")
                t.start()
        except Exception as e:
            time.sleep(5)

if __name__ == "__main__":
    poll_updates()

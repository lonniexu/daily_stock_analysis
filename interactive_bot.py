import os
import re
import time
import logging
import requests
import subprocess
import threading

# 1. 工业级日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(threadName)s: %(message)s',
    handlers=[logging.StreamHandler()]
)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

# 2. 核心安全锁：防止多进程同时运行导致缓存文件读写冲突、数据污染
process_lock = threading.Lock()

def send_msg(chat_id, text):
    """工业级消息发送器，自带网络抖动重试机制"""
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    for attempt in range(3):
        try:
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                return True
            logging.warning(f"TG消息发送返回异常状态码: {res.status_code}")
        except Exception as e:
            logging.error(f"TG消息发送失败 (尝试 {attempt+1}/3): {e}")
        time.sleep(1)
    return False

def clean_stock_code(raw_text):
    """
    智能股票代码清洗器：
    1. 自动剔除 sh/sz/hk 等前缀
    2. 美股自动转为大写
    3. 规范化港股代码
    """
    cleaned = raw_text.strip().upper()
    # 移除可能带有的自制前缀，如 sh600863 -> 600863
    cleaned = re.sub(r'^(SH|SZ|HK|US)', '', cleaned)
    
    # A股/港股纯数字清洗
    if re.match(r'^\d+$', cleaned):
        if len(cleaned) == 5:  # 港股补正
            return cleaned
        elif len(cleaned) < 5: # 补齐港股前面的0，如 700 -> 00700
            return cleaned.zfill(5)
        return cleaned
    
    # 美股字母清洗
    if re.match(r'^[A-Z\.\-]+$', cleaned):
        return cleaned
        
    return None

def execute_analysis_pipeline(chat_id, stock_code):
    """独立线程任务：安全调用底层量化引擎，自带超时熔断"""
    # 尝试获取安全锁，如果被占用，说明系统正在处理别的股票
    if not process_lock.acquire(blocking=False):
        send_msg(chat_id, "⚠️ **系统繁忙**：AI 军师目前正在为您或他人处理上一只股票的量化模型，由于数据缓存隔离限制，请在 1 分钟后重新发送当前代码。")
        return

    try:
        # 构建完全隔离的运行时环境变量
        current_env = os.environ.copy()
        current_env["STOCK_LIST"] = stock_code
        current_env["TELEGRAM_CHAT_ID"] = str(chat_id)
        
        logging.info(f"开始为子进程点火，分析股票: {stock_code}")
        
        # 工业级防御：加入 timeout=180 秒强行熔断，防止底层爬虫死锁导致外壳永久挂起
        result = subprocess.run(
            ["python", "main.py"],
            env=current_env,
            capture_output=True,
            text=True,
            timeout=180  # 3分钟超时熔断
        )
        
        if result.returncode == 0:
            logging.info(f"股票 {stock_code} 分析成功")
            send_msg(chat_id, f"✅ **【{stock_code}】分析流程运行完毕**\n全功能智能量化长文报告已在上方通道送达。")
        else:
            logging.error(f"底层引擎报错退出: {result.stderr}")
            send_msg(chat_id, f"❌ **分析中止（底层数据源报错）**：\n内部组件在抓取或解析该股票时遇到障碍，建议稍后重试。")
            
    except subprocess.TimeoutExpired:
        logging.error(f"股票 {stock_code} 运行超时，触发熔断")
        send_msg(chat_id, f"⏱️ **系统熔断提示**：\n由于国内财经数据源网络极端拥堵，本次针对【{stock_code}】的抓取已超过 3 分钟未响应，系统已自动强制终止进程以保护服务器安全。请稍后重试。")
    except Exception as e:
        logging.error(f"执行管线发生未知异常: {e}")
        send_msg(chat_id, f"💥 **系统未知错误**：{str(e)}")
    finally:
        # 无论成功还是惨烈失败，最后必须无条件释放安全锁，确保下一次查询畅通
        process_lock.release()
        logging.info("安全锁已成功释放")

def poll_updates():
    """主循环：基于长轮询的 Telegram 消息监听器"""
    offset = 0
    logging.info("🚀 工业级动态交互股票机器人已在新加坡机房点火，开始监听全盘信号...")
    
    while True:
        try:
            # timeout=30 让连接保持长连接，降低请求频次，保护 CPU 不飙升
            response = requests.get(f"{BASE_URL}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
            if response.status_code != 200:
                logging.warning(f"Telegram 接口返回非200状态码: {response.status_code}，5秒后重试...")
                time.sleep(5)
                continue
                
            res = response.json()
            if not res.get("ok") or not res.get("result"):
                continue
                
            for update in res["result"]:
                offset = update["update_id"] + 1
                message = update.get("message")
                if not message or "text" not in message:
                    continue
                
                chat_id = message["chat"]["id"]
                raw_text = message["text"].strip()
                
                # 1. 基础路由过滤
                if raw_text in ["/start", "/help"]:
                    send_msg(chat_id, "🧠 **全功能动态股票智能量化助理已满血上线！**\n\n现在您可以随时向我发送任何 **A股、美股、港股** 的股票代码。\n\n💡 *输入示例*：\n- A股：`600863` 或 `002585`\n- 美股：`AAPL` 或 `TSLA`\n- 港股：`00700`\n\n接收代码后，我将动态为您清洗格式、强行拔出多源多维行情、透视实时新闻舆情，并调动大模型生成实盘级决策深度研报！")
                    continue
                
                # 2. 强力代码清洗
                stock_code = clean_stock_code(raw_text)
                if not stock_code:
                    # 如果不是标准的股票代码格式，直接静默忽略，不污染日志
                    continue
                
                send_msg(chat_id, f"🔍 **动态拦截成功**\n已收到代码：`{stock_code}`\n正在为您强行抓取实时行情并调用大模型进行矩阵计算……\n⏳ 整个过程大约需要 1 分钟，请静候。")
                
                # 3. 多线程异步解耦：把耗时的计算任务丢给子线程，主线程立刻返回继续监听TG，防止机器人“假死”
                t = threading.Thread(
                    target=execute_analysis_pipeline,
                    args=(chat_id, stock_code),
                    name=f"Task-{stock_code}"
                )
                t.start()
                
        except requests.exceptions.ConnectionError:
            logging.error("与 Telegram 服务器断开连接，正在尝试重新握手...")
            time.sleep(5)
        except Exception as e:
            logging.error(f"主监听循环遭遇未知异常: {e}")
            time.sleep(5)

if __name__ == "__main__":
    poll_updates()

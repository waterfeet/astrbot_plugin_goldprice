import requests
import asyncio
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

# --- 配置常量 (源自新脚本) ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.guojijinjia.com/'
}

DATA_API = "https://www.guojijinjia.com/d/gold.js?codes={}"

TARGETS = [
    # 黄金
    {"name": "伦敦金", "code": "hf_XAU", "type": "gold", "loc": "伦敦", "unit": "美元/盎司"},
    {"name": "纽约金", "code": "hf_GC", "type": "gold", "loc": "纽约", "unit": "美元/盎司"},
    {"name": "上海金", "code": "gds_AUTD", "type": "gold", "loc": "上海", "unit": "人民币/克"},
    # 白银
    {"name": "伦敦银", "code": "hf_XAG", "type": "silver", "loc": "伦敦", "unit": "美元/盎司"},
    {"name": "纽约银", "code": "hf_SI", "type": "silver", "loc": "纽约", "unit": "美元/盎司"},
    {"name": "上海银", "code": "gds_AGTD", "type": "silver", "loc": "上海", "unit": "人民币/千克"},
]

@register("gold_rate", "waterfeet", "多交易所金价查询插件", "2.0.2")
class GoldPricePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    def _fetch_data_map_sync(self, codes_list):
        """同步请求逻辑 (源自新脚本 fetch_data_map)"""
        url = DATA_API.format(",".join(codes_list))
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            text = resp.text
        except Exception as e:
            logger.error(f"接口请求失败: {e}")
            return {}

        data_map = {}
        # 解析数据
        statements = text.split(';')
        for stmt in statements:
            if 'var hq_str_' in stmt:
                parts = stmt.split('=')
                if len(parts) == 2:
                    key = parts[0].replace('var hq_str_', '').strip()
                    val_str = parts[1].strip('"').strip("'")
                    val_arr = val_str.split(',')
                    data_map[key] = val_arr
        return data_map

    def _format_beauty_string(self, item_config, data_arr):
        """格式化逻辑 (源自新脚本 format_beauty_string)"""
        if not data_arr or len(data_arr) < 9:
            return f"⚠️ {item_config['name']} 数据获取异常"

        try:
            # 提取基础数据
            curr = float(data_arr[0])
            high = float(data_arr[4])
            low = float(data_arr[5])
            prev_close = float(data_arr[7])
            open_price = float(data_arr[8])

            # 计算涨跌
            change = curr - prev_close
            change_pct = (change / prev_close) * 100 if prev_close != 0 else 0

            # 符号处理
            symbol = "+" if change > 0 else ""
            arrow = "↑" if change > 0 else ("↓" if change < 0 else "-")
            
            # 标题栏图标
            icon = "🟡" if item_config['type'] == 'gold' else "⚪"
            title_text = f"实时黄金行情" if item_config['type'] == 'gold' else f"实时白银行情"

            # 格式化输出模板
            output = (
                f"📊 **{title_text}** ({item_config['name']})\n"
                f"🏛️ 交易所：{item_config['loc']}\n"
                f"💰 当前价：`{curr:.2f}` {arrow} ({item_config['unit']})\n"
                f"📈 涨跌幅：{symbol}{change:.2f} ({symbol}{change_pct:.2f}%)\n"
                f"🌅 今开/昨收：{open_price:.2f} / {prev_close:.2f}\n"
                f"⬆️ 最高/最低：{high:.2f} / {low:.2f}\n"
            )
            return output
        except Exception as e:
            return f"❌ {item_config['name']} 解析错误: {e}"

    @filter.command("gold")
    async def gold(self, event: AstrMessageEvent):
        '''查询实时黄金/白银价格'''
        
        # 1. 准备代码列表
        code_list = [item['code'] for item in TARGETS]
        
        # 2. 在线程池中执行同步请求，避免阻塞 Bot
        loop = asyncio.get_running_loop()
        try:
            data_map = await loop.run_in_executor(None, self._fetch_data_map_sync, code_list)
        except Exception as e:
            return event.plain_result(f"数据请求发生错误: {e}")

        if not data_map:
            return event.plain_result("⚠️ 未能获取到行情数据，请稍后再试。")

        # 3. 格式化输出
        result_texts = []
        for item in TARGETS:
            raw_data = data_map.get(item['code'])
            beauty_str = self._format_beauty_string(item, raw_data)
            result_texts.append(beauty_str)
        
        # 4. 拼接并返回结果
        final_msg = "\n".join(result_texts)
        return event.plain_result(final_msg)
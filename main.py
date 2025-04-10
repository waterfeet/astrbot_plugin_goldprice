from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import requests
from threading import Timer

class GoldPriceFetcher:
    _api = "https://www.guojijinjia.com/d/gold.js"
    
    def __init__(self):
        self._timer = None
        self.data = {}  # 存储最新价格数据
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self._codes = ["gds_AUTD"]

    def init(self):
        self._load(initial=True)

    def _load(self, initial=False):
        try:
            url = self._api.replace("@CODE@", ",".join(self._codes))
            response = requests.get(url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                self._parse_js_data(response.text)
        except Exception as e:
            logger.error(f"获取数据失败: {str(e)}")
        
        # 保持5秒间隔更新
        self._timer = Timer(5.0, self._load)
        self._timer.start()

    def _parse_js_data(self, js_text):
        """解析JS数据并存入实例变量"""
        self.data.clear()
        for line in js_text.split(';'):
            line = line.strip()
            if line.startswith("var hq_str_"):
                var_part, value_part = line.split('=', 1)
                var_name = var_part.split()[1].strip()
                var_value = value_part.strip(" '\n\r")
                self.data[var_name] = var_value

    def get_price(self, code):
        """获取指定代码的格式化价格数据"""
        raw_data = self.data.get(f"hq_str_{code}", "")
        if not raw_data:
            return None
            
        data = raw_data.split(",")
        if len(data) < 9:
            return None

        try:
            # 数据清洗处理
            def clean(s): return s.strip(' "\'')
            
            price = float(clean(data[0]))
            last_close = float(clean(data[7]))
            change = price - last_close
            change_rate = (change / last_close) * 100

            return {
                "price": price,
                "change": change,
                "change_rate": change_rate,
                "open": float(clean(data[8])),
                "high": float(clean(data[4])),
                "low": float(clean(data[5])),
                "last_close": last_close
            }
        except (ValueError, IndexError) as e:
            logger.error(f"数据解析失败: {str(e)}")
            return None

    def stop(self):
        if self._timer:
            self._timer.cancel()

@register("gold_price", "GoldTracker", "实时黄金价格查询插件", "1.0.0")
class GoldPricePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.fetcher = GoldPriceFetcher()
        self.fetcher.init()

    @filter.command("gold")
    async def get_gold_price(self, event: AstrMessageEvent):
        '''查询实时黄金价格'''
        price_data = self.fetcher.get_price("gds_AUTD")
        
        if not price_data:
            yield event.plain_result("⚠️ 暂时无法获取黄金价格，请稍后再试")
            return

        # 生成涨跌符号
        change_symbol = "↑" if price_data["change"] > 0 else "↓" if price_data["change"] < 0 else "–"
        
        # 格式化输出
        output = [
            "🌟 实时黄金价格",
            f"当前价: {price_data['price']:.2f} {change_symbol}",
            f"涨跌幅: {price_data['change']:+.2f} ({price_data['change_rate']:.2f}%)",
            f"今　开: {price_data['open']:.2f}",
            f"昨　收: {price_data['last_close']:.2f}",
            f"最　高: {price_data['high']:.2f}",
            f"最　低: {price_data['low']:.2f}"
        ]
        
        yield event.plain_result("\n".join(output))

    async def terminate(self):
        '''插件卸载时停止数据更新'''
        self.fetcher.stop()
        logger.info("黄金价格插件已安全停止")
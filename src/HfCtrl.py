import requests
from astrbot.api import logger

class HfCtrl:

    def __init__(self):
        self.data = {}
        self._api = "https://www.guojijinjia.com/d/gold.js"
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

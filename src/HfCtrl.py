import asyncio
import json
from pathlib import Path
import httpx
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Set, Any
from astrbot.api import logger


class HfCtrl:
    _CACHE_TTL = 300  # 5分钟缓存
    _API_TEMPLATE = "https://www.guojijinjia.com/d/gold.js?codes={codes}"
    _CONFIG_PATH = Path("data/plugins/astrbot_plugin_goldprice/gold_rate_config.json")
    _CACHE_PREFIX = "data"

    def _load_config(self):
        """从配置文件加载交易所代码"""
        try:
            with open(self._CONFIG_PATH,"r", encoding="utf-8") as f:
                self.exchange_codes = json.load(f)
                logger.info(f"加载金价配置成功：{self.exchange_codes}")
        except Exception as e:
            logger.error(f"配置加载失败：{str(e)}")
            self.exchange_codes = {  # 默认配置
                "上海": "gds_AUTD",
                "纽约": "hf_GC", 
                "伦敦": "hf_XAU"
            }

    def __init__(self):
        self._load_config()  # 新增配置加载
        self.data: Dict[str, str] = {}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (...) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Encoding': 'gzip, br'  # 启用压缩[10](@ref)
        }
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.client: Optional[httpx.AsyncClient] = None
        self.transport = httpx.AsyncHTTPTransport(
            retries=3,
            http2=True,
            verify=False,
            limits=httpx.Limits(
                max_connections=200,
                max_keepalive_connections=50
            )
        )

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            transport=self.transport,
            timeout=httpx.Timeout(10.0, connect=5.0),
            http2=True,
            verify=False,
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_8; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50'}
        )
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    def _gen_cache_key(self, codes: Set[str]) -> str:
        return f"{self._CACHE_PREFIX}_{'_'.join(codes)}"

    async def _fetch_data(self, codes: Set[str], max_retries=3) -> str:
        cache_key = self._gen_cache_key(codes)
        
        # 缓存验证
        if cache_entry := self._cache.get(cache_key):
            if datetime.now() - cache_entry['timestamp'] < timedelta(seconds=self._CACHE_TTL):
                logger.debug(f"缓存命中: {cache_key}")
                return cache_entry['data']

        # 指数退避重试
        delay, attempt = 1, 0
        while attempt < max_retries:
            try:
                start = datetime.now()
                response = await self.client.get(
                    self._API_TEMPLATE.format(codes=",".join(codes))
                )
                response.raise_for_status()
                
                # 更新缓存

                temp = self._parse_js_data(response.text),
                self._cache[cache_key] = {
                    'data': temp,
                    'timestamp': datetime.now()
                }
                logger.debug(f"API耗时: {(datetime.now()-start).total_seconds():.2f}s")
                return temp
                
            except (httpx.HTTPStatusError, httpx.ConnectTimeout) as e:
                logger.warning(f"请求失败: {e.request.url} - {type(e).__name__}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
                attempt += 1

    async def get_price(self, code: str) -> Optional[Dict]:
        try:
            await self._fetch_data({code})
            raw_data = self.data.get(f"hq_str_{code}", "")
            if not raw_data:
                return None
                
            # 数据解析
            if raw_data:
                return self._process_price_data(raw_data)
            return None
        except Exception as e:
            logger.error(f"数据处理失败: {str(e)}")
            return None
        
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
        return self.data

    def _process_price_data(self, raw_data: str) -> Dict:
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

import asyncio
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from .src.HfCtrl import HfCtrl
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class GoldPriceCard:
    """金价信息卡片数据结构"""
    exchange: str  # 交易所名称[3](@ref)
    current_price: float
    price_change: float
    change_rate: float
    open_price: float
    last_close: float
    high: float
    low: float

    @property
    def change_symbol(self) -> str:
        return "↑" if self.price_change > 0 else "↓" if self.price_change < 0 else "–"

@register("gold_rate", "wheneverlethe", "多交易所金价查询插件", "2.0.0")


class GoldPricePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.ctrl = HfCtrl()  # 插件级唯一实例
        self._conn_lock = asyncio.Lock()
        self._is_connected = False
        self.supported_exchanges = ["上海", "纽约", "伦敦"]

    async def _ensure_connection(self):
        async with self._conn_lock:
            if not self._is_connected:
                await self.ctrl.__aenter__()  # 手动触发异步上下文
                self._is_connected = True
                logger.info("HfCtrl连接已建立")  # 网页6的日志监控特性


    @filter.command("gold")
    async def gold_check(self, event: AstrMessageEvent, exchange: str = None ):
        '''金价查询指令'''           
        try:
            await self._ensure_connection()
            # 参数校验与转换
            exchange = exchange or "上海"
            if exchange not in self.supported_exchanges:
                return event.plain_result(f"⚠️ 暂不支持{exchange}交易所，可选：{', '.join(self.supported_exchanges)}")

            code = self.ctrl.exchange_codes["exchange_mapping"][exchange]
            if not code:
                return event.plain_result("⚠️ 交易所配置异常，请联系管理员")

            price_data = await self.ctrl.get_price(code)
            return await self._format_response(event, exchange, price_data)
        
        except Exception as e:
            logger.error(f"查询异常：{str(e)}")
            return event.plain_result("🔧 服务暂时不可用，工程师正在抢修中")     
        
    

    async def _format_response(self, event: AstrMessageEvent, exchange: str, price_data: dict) -> MessageEventResult:
        """统一格式化响应"""
        card = GoldPriceCard(
        exchange=exchange,
        current_price=price_data["price"],
        price_change=price_data["change"],
        change_rate=price_data["change_rate"],
        open_price=price_data["open"],
        last_close=price_data["last_close"],
        high=price_data["high"],
        low=price_data["low"],
        )

       # 创建带日志校验的平台映射
        platform_mapping = {
            "qq": self._render_qq,
            "qq_channel": self._render_qq,
            "wecom": self._render_wecom  # 修正webchat为框架标准标识符wecom
        }

        # 获取平台标识符（根据框架实现可能需要event.platform.value）
        current_platform = event.platform.name.lower()  # 统一转小写 
        logger.debug(f"当前平台标识符：{current_platform}")

        # 带容错的选择渲染器
        renderer = platform_mapping.get(
            current_platform,
            self._render_default  # 默认使用通用渲染
        )

        # 立即执行异步渲染
        try:
            return await renderer(event, card)
        except KeyError as e:
            logger.error(f"渲染失败：{str(e)}")
            return event.plain_result("⚠️ 消息渲染异常，请联系管理员")

    async def terminate(self):
        """安全关闭资源"""
        if self.ctrl.client:
            await self.ctrl.client.aclose()
        logger.info("金价插件已安全停止")

    async def _render_qq(self, event: AstrMessageEvent, card: GoldPriceCard) -> MessageEventResult:
        """QQ/QQ频道富文本渲染（Markdown+图片）"""

        # 构建Markdown消息模板
        md_content = (
            "📊 **实时黄金行情**\n"
            f"🏛️ 交易所：{card.exchange}\n"
            f"💰 当前价：`{card.current_price:.2f}` {card.change_symbol}\n"
            f"📈 涨跌幅：{card.price_change:+.2f} ({card.change_rate:.2f}%)\n"
            f"🌅 今开/昨收：{card.open_price:.2f} / {card.last_close:.2f}\n"
            f"⬆️ 最高/最低：{card.high:.2f} / {card.low:.2f}\n"
        )
    
    # 返回复合消息（Markdown+图片）
        return event.composite_result(
        event.markdown_result(md_content),
        event.image_result(card.trend_chart) if card.trend_chart else None
    )

    async def _render_wecom(self, event: AstrMessageEvent, card: GoldPriceCard) -> MessageEventResult:
        """企业微信卡片消息（支持图文混合）"""
        # 生成趋势图缩略图
    
        # 构建企业微信卡片消息规范
        card_data = {
            "title": f"{card.exchange}黄金行情",
            "description": (
                f"🏛️ 交易所：{card.exchange}\n"
                f"💰 当前价：`{card.current_price:.2f}` {card.change_symbol}\n"
                f"📈 涨跌幅：{card.price_change:+.2f} ({card.change_rate:.2f}%)\n"
                f"🌅 今开/昨收：{card.open_price:.2f} / {card.last_close:.2f}\n"
                f"⬆️ 最高/最低：{card.high:.2f} / {card.low:.2f}\n"
            ),
            "url": "https://www.guojijinjia.com",  # 跳转链接
            "button": [{
                "text": "查看详情",
                "key": "view_detail"
            }]
        }
        return event.card_result(card_data)

    async def _render_default(self, event: AstrMessageEvent, card: GoldPriceCard) -> MessageEventResult:
        """通用文本渲染（适配不支持富文本的平台）"""
        text_content = (
                "📊 **实时黄金行情**\n"
                f"🏛️ 交易所：{card.exchange}\n"
                f"💰 当前价：`{card.current_price:.2f}` {card.change_symbol}\n"
                f"📈 涨跌幅：{card.price_change:+.2f} ({card.change_rate:.2f}%)\n"
                f"🌅 今开/昨收：{card.open_price:.2f} / {card.last_close:.2f}\n"
                f"⬆️ 最高/最低：{card.high:.2f} / {card.low:.2f}\n"
        )
        return event.plain_result(text_content)
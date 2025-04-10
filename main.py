from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from .src.HfCtrl import HfCtrl

@register("gold_rate", "wheneverlethe", "一个简单的金价查询插件", "1.0.0")
class GoldPricePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.gold = HfCtrl()
        self.gold.init()
    

    @filter.command("gold")
    async def gold_check(self, event: AstrMessageEvent):
        '''金价查询指令''' 
        self.gold.init()
        price_data = self.gold.get_price("gds_AUTD")
        if not price_data:
            yield event.plain_result("⚠️ 暂时无法获取黄金价格，请稍后再试")
        else:
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
        logger.info("黄金价格插件已安全停止")
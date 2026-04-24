"""Meta tools: natural-language search across all registered TWSE tools."""

import re
from typing import Optional

_CATALOG: dict[str, str] | None = None


async def _get_catalog(mcp) -> dict[str, str]:
    global _CATALOG
    if _CATALOG is None:
        tools = await mcp.get_tools()
        _CATALOG = {
            n: (t.description or "")
            for n, t in tools.items()
            if n != "search_twse_tools"
        }
    return _CATALOG


def _tokenize(text: str) -> list[str]:
    tokens = []
    for m in re.finditer(r'[a-zA-Z0-9]+', text):
        if len(m.group()) >= 2:
            tokens.append(m.group().lower())
    chinese = re.findall(r'[一-鿿]', text)
    tokens.extend(chinese)
    for i in range(len(chinese) - 1):
        tokens.append(chinese[i] + chinese[i + 1])
    return tokens


def _score(name: str, desc: str, query_tokens: list[str]) -> int:
    name_tokens = set(_tokenize(name))
    desc_tokens = set(_tokenize(desc))
    total = 0
    for term in query_tokens:
        if term in name_tokens:
            total += 8 * len(term)
        if term in desc_tokens:
            total += 3 * len(term)
    return total


def register_tools(mcp, client: Optional[object] = None) -> None:
    @mcp.tool()
    async def search_twse_tools(query: str, limit: int = 8) -> str:
        """用自然語言搜尋本 server 提供的 TWSE 工具。

        輸入關鍵字（中文或英文），回傳最相關的工具名稱與描述摘要。
        範例：「ETF基金」、「券商分公司」、「即時報價」、「法人買賣」、「融資融券」

        Args:
            query: 搜尋關鍵字，支援中英文混合
            limit: 最多回傳幾筆，預設 8
        """
        catalog = await _get_catalog(mcp)
        query_tokens = _tokenize(query)
        if not query_tokens:
            return "請輸入搜尋關鍵字。"

        scored = sorted(
            ((name, desc, _score(name, desc, query_tokens)) for name, desc in catalog.items()),
            key=lambda x: -x[2],
        )
        top = [(n, d) for n, d, s in scored[:limit] if s > 0]

        if not top:
            return f"找不到與「{query}」相關的工具。"

        lines = [f"### 搜尋結果：「{query}」\n"]
        for name, desc in top:
            short_desc = desc[:180] + ("…" if len(desc) > 180 else "")
            lines.append(f"**{name}**\n{short_desc}\n")

        return "\n".join(lines)

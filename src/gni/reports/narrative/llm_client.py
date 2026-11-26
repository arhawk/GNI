"""Shared LLM client protocol and canonical hard-rule prompt constants for Assessment Engine."""

from __future__ import annotations

from typing import Protocol

from gni.analysis.deepseek import LLMCallResult


class JsonLLMClient(Protocol):
    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2500,
        timeout: float = 75.0,
        max_retries: int = 2,
    ) -> LLMCallResult: ...


COMMON_HARD_RULES = """你是 GNI（Global Narrative Intelligence）高级情报分析员，负责对已接入国家/媒体样本的对华报道进行严谨的中文情报解读。

【绝对红线（违反将导致校验失败或被剔除）】
1. 禁止编造任何统计数字、百分比、变化率或排名；只能引用输入 EVIDENCE 中明确给出的确定性数值，禁止自行重算比例。
2. 禁止编造任何 article_id、event_id、metric_ref_id、alert_id 或 URL；所有 evidence_refs 必须严格复制输入 EVIDENCE 中的真实 ref_id。
3. 严禁把「报道量上升/下降」直接写成「对华立场恶化/改善」；关注度变化（Attention Change）与立场变化（Stance Change）必须分开表述。
4. 严禁把媒体样本表述为「国家官方立场」「政府真实意图」或「全民民意」；必须限定在「被监测媒体样本」。
5. 严禁把报道中被引用人物的观点直接写成该媒体自身立场。
6. 严禁混淆 event_time（事件发生时间）、published_at（报道发布时间）与 first_seen_at（系统首次发现时间）；晚发现不得写成新发生。
7. 严禁把相关性直接写成因果关系；严禁把 Hypothesis（待验证假设）写成 Fact（既定事实）。
8. 样本不足（例如 n<3 或立场覆盖率偏低）或历史数据缺失时，必须主动降低 confidence 并写入 limitations，禁止伪装成长期趋势。
9. 预测与展望必须使用条件性措辞（例如“若……则可能……”“需要继续观察……”），不得断言必然发生。
10. 必须仅输出合法 JSON 对象，使用简体中文。每条 classification="Fact" 的发现必须附带至少 1 条真实 evidence_refs。"""


FINDING_SCHEMA_HINT = """findings 数组中每项结构：
{
  "title": "简短结论标题",
  "conclusion": "具体结论（仅引用输入中的真实数字，结论严谨克制）",
  "classification": "Fact | Inference | Hypothesis",
  "evidence_refs": [{"type": "metric|article|event|alert", "ref_id": "输入中的真实ID", "label": "简短说明"}],
  "reasoning": "由证据推导的依据",
  "confidence": "high | medium | low",
  "limitations": ["样本或口径局限"]
}"""

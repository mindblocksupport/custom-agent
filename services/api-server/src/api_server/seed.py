"""Dev 模式自动 seed (v1.5):
- default workspace (Tenant > 隐式默认)
- 演示 skill: 通用助手 / 月报生成 (示例配方)

幂等: 已存在跳过.
"""

from __future__ import annotations

import logging

import psycopg

from api_server.db import skills as skill_db
from api_server.db import workspaces as ws_db
from api_server.db.api_keys import (
    DEFAULT_ACTOR_ID,
    DEFAULT_TENANT_ID,
)

logger = logging.getLogger(__name__)


def seed_default_workspace_and_skills() -> None:
    """dev 模式调用 (lifespan). 出错只 warn, 不挂."""
    try:
        existing = ws_db.list_for_tenant(tenant_id=DEFAULT_TENANT_ID)
        if existing:
            return  # 已 seed
        wid = ws_db.create(
            tenant_id=DEFAULT_TENANT_ID,
            name="default",
            actor_id=DEFAULT_ACTOR_ID,
            description="开发默认工作空间",
            default_model="auto",
            allowed_tools=[],  # 空 = 全部允许
            default_collection="default",
            allowed_collections=["default"],
            features={"rag": True},
        )
        logger.info("seeded default workspace: %s", wid)

        # 演示 skill 1: 通用助手
        skill_db.create(
            workspace_id=wid, tenant_id=DEFAULT_TENANT_ID,
            actor_id=DEFAULT_ACTOR_ID,
            name="通用助手",
            description="通用对话, 工具齐全",
            system_prompt=(
                "你是一个企业内部 Agent。"
                "回答时优先用 search_kb 工具查内部知识库；"
                "无相关内容时直接说『知识库无相关内容』，不编造。"
            ),
            allowed_tools=[],
            default_collections=["default"],
            starter_examples=["项目用什么 LLM", "怎么启动后端"],
            visibility="workspace",
            tags=["demo"],
        )

        # 演示 skill 2: 月报生成
        skill_db.create(
            workspace_id=wid, tenant_id=DEFAULT_TENANT_ID,
            actor_id=DEFAULT_ACTOR_ID,
            name="月报生成",
            description="基于业务文档生成结构化月报",
            system_prompt=(
                "你是一个数据分析助手. 用户会问业务月报相关问题. "
                "步骤: 1) 用 search_kb 找数据 2) 用 calculator 算关键指标 "
                "3) 输出结构化月报: 摘要 / 关键指标 / 风险提示 / 数据源引用. "
                "永不编造数字."
            ),
            allowed_tools=["search_kb", "calculator"],
            default_collections=["default"],
            starter_examples=[
                "上月营收增长率",
                "Q3 华东大客户违约率",
                "最近一周 P0 工单趋势",
            ],
            visibility="workspace",
            budget_per_call_usd=0.05,
            tags=["analyst", "demo"],
        )
        logger.info("seeded 2 demo skills under workspace %s", wid)
    except psycopg.errors.UndefinedTable:
        logger.warning(
            "workspaces/skills table missing — run infra/migrations/006 first"
        )
    except Exception as e:
        logger.warning("seed_default_workspace_and_skills failed: %s", e)

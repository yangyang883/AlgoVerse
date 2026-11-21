# 二十天分工指导

每位同学阅读自己的四份文件，分别对应 D1–D5、D6–D10、D11–D15、D16–D20。每天在对应 Issue 或 PR 留下提交、测试命令及结果；所有时间点按项目启动日计数。D1 工程骨架已提交，不等于 D3 模型闭环已通过。各文件的“完成”均以运行证据为准，不能用 Mock 冒充真实模型、算法或评测。

| 角色 | 周期 1 | 周期 2 | 周期 3 | 周期 4 |
|---|---|---|---|---|
| 1 AI/NLP | [D1–D5](member-1-ai/d01-d05.md) | [D6–D10](member-1-ai/d06-d10.md) | [D11–D15](member-1-ai/d11-d15.md) | [D16–D20](member-1-ai/d16-d20.md) |
| 2 算法 | [D1–D5](member-2-engine/d01-d05.md) | [D6–D10](member-2-engine/d06-d10.md) | [D11–D15](member-2-engine/d11-d15.md) | [D16–D20](member-2-engine/d16-d20.md) |
| 3 后端集成 | [D1–D5](member-3-backend/d01-d05.md) | [D6–D10](member-3-backend/d06-d10.md) | [D11–D15](member-3-backend/d11-d15.md) | [D16–D20](member-3-backend/d16-d20.md) |
| 4 前端 | [D1–D5](member-4-frontend/d01-d05.md) | [D6–D10](member-4-frontend/d06-d10.md) | [D11–D15](member-4-frontend/d11-d15.md) | [D16–D20](member-4-frontend/d16-d20.md) |
| 5 评测交付 | [D1–D5](member-5-evaluation/d01-d05.md) | [D6–D10](member-5-evaluation/d06-d10.md) | [D11–D15](member-5-evaluation/d11-d15.md) | [D16–D20](member-5-evaluation/d16-d20.md) |

## 全组固定节奏

- 每天：各人上午公布阻塞和当天交付，下午提交可运行的小 PR；组员 3 核对契约与主线，组员 5 留存可复现记录。跨模块变更先在同一 Issue 写明请求/响应样例。
- D3：真实 Qwen 自然语言→配置→校验→冒泡真实执行→JSON 的链路必须复演。缺模型凭据时记录未通过，手动配置仅作离线预案。
- D7：四排序、RAG 来源、多轮修订、一个 SVG 播放器完成集成测试；未过则禁止 P1。
- D12：工具编排、反例、同输入对比、报告预览的 P0 功能冻结。D13 起只修缺陷和做评测。
- D16：冻结测试集、基线和一项消融有原始结果、版本、失败分类。D20：在答辩目标机器复演固定脚本。
- 任一闸门未过：先修最短 P0 链路，取消 P1 和装饰性增强；不把 P2 列入本期。20 天无法靠文档保证，闸门和失败预案用于尽早暴露交付风险。

通用验收：`cd backend; python -m pytest -q`，仓库根目录 `python scripts/export_contracts.py --check`，`cd frontend; npm install; npm run build`。当前 Windows 沙箱曾使 HTTP 测试跳过；必须在正常开发机或 CI 上补跑，不得把跳过记成通过。前端尚无 lockfile，首个可联网开发环境应生成并提交 `package-lock.json`，CI 改回 `npm ci`。

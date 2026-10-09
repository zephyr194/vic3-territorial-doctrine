# 国家领土原则 · Territorial Doctrine

《维多利亚3》**1.13** 目标版本的领土立法模组，当前为 `0.2.0-alpha.1`。基于已定稿 v0.2 设计，从“西班牙—阿尔里夫”固定目标场景开始实现。

已有四条原生法律，以及北非重点区域、宣称法案、正式接纳法案、建设承诺和行政整合脚本。国内立法只产生宣称，外交与取得土地沿用原版；一年整合保留居民的文化和宗教。

**当前验证为离线验证。尚未在 Vic3 1.13 本体中加载或游玩，不能据此认定引擎兼容或平衡已通过。**

开发只需 Python 3.10+，无第三方包：

```bash
python3 tools/generate.py --check
python3 -m unittest discover -s tests -v
python3 tools/validate.py
python3 tools/scenario.py
python3 tools/package.py
```

安装包输出到 `dist/territorial_doctrine-0.2.0-alpha.1.zip`。见 [安装说明](docs/INSTALL.md) 与 [游戏内验收](docs/TESTING.md)。

| 内容 | 当前实现 |
|---|---|
| 四条法律、八集团基础倾向、5年改法锁定 | 原生脚本；沿用原版改法流程 |
| 重点区域、资源预留与等待 | 西班牙的一个北非区域；其余区域选择未开放 |
| 宣称、接纳、90天轮次、3成/3败、2年冷却 | 阿尔里夫固定目标脚本 |
| 目标相关支持 | 海峡安全、接纳、战争、两项承诺、既往违约 |
| 承诺履约 | 海军基地与铁路，首次完整取得主权时登记基线，3年期限 |
| 整合 | 常规原版路线；12个合格月快轨；6个连续不合格月回退 |
| 历史登记、资源短缺与同胞人口宣称 | 离线规则模型；尚未接入通用游戏目标选择 |
| 列强介入风险、领袖个别修正、多国多州、自治/殖民、扩张AI | 尚未实现 |

详细规则与取舍见 [设计与实现状态](docs/DESIGN.md)。

`mod/` 是实际游戏载荷。法律、意识形态、基础分、常量、修正、法律文本、图标和元数据由 `tools/generate.py` 从 `territorial_doctrine/rules.json` 生成，其余脚本直接维护。改数值后运行生成器，再运行检查；不要只修改生成文件。

云任务已隔离，直接使用现有 `/workspace/vic3-territorial-doctrine` checkout，不需要另建 worktree。云端开发不需要 Steam 凭据或下载游戏。游戏本体用于本地引擎验收。

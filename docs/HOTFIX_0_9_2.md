# 0.9.2-alpha.1：1.13脚本语法与标识修复

根据用户补充的引擎报错修复六类错误，并恢复原生脚本的UTF-8 BOM。0.9.1的离线解析和夹具没有识别这些问题；本版增加针对性校验，不以离线通过代替实机验收。

## 修复

1. 在生成源`tools/civic_assets.py`和输出`events/td_civic_events.txt`的文件首部声明`namespace = td`。事件按文件注册，另一个文件中的namespace不能替代它。
2. `td_can_designate_focus_trigger`中的三处条件改用`trigger_if`。数值公式和效果中的合法`if`保持原义。
3. 建筑等级全部改为`state_has_building_type_levels = { target = bt:building_… value > … }`块式判断，不再作为数值链接读取。签约拥有州或首次取得外国目标州时，先以倍增方式确定等级范围，再用二分探测缓存准确基线；检查次数随等级对数增长，超过1000级也不会耗尽默认1000次循环上限。月度履约只判断绑定州是否严格超过原基线，不刷新基线或期限。
4. 三处破产判断使用`declared_bankruptcy`。
5. 阻止州整合的两项修正使用`state_disallow_incorporation_bool = yes`。
6. 政策分类使用`law_census_voting`。

原先缺失BOM的12个文件已恢复。生成器现在统一维护全部原生`.txt`脚本的BOM；重新生成不会把这些文件变回无BOM编码。除编码外，手工脚本的内容继续直接维护。

生成源、输出载荷、数据库校验所需标识和测试夹具同步更新，避免重新生成或测试继续沿用错误名称。测试夹具已删除虚构的建筑数值链接，明确支持块式等级判断和`trigger_if`，并在触发器中遇到效果式`if`时拒绝执行。

## 检查

新增11项回归覆盖：账目决议实际到达`td.40`、文件内namespace、条件触发器的各原则门槛、破产阻止立法和税档操作、人口普查投票分类、两类建筑从0到200万级的准确快照、循环次数、目标隔离、严格净增长、失效目标、BOM及再生成。已有合同回归继续覆盖签约和取得基线、拆建、失地复得、预算、期限及旧窗口。

验证器会拒绝：缺少BOM的原生脚本、事件文件缺本地namespace、触发器内的效果式条件、建筑等级数值/多冒号链接、错误块式参数，以及本次报告中的旧标识。回归测试会故意重新引入这些错误，确认它们确实被检出。

```bash
python3 tools/generate.py --check
python3 -m unittest discover -s tests -v
python3 tools/validate.py
python3 tools/scenario.py
python3 tools/package.py
```

建筑块式判断和`while`语法对照了社区[cwtools触发器](https://github.com/cwtools/cwtools-vic3-config/blob/master/config/triggers.cwt)与[效果](https://github.com/cwtools/cwtools-vic3-config/blob/master/config/effects.cwt)。仍未提供1.13游戏本体，完整引擎作用域、实际事件打开、真实存档和崩溃情况需实机确认。

## 附带警告

`td.24`、`td.26`和`td.27`为兼容旧调用保留，标记`orphan = yes`说明它们有意不接入现行回调；未恢复旧战争惩罚。`td.40`已有账目决议调用，修复文件namespace后可按正常事件解析。

未因“变量已设置但未使用”警告批量删除存档字段、缓存或兼容接口。报告中的`ai_can_use`、`MISSING_DLC_ENTRY`和`Unlocalized text`未在模组载荷中找到相应来源，未改动原版或启动器文件。

## 更新与验收

退出游戏，获取本版源码后执行`vtd.cmd update`（Windows）或`python3 vtd.py update`，再重启启动器。安装器会备份旧载荷；使用新测试档或旧档副本，仅加载一份VTD。

1. 启用任一独立核算模块，执行账目决议，确认能打开`td.40`。
2. 检查新的错误日志，不再出现本次六类解析错误；区分旧轮转日志。
3. 分别在已有海军基地/铁路和没有该建筑的州签约，确认已有等级不被误算为履约；绑定州净新增一级才兑现，其他州建设无效。
4. 检查外国合同取得时绑定实际州、保存并重载后基线/付款/期限不变，失地复得不重置。
5. 在破产、三种领土原则的行政/权威门槛，以及人口普查投票法下复核对应资格与分类。

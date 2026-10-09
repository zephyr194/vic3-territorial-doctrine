# 安装 alpha 测试版（目标 Vic3 1.13）

尚未在游戏内验收。请使用独立测试存档与仅包含本模组的测试播放集。

## ZIP 安装

解压 `territorial_doctrine-0.2.0-alpha.1.zip`，将 `territorial_doctrine/` 和 `territorial_doctrine.mod` 放进用户数据目录下的 `Victoria 3/mod/`。不是 Steam 的游戏安装目录。常见位置：

- Windows：`文档/Paradox Interactive/Victoria 3/mod/`（文档可能由 OneDrive 重定向）。
- Linux：`~/.local/share/Paradox Interactive/Victoria 3/mod/`。
- macOS：`~/Documents/Paradox Interactive/Victoria 3/mod/`。

在 Paradox 启动器添加本地模组并加入播放集。若启动器不接受 ZIP 中的相对路径，使用启动器“创建模组”生成本地路径记录，再将载荷目录内容复制进去，或采用下方安装脚本写入绝对路径。

## 从源码安装

本地安装 Python 3.10+，在仓库根目录运行：

```bash
python tools/package.py --install-dir "/你的用户数据路径/Paradox Interactive/Victoria 3/mod"
```

该命令只创建本模组目录和对应 `.mod` 文件。若同名安装已存在会拒绝覆盖，请自行备份并移走旧版本后再装。它不会登录 Steam、下载游戏或改变原版游戏文件。

加载前，可对本机1.13数据库做标识检查（路径末尾是 `game`）：

```bash
python tools/validate.py --game-dir "/你的Steam游戏路径/Victoria 3/game"
```

这只核对用到的数据库名称。引擎作用域和运行行为还需要按 TESTING.md 验收。不要把只运行上述工具当作已通过游戏兼容测试。

## 首次玩法

1. 开新档，选择西班牙。国家领土原则初始为领土现状主义。
2. 通过原版立法流程改为战略边疆主义或帝国扩张主义。
3. 对北非建立原版区域利益；通过决议指定北非重点区域并等待6或12个月。
4. 提出阿尔里夫宣称法案，可通过决议查看支持率和提供最多两项建设承诺。
5. 宣称通过后，使用原版外交取得整个阿尔里夫州区域的主权。
6. 推动正式接纳法案，再选择常规或满足条件后的一年整合。常规路线仍需在州界面启动整合。

西班牙开局部分拥有该州不能跳过取得完整主权的步骤。历史权利主义不授予该州虚构历史权利。

D0：环境完成
现象：VS Code WSL 扩展通过命令行安装时出现 BAD_DECRYPT。
假设与验证：怀疑命令行下载或代理影响，改用 VS Code 扩展页面安装。
真实原因：命令行扩展安装流程异常，Ubuntu 网络正常。
修复与收获：从 VS Code 图形界面成功安装 WSL 扩展；遇到错误要先区分 Windows 与 WSL 环境。
明日前三件事：进入项目；激活 .venv；开始 D1。
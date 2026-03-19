# Git 工作流程和提交规范

## 工作流程

### 分支模式
- **main**: 主分支，用于正式发布版本
- **develop**: 开发分支，集成新特性
- **feature/***: 特性分支，开发新功能
  - 命名：`feature/[功能名称]`
  - 例：`feature/add-skill-framework`
- **fix/***: 修复分支，修复 bug
  - 命名：`fix/[bug编号]-[bug名称]`
  - 例：`fix/001-agent-parsing-error`
- **docs/***: 文档分支，更新项目文档
  - 命名：`docs/[文档名称]`
  - 例：`docs/api-reference`

### 工作流程步骤
1. 从 `develop` 分支创建新分支
2. 在分支上进行开发和提交
3. 定期同步上游 `develop` 分支的最新内容
4. 完成开发后创建 Pull Request
5. 代码审查通过后合并到 `develop` 分支
6. 定期从 `develop` 合并到 `main` 进行发布

## 提交信息规范

### 格式
```
<type>(<scope>): <subject>

<body>

<footer>
```

### 类型 (type)
- **feat**: 新增功能
- **fix**: 修复 bug
- **docs**: 文档变更
- **style**: 代码风格变更（不影响功能）
- **refactor**: 代码重构
- **perf**: 性能优化
- **test**: 测试相关
- **chore**: 构建、依赖、工具变更
- **ci**: CI/CD 相关

### 作用域 (scope)
- `agent`: Agent 核心
- `skill`: Skill 框架
- `llm`: LLM 集成
- `webui`: Web UI 前端
- `backend`: 后端基础设施
- `api`: API 接口
- `db`: 数据库
- `project-facts`: 项目事实信息系统
- `conversation`: 对话管理
- `docs`: 文档
- `infra`: 基础设施部署

### 主题 (subject)
- 使用祈使句，第一个字母小写
- 不超过 50 个字符
- 用英文或中文，保持一致

### 主体 (body)
- 说明为什么做这个变更（不是做了什么）
- 每行不超过 72 个字符
- 用中文或英文，保持一致

### 页脚 (footer)
- 引用相关的 issue：`Closes #123`, `Related to #456`
- 用中文或英文，保持一致

### 示例
```
feat(skill): 实现 Skill 自动发现机制

- 扫描 skills/ 目录下的所有 Skill
- 验证 skill.md 中的必需字段
- 自动加载和注册 Skill 到管理器

Closes #456
```

## 代码审查标准

### 必须检查的内容
1. 代码逻辑正确性
2. 测试覆盖率（新代码应有相应测试）
3. 文档完整性
4. 代码风格和规范
5. 性能影响
6. 安全性考虑

### 审查意见格式
- **建议**: 使用 `建议:` 前缀
- **必须**: 使用 `必须:` 前缀
- **问题**: 使用 `问题:` 前缀

## 版本管理

### 语义版本号格式
`vX.Y.Z`

- **X（主版本）**: 不兼容的 API 变更
- **Y（次版本）**: 向下兼容的功能增加
- **Z（修订号）**: 向下兼容的 bug 修复

### 发布流程
1. 在 `develop` 分支更新版本号
2. 更新 CHANGELOG
3. 创建版本 tag：`git tag vX.Y.Z`
4. 合并到 `main` 分支
5. 推送到远程仓库

## 开发环境配置

### 必需工具
- Python 3.11+
- Node.js 18+
- Git
- Docker（用于本地开发和测试）

### 本地开发环境搭建
```bash
# 克隆仓库
git clone <repository-url>
cd nextagent-doc-assistant

# 创建 Python 虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..

# 初始化配置
cp .env.example .env
# 编辑 .env 文件进行本地配置
```

## 常用命令

```bash
# 创建新特性分支
git checkout -b feature/[功能名称]

# 查看当前分支
git branch -a

# 提交代码
git commit -m "type(scope): subject"

# 推送到远程
git push origin feature/[功能名称]

# 创建 Pull Request
# 在 GitHub/GitLab Web UI 上创建 PR

# 更新分支
git pull origin develop

# 删除本地分支
git branch -d feature/[功能名称]

# 删除远程分支
git push origin --delete feature/[功能名称]
```

## 参考资源

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/)
- [Semantic Versioning](https://semver.org/)

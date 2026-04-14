# Custom Node Resolution

自定义节点解析顺序：

1. 本地字典精确匹配
2. 命名规则匹配
3. ComfyUI Registry 在线查询
4. 仍未命中时标记为 `unresolved`

输出字段约定：

| 字段 | 说明 |
| --- | --- |
| `node_name` | 工作流里的节点类型名 |
| `repo_url` | 推荐仓库地址 |
| `install_spec` | `registry:<name>` 或 `git:<repo-url>` |
| `version_hint` | 分支、tag、commit，占位即可 |
| `extra_dependencies` | 额外 Python 或系统依赖，占位即可 |
| `confidence` | `high` / `medium` / `low` / `none` |
| `verification_required` | 是否必须人工核对 |
| `resolution_source` | `local_map` / `pattern` / `registry` / `unresolved` |

生成 `custom-nodes.txt` 时的默认规则：

- 只有在能明确识别 registry 名称时，才写 `registry:<name>`
- 其余已识别仓库统一写 `git:<repo-url>`
- 未识别项不要静默丢弃，要写成注释 TODO，方便人工补全

# RunPod Serverless 傻瓜式 SOP

这份 SOP 是给你自己和 AI 用的。

目标很简单：

拿到客户工作流后，按固定顺序推进，一直到交付成功。

---

## 一、先搞清楚客户给了什么

客户一般会给你这些东西里的几样：

- ComfyUI 工作流
- 参考效果图或视频
- 输入样例
- 模型链接
- 自定义节点信息
- 希望怎么部署

你第一步不要急着部署。

先确认下面几个问题：

1. 工作流是不是 `Workflow > Export (API)` 导出的 JSON
2. 客户要的最终效果是什么
3. 客户是要图片还是视频
4. 客户以后要不要自己维护代码
5. 客户更想用 GitHub 还是 Docker
6. 有没有必须用的模型和节点

如果这些信息不清楚，先补齐。

建议先填：

- `templates/serverless-project/00_project-intake.md`
- `templates/serverless-project/AI_TASK_BRIEF.md`

---

## 二、先在本地把工作流跑通

这一步最重要。

不要一上来就去 RunPod。

正确顺序是：

1. 拿到客户工作流
2. 在本地 ComfyUI 或模板环境里跑
3. 看看有没有报错
4. 看看效果对不对
5. 和客户参考结果对比

你要确认三件事：

- 能不能跑通
- 跑出来的效果对不对
- 需要哪些模型和节点

如果本地都跑不通，后面部署只会更乱。

---

## 三、整理依赖清单

本地跑通后，马上做两张表。

### 1. 模型清单

至少整理这些：

- 模型文件名
- 下载链接
- 模型类型
- 应该放在哪个目录
- 哪些是必须的

写到：

- `project-config/model-manifest.txt`
- `templates/serverless-project/02_dependencies.md`

### 2. 自定义节点清单

至少整理这些：

- 节点名称
- 仓库地址
- 分支或版本
- 有没有额外依赖

写到：

- `project-config/custom-nodes.txt`
- `templates/serverless-project/02_dependencies.md`

这一步做好了，后面就顺了。

---

## 四、决定哪些东西放镜像，哪些东西放 Volume

默认建议这样做：

- 自定义节点放镜像
- 模型放 Network Volume

原因很简单：

- 镜像更小
- 构建更快
- 模型更新不需要重新构建镜像
- 后续维护更轻松

一般不要把大模型直接写死在 Dockerfile 里。

---

## 五、改项目配置

接下来开始改模板项目。

你通常只需要优先看这几个地方：

- `project-config/custom-nodes.txt`
- `project-config/model-manifest.txt`
- `Dockerfile`
- `handler.py`
- `src/start.sh`
- `.runpod/hub.json`

### 正常情况下怎么改

#### `custom-nodes.txt`

把客户项目需要的自定义节点填进去。

#### `model-manifest.txt`

把客户项目需要的模型下载链接填进去。

#### `Dockerfile`

一般不用大改。

只有遇到这些情况才改：

- 需要额外系统依赖
- 某些节点需要额外 Python 包
- 构建流程需要特殊处理

#### `handler.py`

一般也不用大改。

只有客户接口格式特别特殊时再改。

比如：

- 输入结构要兼容客户现有系统
- 输出格式需要特殊整理
- 要增加额外预处理或后处理

---

## 六、准备模型到 Network Volume

模型不要临时等到 Endpoint 运行时再下载。

正确做法是：

1. 在 RunPod 创建 Network Volume
2. 保证 Region 一致
3. 用临时 Pod 挂载这个 Volume
4. 运行模型下载脚本

命令示例：

```bash
bash scripts/download-models-to-volume.sh /runpod-volume project-config/model-manifest.txt
```

下载完后检查：

- 目录对不对
- 文件名对不对
- 工作流引用名对不对

如果模型名和工作流里的名字不一致，后面一定报错。

---

## 七、构建镜像并本地测试

先本地构建：

```powershell
docker build --platform linux/amd64 -t runpod-serverless-template:local .
```

再本地启动：

```powershell
docker-compose up
```

然后打开：

- [http://localhost:8000/docs](http://localhost:8000/docs)
- [http://localhost:8188](http://localhost:8188)

接着测：

1. `/health`
2. `/runsync`
3. 工作流是否能正常执行
4. 输出格式是否正确

如果这里还有缺节点、缺模型、路径错、环境变量缺失，就继续修。

不要跳过这一步。

---

## 八、决定最终部署方式

你一般有两种选择。

### 方案 A：GitHub

适合：

- 客户后续要自己维护
- 客户想保留源码
- 后续还会经常改

### 方案 B：Docker

适合：

- 你想交付一个更固定的版本
- 客户不一定会改代码
- 更看重稳定交付

大多数你说的实际业务里，客户更偏 GitHub，这就优先走 GitHub。

---

## 九、在 RunPod 创建 Serverless Endpoint

这一步主要就是按配置填。

重点确认：

- 镜像地址
- GPU
- Container Disk
- Active Workers
- Max Workers
- Idle Timeout
- Flash Boot
- Network Volume
- 环境变量

最常见漏项：

- 没挂 Network Volume
- Region 不一致
- 环境变量忘了填
- Container Disk 太小

---

## 十、用 Postman 做正式测试

你自己也说了，习惯用 Postman，这很对。

建议固定这样测：

1. 测 `/health`
2. 测 `/runsync`
3. 测 `/run`
4. 测 `/status`

至少保留三组样例：

- 最小测试样例
- 标准业务样例
- 边界样例

你要检查：

- 返回有没有报错
- 输出结果是不是客户要的
- 节点和模型是否都加载成功
- 同一请求多测几次是否稳定

测试记录写到：

- `templates/serverless-project/04_test-and-delivery.md`

---

## 十一、排错

如果测试失败，优先按这个顺序排：

1. 缺模型
2. 缺节点
3. 模型路径不对
4. 工作流不是 API 导出格式
5. 环境变量缺失
6. 输入图片下载失败
7. GPU 或显存不够

不要一上来就怀疑 `handler.py`。

大多数问题都出在依赖和路径。

---

## 十二、交付给客户

交付时，至少给客户这些东西：

1. Endpoint 地址
2. 调用方式
3. Postman 示例
4. 输入 JSON 示例
5. 输出 JSON 示例
6. 必要环境变量说明
7. 如果是 GitHub 部署，把仓库地址也给客户

如果客户要自己维护，还要说明：

- 哪些文件最常改
- 模型以后怎么更新
- 节点以后怎么加

---

## 十三、交付完成标准

满足下面这些，就可以算交付完成：

- 工作流本地已跑通
- RunPod Endpoint 已成功部署
- Postman 测试通过
- 客户能调用成功
- 客户确认结果没问题

---

## 十四、你以后固定照着做就行

以后每来一个新项目，固定按这个顺序：

1. 收集客户资料
2. 本地跑通
3. 整理模型和节点
4. 改配置
5. 下载模型到 Volume
6. 本地测试
7. 部署 RunPod
8. Postman 测试
9. 客户验收

不要倒着做。

---

## 十五、配套文件

建议配合这些文件一起用：

- [README.md](./README.md)
- [QUICK_START.md](./QUICK_START.md)
- [项目配置说明](./project-config/README.md)
- [脚本说明](./scripts/README.md)
- [标准项目模板](./templates/serverless-project/README.md)

# Model Path Mapping

本 skill 生成 `project-config/model-manifest.txt` 时，默认按下列规则写 `relative_path`：

| 模型类型 | 默认路径规则 |
| --- | --- |
| `checkpoint` | `checkpoints/<family>` |
| `lora` | `loras/<family>` |
| `vae` | `vae` |
| `controlnet` | `controlnet` |
| `clip_vision` | `clip_vision` |
| `upscale_model` | `upscale_models` |
| `unet` | `unet` |
| `clip` | `clip` |
| `other` | `misc/TODO-family` |

`<family>` 的默认推断规则：

- 文件名包含 `flux` -> `FLUX`
- 文件名包含 `sdxl`、`xl` -> `SDXL`
- 文件名包含 `pony` -> `Pony`
- 文件名包含 `sd15`、`1.5`、`v15` -> `SD15`
- 文件名包含 `wan` -> `WAN`
- 无法确定时 -> `TODO-family`

注意：

- 这是 RunPod 草稿路径，不代表最终一定正确。
- 无法确定 family 时，宁可写 `TODO-family`，不要伪造确定值。

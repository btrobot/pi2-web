# Test Spec — req1 BS bilingual implementation

## Test dimensions
1. 模式合同正确性
2. API 行为正确性
3. 历史/录音 FIFO 正确性
4. 单壳 UI 结构正确性
5. 双语切换正确性
6. 导出/删除正确性
7. 3 分钟录音限制正确性

## Automated tests
### tests/test_api.py
- bootstrap 返回完整模式与 i18n 注册表
- 文本输入接口覆盖：`tts_zh_zh`, `tts_en_en`, `mt_tts_zh_en`, `mt_tts_en_zh`, `mt_zh_en`, `mt_en_zh`
- 语音输入接口覆盖：`asr_zh_zh`, `asr_en_en`, `asr_mt_zh_en`, `asr_mt_en_zh`, `asr_mt_tts_zh_en`, `asr_mt_tts_en_zh`
- recent history 最多 3 条
- full history 最多 5 组
- recordings 最多 5 条
- delete history / delete recording
- history export / recordings export ZIP 结构
- speech upload 超时/缺失/非法 mode 校验

### tests/test_pipeline.py
- 纯操作拆分后的 transcribe / translate / synthesize 单测
- 12 个 mode_key 到 pipeline chain 的映射测试
- speech-to-speech 返回 text + audio 工件
- text-to-text 不应生成音频
- same-language speech-to-text 不应生成翻译文本

### tests/test_storage.py
- history manifest 创建与读取
- 不同模式的 optional artifact 组合正确
- history FIFO 淘汰目录正确
- recording FIFO 淘汰文件正确
- export ZIP 包含 manifest 与工件
- delete 删除完整记录组

### UI render/integration tests
- `GET /` 渲染 header/sidebar/breadcrumb/footer
- recent history panel 存在
- history route/view 存在
- CN/EN 标签切换正确
- 帮助与用户设置入口存在

## Manual walkthrough
### CN UI
- 跑完 12 个叶子模式各 1 次
- 跑独立录音 1 次
- 检查 recent history / full history / delete / export

### EN UI
- 重复上述流程

> Headless OMX lane note: when no interactive browser screenshot lane is available,
> the walkthrough may be closed by an assertion-backed acceptance ledger stored in
> `.omx/plans/acceptance-evidence-req1-bs-bilingual-ui.md`, as long as the artifact
> explicitly distinguishes deterministic verification from human click/screenshot proof.

## Acceptance evidence
- 每个 mode_key 一条通过记录
- 历史与录音各自 FIFO 证明
- 双语截图或断言结果
- ZIP 导出结构证明
- 归档到 `.omx/plans/acceptance-evidence-req1-bs-bilingual-ui.md`

## Additional contract checks
- `POST /api/conversions/speech` 必须支持 `recording_id` 复用流。
- `GET /api/history/recent` / `GET /api/history` / `GET /api/recordings` DTO 形状固定并有断言。
- 两个 DELETE 接口统一返回 `{ ok, deleted_kind, deleted_id }`。

## Legacy-path checks
- `main.py` 默认进入 server mode；`--cli` 仍可进入最小调试路径。
- `tests/test_system.py` 不再断言旧 numeric mode API。

## Recording reuse UI checks
- 点击“用于转换”必须弹出 speech mode picker。
- picker 只包含 6 个 speech-input 叶子模式。
- 选中后页面预填 `recording_id`，但不会自动提交，需用户显式点击开始转换。

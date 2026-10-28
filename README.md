# zcode-android-build

在 GitHub Actions 上编译 [zai-org/ZCode](https://github.com/zai-org/ZCode) 官方 Android 壳，不需要本地 Android SDK。

## 为什么是这种方式

不 fork 官方仓库（那是整个桌面端 + CLI + 服务端的 monorepo）。CI 里用 `actions/checkout` 的稀疏检出只拉 `packages/android` 一个目录，编译完上传 APK。上游更新后重跑一次就是最新版，本地不需要同步任何代码。

这个仓库本身**不含任何源码**，只有 workflow、本文件和 `patches/` 下的小补丁。

## 用法

1. Actions → **Build ZCode Android APK** → **Run workflow**
2. `upstream_ref` 留 `main` 就是官方最新；要固定版本就填提交号或 tag
3. 跑完从 [Releases](https://github.com/jianzhangg/zcode-android-build/releases) 下 `latest` 里的 APK

## 为什么别从 Artifacts 下载

Actions 的 artifact 下载会被 302 到 `*.blob.core.windows.net`（实测落在南非的 `productionresultssa19`），这条路既不在常见代理规则的 `github.com` / `githubusercontent.com` 里，也没有国内 CDN，几十 KB/s 或者直接 TLS 超时都正常。

所以 workflow 跑完会额外发一个 rolling Release（tag 固定 `latest`，每跑一次删旧建新，URL 不变）：

```bash
curl -L -O https://github.com/jianzhangg/zcode-android-build/releases/download/latest/zcode-android-<sha8>-patched.apk
```

Release 附件走 `objects.githubusercontent.com`，代理能覆盖，也套得上加速前缀（例如 `https://ghfast.top/` 拼在原 URL 前面）。文件名里的 sha8 是上游提交号，每次可能变，先看 Release 页确认。

## 产出说明

- 应用包名 `com.example.zcode_mobile`，App 名称 `ZCode`，与官方桌面端区分开
- **release 变体**：无 `debuggable`，不放行明文流量；入口链接仍只接受 `https://zcode.z.ai/remote…`（`RemoteControlUrlPolicy` 拦在扫码/粘贴/deep link 这一步），进壳之后的导航不再卡域名，否则登录走不通（见下节）
- 官方 `build.gradle.kts` 没有 signingConfig，直接 `assembleRelease` 只会得到 unsigned 包。workflow 里用 `zipalign` + `apksigner` 补签名，密钥来自仓库 secret
- 签名证书固定，所以后续版本可以覆盖安装
- 功能范围：扫码 / 粘贴链接 / deep link 三种入口，最近 5 条链接，WebView 承载官方远控页，前台服务保活 + 屏幕常亮。**没有**任务通知、应用锁、多机管理

## 为什么要打补丁

官方壳的 WebView 导航策略把「主框架跳到非 `https://zcode.z.ai/remote` 前缀」的请求全部交给外部浏览器。而远控页的登录恰恰是往别的域名跳：

| 环节 | 事实 |
| --- | --- |
| 登录入口 | `packages/web/src/auth/webAuthService.ts:63` → `window.location.assign(authorizeUrl)`，顶层跳转，不是弹窗 |
| Z.ai 侧 | `webZaiOAuthConfig.ts:30` → `https://chat.z.ai/api/oauth/authorize` |
| BigModel 侧 | `webZaiOAuthConfig.ts:41` → `<bigmodel origin>/login` |
| 回调 | `webRemoteControlEntry.ts:17-27` 的 `isWebRemoteControlOAuthCallback`：落回 `/remote/v4` 并带 `state` + `code`/`authCode` |

于是点「登录」→ 跳到 `chat.z.ai`（不在白名单）→ 被 `openExternalUrl` 甩到系统浏览器 → 登录态留在浏览器进程，WebView 里永远未登录。这就是「打包过但一直登录不成功」的原因。

`patches/0001-keep-oauth-login-inside-webview.patch` 做三件事：

1. `shouldOverrideUrlLoading` 里，除 `zcode://` 深链外的 `http(s)` 主框架导航一律留在 WebView（`return false`），只把非 http(s) 的 scheme 交给系统。这样登录能走通，页面里的普通链接也都在壳内打开，靠系统返回键回退（`RemoteControlApp.kt` 里已有的 `BackHandler` 是「能退就 `goBack()`，退到底才关掉远控」）
2. WebView 打开 `setAcceptThirdPartyCookies`，避免回调链路里的跨站 Cookie 静默丢失
3. `setSupportMultipleWindows(true)` + `onCreateWindow`：远控页里 `window.open` / `target=_blank` 的链接（文档、反馈、社区）原来点下去毫无反应，现在装进同一个 WebView

顺带解决 `/remote` → `/cn/remote` 这类同域跳转同样被甩出去的问题。

## 图标

用 ZCode 官方应用图标：纯黑底 + 白色 Z。

源头是 mac 上 `/Applications/ZCode.app/Contents/Resources/icon.png` 直接拷来的 `icon/src/zcode-app-1024.png`（macOS squircle，四角透明、带一点自上而下的渐变）。安卓要满幅方形，所以 `icon/generate.py`（Pillow）把白 Z 抠出来重铺到纯黑底 `#0A0B0C` 上：

- `mipmap-*dpi/ic_launcher.png` 与 `ic_launcher_round.png`：传统方形 + 圆形版，48/72/96/144/192 px，Z 占边长 49.8%（与源图一致）
- `mipmap-*dpi/ic_launcher_foreground.png`：adaptive 前景，透明画布 108dp，只放白 Z，换算成可见区里同样是 49.8%
- `mipmap-anydpi-v26/ic_launcher{,_round}.xml`：`<background>` 指向 `@color/zcode_icon_background`，`<monochrome>` 复用前景供主题图标取色

上游那套图标是 AOSP 模板（绿色机器人 + `.webp` 位图），CI 覆盖时先删 `.webp` 再整目录拷进去。换掉它同时意味着启动器不再显示 Android 默认机器人。

## 源码完整性

构建分三步校验：

```bash
# 1. 打补丁前：上游检出本身必须是干净的
cd zcode
changes=$(git status --porcelain | grep -v '^?? packages/android/local.properties$' || true)
[ -n "$changes" ] && exit 1

# 2. 打补丁后：源码树里的改动必须恰好等于 patches/ 下所有补丁
cat ../self/patches/*.patch > expected.patch
git diff > actual.patch
diff -u expected.patch actual.patch

# 3. 换图标后：res/ 之外不许再冒出别的改动
git status --porcelain | grep -vE 'local.properties|src/main/res/|ui/RemoteControlApp\.kt' && exit 1
```

除 `local.properties`（只含一行 `sdk.dir`）和 `patches/` 里的补丁之外，上游源码树有任何改动就中止构建。产物里附 `upstream-commit.txt`（编译用的提交号）和 `patches.txt`（补丁哈希）。

## 需要的仓库 secrets

| secret | 内容 |
| --- | --- |
| `ZCODE_KEYSTORE_B64` | PKCS#12 密钥库的 base64 |
| `ZCODE_KEYSTORE_PASS` | 密钥库密码 |
| `ZCODE_KEY_PASS` | 私钥密码 |

密钥别名固定为 `zcode`。换密钥会导致已装版本无法覆盖升级。

## 构建参数

| 项 | 值 |
| --- | --- |
| Gradle | 9.4.1（项目自带 wrapper） |
| AGP | 9.2.1 |
| Kotlin | 2.2.10 |
| JDK | 21 |
| compileSdk | 36（minorApiLevel 1） |
| build-tools | 36.1.0 |
| minSdk | 24 |

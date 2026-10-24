# zcode-android-build

在 GitHub Actions 上编译 [zai-org/ZCode](https://github.com/zai-org/ZCode) 官方 Android 壳，不需要本地 Android SDK。

## 为什么是这种方式

不 fork 官方仓库（那是整个桌面端 + CLI + 服务端的 monorepo）。CI 里用 `actions/checkout` 的稀疏检出只拉 `packages/android` 一个目录，编译完上传 APK。上游更新后重跑一次就是最新版，本地不需要同步任何代码。

## 用法

1. Actions → **Build ZCode Android APK** → **Run workflow**
2. `upstream_ref` 留 `main` 就是官方最新；要固定版本就填提交号或 tag
3. 跑完在 run 页面底部下载 `zcode-android-debug` 产物

## 产出说明

- 应用包名 `com.example.zcode_mobile`，App 名称 `ZCode`，与官方桌面端区分开
- **debug 签名**：官方 `build.gradle.kts` 没有 release 签名配置，出不了可直接安装的 release 包。debug 包可以正常安装，缺点是 `debuggable=true`（需要 USB 调试加物理接触才能利用）
- debug 版额外允许 localhost 和局域网地址，方便本地调试；生产包只允许 `https://zcode.z.ai/remote`
- 功能范围：扫码 / 粘贴链接 / deep link 三种入口，最近 5 条链接，WebView 承载官方远控页，前台服务保活 + 屏幕常亮。**没有**任务通知、应用锁、多机管理

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

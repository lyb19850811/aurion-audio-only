# Hostinger 共享主机管理方案（REST API）

> 适用：WordPress 部署在 Hostinger 等**共享虚拟主机**上（无 SSH / 无 root / 无 Docker）时，如何用 AI 或脚本远程改页面、管产品。
> 与 ECS 的区别：ECS 有 SSH，可直接跑 wp-cli、改数据库；虚拟主机只有 hPanel/cPanel + FTP + phpMyAdmin。

## 一、核心思路

WordPress 自带 REST API，走 **HTTPS + 认证**就能增删改页面/文章/菜单/产品，**不需要 SSH**。所以「AI 写页面 → 上传」的工作流照旧，只是把「上传」从 wp-cli 换成 REST API。

| 操作 | 端点 | 认证 |
|---|---|---|
| 页面 | `/wp-json/wp/v2/pages` | 应用密码 |
| 文章 | `/wp-json/wp/v2/posts` | 应用密码 |
| 菜单 | `/wp-json/wp/v2/menus`、`/wp-json/wp/v2/menu-items`（WP 5.9+） | 应用密码 |
| 产品（WooCommerce） | `/wp-json/wc/v3/products` | WooCommerce 密钥 |

## 二、前置准备（一次性）

### 1. 生成「应用密码」（页面/文章/菜单用）

后台 → **Users → Profile → Application Passwords → Add New**，输入一个名字（如 `ai-bot`），复制生成的密码（形如 `xxxx xxxx xxxx xxxx xxxx xxxx`）。

> 应用密码是 WordPress 5.6+ 内置功能，每个用户独立，可随时吊销，无需装插件。

### 2. 生成 WooCommerce 密钥（产品用，仅装了 WooCommerce 时）

后台 → **WooCommerce → Settings → Advanced → REST API → Add key**，权限选 Read/Write，复制 `Consumer Key`（ck_…）和 `Consumer Secret`（cs_…）。

### 3. 配置脚本

```bash
cp .env.hostinger.example .env.hostinger
# 编辑 .env.hostinger，填入 WP_URL / WP_USER / WP_APP_PASSWORD /（可选）WC_*
```

`.env.hostinger` 已被 `.gitignore` 排除，密钥不会进 git。

## 三、脚本用法（scripts/hostinger_wp.py）

### 页面

```bash
# 列出所有页面
python3 scripts/hostinger_wp.py page list

# 创建页面（内容可以是文件路径，也可以是 HTML 字符串）
python3 scripts/hostinger_wp.py page create --title "FAQ" --slug faq --content content/faq.html

# 按 slug 更新页面
python3 scripts/hostinger_wp.py page update faq --content content/faq.html

# 按 slug 删除页面
python3 scripts/hostinger_wp.py page delete faq
```

### 文章

```bash
python3 scripts/hostinger_wp.py post list
python3 scripts/hostinger_wp.py post create --title "标题" --content content/post.html
```

### 菜单

```bash
# 列出菜单（拿到菜单 ID）
python3 scripts/hostinger_wp.py menu list

# 列出某菜单下的菜单项
python3 scripts/hostinger_wp.py menu items <菜单ID>

# 加顶级自定义链接
python3 scripts/hostinger_wp.py menu add-custom "外部连接" "#" --menu-id <菜单ID>

# 加子项（--parent-id 指到父项，做成下拉）
python3 scripts/hostinger_wp.py menu add-custom "百度" "https://www.baidu.com" \
  --menu-id <菜单ID> --parent-id <父项ID>
```

### 产品（WooCommerce）

```bash
python3 scripts/hostinger_wp.py product list
python3 scripts/hostinger_wp.py product create --name "Aurion A1" --price 199 --description "五动铁入耳监听"
```

## 四、产品管理的两种情况

| 现状 | 怎么管 |
|---|---|
| 没装 WooCommerce（产品只是页面里的卡片） | 走 `page` 命令改页面内容 |
| 装了 WooCommerce（真商品：价格/库存/详情页） | 走 `product` 命令 |

## 五、与 ECS 的对比

| | ECS（VPS） | Hostinger（虚拟主机） |
|---|---|---|
| 访问通道 | SSH → wp-cli / 直接改 DB | HTTPS → REST API |
| 依赖 | 需要 SSH 权限 | 只需应用密码 |
| 脚本 | `docker compose exec … wp …` | `scripts/hostinger_wp.py` |
| 数据库直连 | 可 | 只能 phpMyAdmin（网页） |
| 安全性 | 密钥在服务器 | 应用密码可随时吊销 |

## 六、注意事项

1. **HTTPS 必须**：应用密码走 Basic Auth，明文等于密码，必须配合 HTTPS；Hostinger 默认带免费 SSL，确认已开启。
2. **菜单 REST API 需 WP 5.9+**：更老的版本用 `menu` 命令会失败，改用后台手动或 wp-cli。
3. **内容格式**：`--content` 传的文件就是 Gutenberg 区块 HTML（`<!-- wp:… -->`），和本项目 `content/*.html` 同一套，导入后后台仍可可视化编辑。
4. **吊销**：不再需要时，去 Application Passwords 删掉对应密码即可一键断权限。

## 七、curl 直接操作（不依赖脚本）

脚本覆盖了常用场景，但有两个能力脚本没有：**页面引用型菜单项**、**任意字段定制**。这些用 curl 最直观。

### 通用模板

```bash
curl -X POST "https://你的域名/wp-json/wp/v2/menu-items" \
  -u '用户名:应用密码' \
  -H "Content-Type: application/json" \
  -d '{ ...JSON 请求体... }'
```

> 认证是 Basic Auth（`-u '用户名:应用密码'`），密码放单引号里避免 shell 转义；必须走 HTTPS。

### 1. 加「页面引用」型菜单项（推荐，脚本没有此能力）

```bash
curl -X POST "https://你的域名/wp-json/wp/v2/menu-items" \
  -u '用户名:应用密码' \
  -H "Content-Type: application/json" \
  -d '{
    "menus": 3,
    "title": "FAQ",
    "status": "publish",
    "type": "post_type",
    "object": "page",
    "object_id": 49,
    "menu_order": 7
  }'
```

### 2. 加「自定义链接」菜单项（等价于脚本 `menu add-custom`）

```bash
curl -X POST "https://你的域名/wp-json/wp/v2/menu-items" \
  -u '用户名:应用密码' \
  -H "Content-Type: application/json" \
  -d '{"menus":3,"title":"百度","url":"https://www.baidu.com","status":"publish"}'
```

### 3. 创建页面

```bash
curl -X POST "https://你的域名/wp-json/wp/v2/pages" \
  -u '用户名:应用密码' \
  -H "Content-Type: application/json" \
  -d '{"title":"FAQ","slug":"faq","status":"publish","content":"<p>内容</p>"}'
```

### 参数速查

| JSON 参数 | 含义 | 说明 |
|---|---|---|
| `menus` | 菜单 ID | `menu list` 查 |
| `title` | 菜单项文字 | |
| `type` | 类型 | `post_type`(页面引用) / `custom`(自定义链接) |
| `object` + `object_id` | 引用对象 | 页面引用时：`object=page`、`object_id=页面ID` |
| `url` | 链接 | 仅 `custom` 类型需要 |
| `parent` | 父项 ID | 填了 = 做成下拉子项 |
| `menu_order` | 排序位置 | 数字越小越靠前 |

### 三种操作方式对比

| 方式 | 适用 | 优缺点 |
|---|---|---|
| curl | 任意定制、页面引用 | 最灵活，需手写 JSON |
| 脚本 `hostinger_wp.py` | 常用操作 | 简单；菜单只支持 custom 链接 |
| wp-admin 后台 | 偶尔手动 | 零命令，但不可脚本化 |

## 八、实际案例（orioleaudio.com，2026-10）

> 以下记录实际执行的操作，**不含密钥**（应用密码存于 `.env.hostinger`）。

- 站点：https://www.orioleaudio.com
- 账号：用户名 `ai-bot`（管理员），邮箱 lyb19850811@gmail.com
- 生效菜单：`Primary`（id=3，分配在 primary 位置）；闲置菜单 `Primary (2)`（id=4，未分配位置）

已执行操作：

1. 创建 FAQ 页面（id=49，slug=faq，publish），内容取自 `content/faq.html`，CTA 按钮链接由 `/contact/` 改为 `#contact`
2. 把 FAQ 以「页面引用」方式加入 Primary 菜单（菜单项 id=50，type=post_type / object=page / object_id=49，menu_order=7 排末尾）
3. 访问地址：https://www.orioleaudio.com/faq/

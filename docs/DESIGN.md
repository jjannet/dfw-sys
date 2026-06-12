# dfw-sys — Database Schema + โครง Solution (ร่างเพื่อ review)

> ร่างวันที่ 2026-06-12 ต่อจาก [SPEC.md](SPEC.md) — **review แล้ว ข้อตัดสินใจปิดครบ (ข้อ 5)** พร้อมเริ่ม phase 1
> ข้อ 6 คือ scan patterns ที่ได้จากการสำรวจ repo ตัวอย่างจริง — เป็น input ของ scan skill ใน phase 2

## 1. หลักการออกแบบ schema

**ใช้ EF Core migrations กับ PostgreSQL (Npgsql)** — ทีมคุ้น EF Core จาก framework เดิมอยู่แล้ว และใช้ extension `vector` (pgvector) กับ full-text search ของ Postgres ใน database เดียว

**Graph แบบ "typed nodes + node registry":** entity แต่ละชนิดมีตารางของตัวเอง (query สะดวก, มี FK จริง) แต่ทุก row จะลงทะเบียนใน `catalog_nodes` ด้วย เพื่อให้ตาราง `relations` (edges) ชี้หา node ชนิดไหนก็ได้โดยยังมี FK integrity — ได้ทั้งความเป็น graph และความเป็น relational

**สองชั้น auto/manual ในทุก entity ของ catalog:**

- คอลัมน์โครงสร้าง (path, method, ชื่อ table ฯลฯ) — scan เป็นคนดูแล ทับได้
- `scan_meta jsonb` — รายละเอียดเพิ่มเติมจาก scan (signature, file path, commit) ทับทั้งก้อนทุกรอบ scan
- คอลัมน์ curated (`owner`, `purpose`, `usage_notes`) — แก้จาก UI เท่านั้น scan ห้ามแตะ

## 2. ตาราง (จัดกลุ่มตามหน้าที่)

### 2.1 Catalog graph

| ตาราง | คอลัมน์หลัก |
|---|---|
| `catalog_nodes` | `id uuid PK`, `node_type` (registry กลางของทุก node — ทุกตารางด้านล่างมี FK 1:1 มาที่นี่) |
| `zones` | id, `key` (core, dxc, …), name, `zone_type` (core/product) |
| `repos` | id, **`repo_url` unique (natural key)**, `repo_type` (service/submodule), `submodule_kind` (intercom/shared-api/shared-ui, null ถ้าเป็น service), zone_id, name, `has_tenant_db bool` — curated: owner, purpose, notes |
| `endpoints` | id, repo_id, `protocol` (http/grpc), http: method+path / grpc: proto_service+method, scan_meta — curated: purpose, usage_notes |
| `functions` | id, repo_id, name, file_path, scan_meta — curated: description |
| `db_objects` | id, `object_type` (table/view/table_type/sql_file/stored_proc/redis_key/mongo_collection), name, `owner_repo_id` (จาก prefix), `database_scope` (main/tenant ถ้ารู้), scan_meta — curated: purpose |
| `config_items` | id, repo_id, key, `config_location` (จุดที่ config), scan_meta — curated: purpose |
| `deploy_groups` | id, name (เช่น `gs-coreutils`), + `deploy_group_members` (group_id, repo_id) — ใช้ฝั่ง monitoring เท่านั้น; **derive อัตโนมัติได้จาก oc** (k8s Service ราย service ชี้เข้า pod ของ group) เก็บใน catalog เป็น snapshot/cache ไม่ต้องกรอกมือ |
| `relations` | id, `source_node_id FK→catalog_nodes`, `target_node_id FK→catalog_nodes`, `relation_type` (calls / uses_submodule / reads / writes / configured_at), `version_ref` (branch/commit — ใช้กับ uses_submodule), `origin` (scanned/manual), `scanned_commit`, created_at/by — unique กัน edge ซ้ำ |

### 2.2 Scan

| ตาราง | คอลัมน์หลัก |
|---|---|
| `scan_runs` | id, repo_id, branch, commit, pushed_by (user), started_at, finished_at, `summary jsonb` (เพิ่ม/ลบ/แก้กี่รายการ) |
| `skills` | id, `skill_key` (scan / error-hunt), version, `content` (markdown), is_active, updated_by/at — skill เก็บในระบบ มี version history ในตัว (row ละ version, active ทีละอัน) |

### 2.3 AppSettings + Log targets

| ตาราง | คอลัมน์หลัก |
|---|---|
| `app_settings` | id, repo_id, `environment` (**text อิสระ ไม่ fix enum** — ของจริงมี Development/Dev/Sit/Uat/Production + ตัว *Debug และ UI มี qas), `content_encrypted bytea`, updated_by/at — unique (repo, env) |
| `app_settings_history` | snapshot เดิมทุกครั้งที่แก้ (ดูย้อน/กู้คืนได้) |
| `log_targets` | id, zone_id, `target_type` (seq/jaeger), url, `auth_type` (none/api_key/basic), `secret_encrypted` |

### 2.4 Case knowledge base

| ตาราง | คอลัมน์หลัก |
|---|---|
| `cases` | id, title, symptom, `error_signature` (ไว้จับซ้ำ), `investigation` (markdown — ขั้นตอนที่ใช้ตามหา), root_cause, fix_temporary, fix_permanent, `status` (open/recurring/fixed_permanently), created_by/at |
| `case_occurrences` | case_id, occurred_at, noted_by, notes — เกิดซ้ำบันทึกที่นี่ ไม่สร้าง case ใหม่ |
| `case_links` | case_id, node_id FK→catalog_nodes — ผูก case เข้า service/endpoint ใน graph |

### 2.5 Users / Auth / Audit

| ตาราง | คอลัมน์หลัก |
|---|---|
| `users` | id, email unique, entra_object_id, display_name, `status` (invited/active/disabled) — admin ไม่อยู่ใน DB, เช็คจาก email list ใน `.env` ตอน login |
| `invitations` | id, email, invited_by, invited_at, accepted_at |
| `product_editors` | user_id, zone_id — role แก้ไขราย product (view ทุกคนเห็นหมด) |
| `pat_tokens` | id, user_id, name, `token_hash` (เก็บ hash ไม่เก็บตัวจริง), created_at, last_used_at, expires_at, revoked_at |
| `audit_logs` | id, actor_user_id, `via` (ui/scan/mcp), action, node_type, node_id, `diff jsonb`, scan_run_id (ถ้ามาจาก scan), created_at |

### 2.6 RAG

| ตาราง | คอลัมน์หลัก |
|---|---|
| `rag_documents` | id, node_id FK→catalog_nodes (รวม case ด้วย), `content` (การ์ดข้อความที่ render), `embedding vector(1024)` (bge-m3), `content_tsv tsvector` (full-text), updated_at — มี trigger/outbox ให้ re-index เมื่อ entity เปลี่ยน |

## 3. โครง Solution (monorepo)

```
dfw-sys/
├── docs/                          # SPEC, DESIGN, ADR ต่อ ๆ ไป
├── server/
│   ├── DfwSys.sln
│   ├── src/
│   │   ├── DfwSys.Api/            # .NET 10 Web API host — controllers, auth (Entra OIDC), DI
│   │   ├── DfwSys.Core/           # domain: entities, business rules, interfaces (ไม่พึ่ง infra)
│   │   ├── DfwSys.Infrastructure/ # EF Core + Npgsql + pgvector, encryption, audit,
│   │   │                          #   vLLM clients (embed/rerank/chat), RAG engine
│   │   └── DfwSys.Contracts/      # DTOs ที่ใช้ร่วมกับ client: scan payload, API models
│   └── tests/
│       └── DfwSys.Api.Tests/
├── client/
│   ├── DfwClient.sln              # อ้าง DfwSys.Contracts ด้วย project reference (monorepo)
│   └── src/
│       ├── DfwClient/             # daemon host: localhost REST + MCP server (streamable HTTP),
│       │                          #   PAT config, origin check, self-update check
│       └── DfwClient.Connectors/  # Seq, Jaeger, OpenShift (เรียก oc / kubeconfig ของ user)
├── ui/                            # Angular 22 workspace + PrimeNG
│   └── src/app/
│       ├── core/                  # auth, api client, layout
│       ├── shared/                # UI kit กลาง: wrapper components ครอบ PrimeNG + theme,
│       │                          #   pipes, directives — feature ต้องใช้จากตรงนี้เท่านั้น
│       └── features/              # catalog, graph-explorer, monitoring, cases,
│                                  #   appsettings, ai-search, admin
├── .github/workflows/
│   └── deploy.yml                 # self-hosted runner บนเครื่องนี้: detect-changes (api/ui)
│                                  #   → copy .env จาก action-runner/envs/dfw-sys/
│                                  #   → docker compose up -d --build → image prune
├── deploy/
│   ├── docker-compose.yml         # postgres(+pgvector), api, ui (nginx) — ทุก image เป็น arm64
│   └── .env.example               # admin emails, encryption key, Entra app, vLLM endpoints
│                                  #   (.env จริงอยู่ที่ /home/jjannet/shared/action-runner/envs/dfw-sys/)
└── README.md
```

จุดที่จงใจเลือก:

- **`DfwSys.Contracts` เป็น project เดียวที่ server กับ client ใช้ร่วม** — contract ของ `push_scan` อยู่ที่เดียว แก้แล้วเห็นพร้อมกันสองฝั่ง
- client แยก solution เพราะ build target ต่างกัน (publish self-contained win-x64 / osx-arm64) แต่ยังอยู่ repo เดียว
- RAG ไม่แยกเป็น service ต่างหาก — เป็น module ใน Infrastructure เรียก vLLM ที่รันอยู่แล้วผ่าน HTTP (ลด process บนเครื่องที่ memory ตึง)

## 4. Flow สำคัญที่กระทบ schema

**push_scan (upsert ชั้น auto):** เปิด `scan_runs` → upsert nodes ตามโครงสร้างที่ scan เจอ (เทียบของเดิมด้วย natural key: repo_url, method+path, ชื่อ table) → ของที่หายไปจาก scan = soft-delete (mark `removed_at` ไม่ลบจริง เพื่อให้ curated data ไม่หาย ถ้า scan รอบหน้าเจออีกค่อยปลุกคืน) → replace edges ที่ `origin=scanned` ของ repo นั้น → ปิด run + audit + คิว re-index RAG

**PAT auth:** client ส่ง token → server เทียบ hash → ได้ user → สิทธิ์เท่ากับ user คนนั้น (editor ราย product มีผลกับ MCP ด้วย)

**Encryption:** `app_settings.content_encrypted` และ `log_targets.secret_encrypted` ใช้ AES-256-GCM, key อยู่ใน `.env` ของ server เท่านั้น — decrypt ฝั่ง server ตอนเสิร์ฟให้ user ที่ login แล้ว

## 5. ข้อตัดสินใจ (สรุปจาก review 2026-06-12)

1. **Soft-delete** ✅ — ตอน scan ไม่เจอของเดิมให้ mark `removed_at` ไม่ลบจริง และ **UI ต้องดูย้อนหลังได้ว่าอะไรถูกลบไปตอนไหน** (มุมมองประวัติการลบ)
2. **PAT หมดอายุ 90 วัน** ✅ — ต่ออายุ/ออกใหม่จากหน้า web, ไม่มี token ถาวร (PAT = token ที่ client ใช้ authen กับ server)
3. **Namespace ใช้ `DfwSys` / `DfwClient`** ✅ — user confirm แล้ว
4. **Angular เป็น app เดี่ยว + แยก `shared/` เป็น UI kit กลาง** ✅ — ไม่แยกเป็น library แต่บังคับโครง folder: ทุก component ที่ใช้ซ้ำ (ปุ่ม ตาราง ฟอร์ม dialog) อยู่ใน `shared/` เป็น wrapper ครอบ PrimeNG ผูกกับ theme กลาง — **feature ห้ามแต่ง style เอง ต้องใช้ของจาก `shared/`** เพื่อให้ทั้ง project คุม style จุดเดียว theme ไม่หลุด

## 6. Scan patterns จาก repo ตัวอย่าง (input ของ scan skill)

จากการสำรวจ `be-pttdigital-dfw-cs-config`, `be-pttdigital-dxc-cs-pdoc`, `fe-pttdigital-dxc-ui-main`:

| สิ่งที่หา | Pattern ที่ scanner ใช้จับ |
|---|---|
| HTTP endpoints | controller ใน `Service.API/Controllers/V*/` + `[Route("api/v{version:apiVersion}/[controller]")]` + HTTP method attributes |
| gRPC ฝั่งให้บริการ | class inherit `{X}Proto.{X}ProtoBase` + `endpoints.MapGrpcService<T>()` ใน Startup |
| gRPC ฝั่งเรียก | `AddGrpcClient<T>` / `AddGrpcClientCorrelation<T>` / `AddGrpcClientCustomHeader<T>` ใน Startup + section `GrcpServiceSetting` ใน appsettings → **รู้ target service จากชื่อ setting ตรง ๆ** |
| HTTP ฝั่งเรียก | `IDFWRestClient` + section `DFWRestSetting` ใน appsettings |
| จุดเรียกจริงระดับ function | การ inject/ใช้ `{X}ProtoClient` และ `IDFWRestClient` ใน Services/Repositories |
| Tables | EF entities + `IEntityTypeConfiguration<T>` + migrations — prefix: core = schema+`MS_`/`TX_`, product = `{ZONE}_{SVC}_MS_`/`TX_` + attribute `[TableType(MASTER)]` |
| Tenant pattern | มี `TenantDbContext` / `BaseTenantDbContext` / `TenantDbContextSettings` → ติด flag `has_tenant_db` |
| Views / table types / SQL | migration scripts (`migrationBuilder.Sql(...)`) + ไฟล์ `.sql` ใน repo (Dapper — สอง repo ตัวอย่างไม่มี แต่บาง project มี) |
| Submodules | `.gitmodules` + commit ที่ pin (`git submodule status`) — backend: `*-mw-*` (core/shared/intercom/utils/biz/erp), frontend: `src/@core`, `src/@shared`, `src/@doc` |
| Config keys | appsettings ทุก environment + ตัว `*Debug` |
| Redis / Mongo | `RedisSettings`, `SQLCacheRedis`, `TenantMongoDbContextSettings`, `CompanyMongoDbSettings` |
| UI → API | `${environment.apis.{service}}/api/v1/{Resource}/{action}` ใน Angular services + map `environment.apis` ใน `src/environments/` |
| Zone/service identity | `ProductName` + `ServiceName` ใน appsettings.json + ชื่อ repo `be-pttdigital-{zone}-cs-{service}` |
| Deploy/OpenShift naming | namespace `do{code}-{zone}-{env}` (env: dev/sbx/sit/uat, prd คนละ cluster), pod เดี่ยว `…-cs-{name}-{env}` / group `…-gs-{group}-{env}` (1 container, หลาย service ใน process เดียว, port คู่ HTTP/gRPC ต่อ service), k8s Service ราย logical service → ใช้ resolve pod อัตโนมัติ, ConfigMap/Secret 3 ชั้น `ut-oc-{c\|p\|a}conf`, image tag `{env}-{commit}` |

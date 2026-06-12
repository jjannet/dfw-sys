# dfw-sys — System Specification

> ร่างจากการคุย requirements วันที่ 2026-06-12 — สถานะ: requirements นิ่งแล้ว ยังไม่เริ่ม code
> ขั้นถัดไป: ร่าง database schema ฉบับเต็ม + โครง solution

## 1. ปัญหาและเป้าหมาย

Framework ภายในเป็น microservice (.NET 6 + Angular) มี service จำนวนมาก เส้น gRPC และ HTTP API ยิงไปมาเต็มไปหมด ไม่มีเอกสารกลาง — การจะรู้ว่าดึงข้อมูลยังไงต้องไปถามคนทำแต่ละ service ซึ่งช้าและพึ่งพาตัวบุคคล

**dfw-sys** คือระบบ Service Catalog + Observability Hub ที่เป็น single source of truth ของทั้ง framework:

1. Catalog เส้น API / gRPC ทั้งหมด — ใครเป็นเจ้าของ เอาไว้ทำอะไร ใช้งานยังไง ใครเรียกบ้าง
2. ผูก relation ทั้ง framework และมี UI ไล่ดูเส้นทาง (graph explorer)
3. Catalog ฝั่ง database (SQL Server / Redis / Mongo) — มี table อะไร ใช้ทำอะไร
4. Catalog config + เก็บ appsettings กลางของแต่ละ project (โหลดไป debug ได้)
5. Monitor production ผ่าน client ที่เครื่อง user (Seq / Jaeger / OpenShift)
6. MCP tools ให้ AI ทุกตัว (Claude Code, Cursor ฯลฯ) เรียกใช้ข้อมูลและ monitor ได้
7. RAG เต็ม loop ด้วย model local สำหรับ AI search
8. Case knowledge base — เก็บ case ที่เคยไล่ปัญหา/แก้แล้ว ให้ AI ใช้เป็นทางลัดรอบหน้า และเป็น issue data สำหรับการแก้ถาวร

## 2. บริบทของ framework ที่จะ catalog

- .NET 6 microservices + Angular UI แบ่งโซนเป็น **core** (มี ERP และ service IDS กลางสำหรับ authen ทั้ง framework) และ **product** 4 ตัว — รวม ~50 services
- **Focus แรก: core + product 1 ตัว (~30 services)**
- Service คุยกันด้วย gRPC และ HTTP
  - proto files รวมอยู่ใน git submodule ชื่อ **intercom**
  - function เรียก HTTP ก็อยู่ใน shared submodule เช่นกัน → relation หาได้จากการ scan code
- **Shared submodules** (ฝั่ง API และ UI) ใช้ร่วมทั้ง framework แยก release เป็น branch ตาม version
- Database: SQL Server (table แยก prefix ตามชื่อ service, auto migration ด้วย EF Core), Redis, Mongo
  - แต่ละ service มี **main DB + tenant DB แยกตามลูกค้า auto-switch ตาม token**
  - มี stored procedure / function / view / table type และบาง project มี SQL file เรียกผ่าน Dapper
- Log: **Seq แยกตามกลุ่ม** (core 1 ตัว + product ละ 1 ตัว, auth ด้วย API key) + **Jaeger 1 ตัว** ทั้ง framework (ไม่มี auth ในตัว — ต้องเช็คว่า expose ผ่านอะไร)
- Deploy บน OpenShift มีการ **group service** — 1 pod อาจรัน ~4 services (มีผลตอน monitor log, ไม่มีผลตอน relation)
- Environment: dev / sit / uat / production — **ระบบ focus production เท่านั้น** (ฝั่ง monitoring) เพื่อให้ใช้ง่าย ไม่ซับซ้อน
- **Jaeger production เปิดโล่ง ไม่มี auth** — แค่ต้องอยู่ใน internal network
- OpenShift: client เรียกผ่าน **`oc` CLI ของ user** — ต้อง handle เคส oc ไม่ได้ติดตั้ง / ยังไม่ login ให้ฟ้องชัดเจน

### Conventions ที่พบจาก repo ตัวอย่างจริง

ตัวอย่าง 3 repo อยู่ที่ `/home/jjannet/shared/projects/ex-dfw-project/`:
`be-pttdigital-dfw-cs-config` (core service) · `be-pttdigital-dxc-cs-pdoc` (product service) · `fe-pttdigital-dxc-ui-main` (product UI)

- **ชื่อ repo:** `be-pttdigital-{zone}-cs-{service}` / `fe-pttdigital-{zone}-ui-{name}` / submodule `-mw-` (backend), `-md-` (frontend) — zone code: `dfw` = core, `dxc` = product / git อยู่ที่ `git.pttdigital.com` group `do64002-dfw`, `do65005-dxc`
- **Submodules backend:** `dfw-mw-core`, `dfw-mw-shared`, `dfw-mw-intercom` (proto กลาง), `dfw-mw-utils`, `dfw-mw-biz`, `dfw-mw-erp` + ฝั่ง product มี `dxc-mw-intercom`, `dxc-mw-biz` ของตัวเอง — pin ด้วย commit (บางตัว track branch เช่น dev)
- **Submodules frontend:** `src/@core` (auth/layout/interceptor), `src/@shared` (ของ product), `src/@doc`
- **gRPC:** service ฝั่งรับ inherit `{Name}Proto.{Name}ProtoBase` + `MapGrpcService<T>()` / ฝั่งเรียกลงทะเบียน `AddGrpcClient<T>` หรือ extension `AddGrpcClientCorrelation<T>` / `AddGrpcClientCustomHeader<T>` โดย URL มาจาก `GrcpServiceSetting` ใน appsettings → **map client→target service ได้จาก config ตรง ๆ**
- **HTTP ข้าม service:** `IDFWRestClient` + section `DFWRestSetting` ใน appsettings (Core, ErpSrc, Storage, Hrs, Travel ฯลฯ)
- **Controller:** `[Route("api/v{version:apiVersion}/[controller]")]` + `[Authorize]` + AutoWrapper ครอบ response
- **EF Core:** DbContext หลัก + `TenantDbContext` (inherit `BaseTenantDbContext`, สลับ connection ตาม token/`TenantDbContextSettings`) / table prefix จริง: core ใช้ schema (เช่น `Config`) + prefix `MS_` (master), `TX_` (transaction); product ใช้ `DXC_PDOC_MS_…` / มี attribute `[TableType(MASTER)]` บน entity / migrations อยู่ `Service.API/Migrations/` (แยก `TenantDb/`)
- **appsettings จริง:** `appsettings.{Development,Dev,Sit,Uat,Production}.json` + ตัว `*Debug` (DevDebug/SitDebug/UatDebug) → **environment ในระบบเป็นค่าอิสระ ไม่ fix enum** (หมายเหตุ: `qas` ที่เจอใน UI เป็นของเก่าลืมลบ ไม่ใช้)
- **Logging:** Serilog + Seq sink, URL pattern `do65005-dxc-be-pttdigital-dxc-os-seq-prd` / IDS: `StartupHelper.SetIdentityServer` ชี้ IDS ที่ core
- **Angular UI เรียก API:** `${environment.apis.{service}}/api/v1/{Resource}/{action}` โดย `environment.apis` map ชื่อ service → URL ผ่าน api gateway — scanner ฝั่ง UI หา pattern นี้
- **C# namespace ของ service จริงใช้ generic** (`Config.API`, `Service.API`) — ไม่มี company prefix ใน namespace

## 3. Tech stack ของ dfw-sys

| ส่วน | เทคโนโลยี |
|---|---|
| Backend | .NET 10 Web API |
| Frontend | Angular 22 + PrimeNG |
| Database | PostgreSQL (Docker บนเครื่องนี้) + pgvector ใน DB เดียวกัน |
| Client | .NET 10 self-contained single binary (win-x64, osx-arm64) headless daemon |
| LLM stack | vLLM ที่รันอยู่แล้ว: `bge-m3` (embeddings), `bge-reranker-v2-m3`, `Qwen3.6-35B-A3B` fp8 131k ctx tool-calling, `typhoon-ocr-7b` |
| Server | Lenovo PGX — NVIDIA GB10 (Grace Blackwell), 119 GiB unified memory, 20 cores, aarch64. GPU mem ถูกจองแล้ว ~75% — ต้องคุม memory ของระบบ |

## 4. Architecture

```
                    เครื่อง Lenovo PGX (server dfw-sys)
┌──────────────────────────────────────────────────────────────────┐
│  Angular 22 UI (PrimeNG)                                         │
│       │                                                          │
│  .NET 10 Web API ────────────┬──────────────────────┐            │
│   - Catalog API              │                      │            │
│   - Auth (Microsoft login)   │                      │            │
│   - AppSettings store        │                      │            │
│   - Audit log                │                      │            │
│       │                  RAG Engine            vLLM (มีอยู่แล้ว) │
│  PostgreSQL (Docker)      - hybrid search      - bge-m3          │
│   - catalog graph         - agentic loop       - bge-reranker    │
│   - pgvector                                   - qwen3.6-35b     │
│   - appsettings (encrypt)                                        │
└──────────────────────────────────────────────────────────────────┘
                              ▲ HTTPS + PAT token
                              │
                  dfw-client (เครื่อง user: Windows / macOS)
┌──────────────────────────────────────────────────────────────────┐
│  localhost HTTP server                                           │
│   - REST ให้เบราว์เซอร์ (web UI) เรียก                           │
│   - MCP server (streamable HTTP) ให้ AI ทุกตัวเรียก              │
│  local config file: PAT token                                    │
│  ใช้ oc login ของ user สำหรับ OpenShift                          │
└──────────┬───────────────────────────────────────────────────────┘
           │ (network ฝั่ง framework — user ต้องเข้าถึงได้)
   Seq core / Seq products / Jaeger / OpenShift (production)
```

หลักคิด: **server ของ dfw-sys อยู่คนละ network กับ framework** — ทุกอย่างที่ต้องแตะของจริง (log, trace, pod) วิ่งผ่าน client ที่เครื่อง user เสมอ ทั้งจาก web UI และจาก AI

### 4.1 dfw-client

- .NET 10 console app, self-contained single binary, **ไม่มี GUI** — รันเป็น background daemon (Windows: startup/tray, macOS: launchd agent)
- เปิด localhost HTTP: REST สำหรับเบราว์เซอร์ + MCP endpoint (streamable HTTP — มาตรฐานเปิด AI ทุกตัวใช้ได้)
- Authen กับ server ด้วย **Personal Access Token (PAT)** ที่ user generate จากหน้า web แล้ววางใน config file
- ต้องกัน website อื่นแอบเรียก: เช็ค Origin (CORS) + บังคับ token
- มีหน้า "ตรวจสถานะ client" ใน web UI ยิง localhost เช็คว่าต่อติดครบทุกระบบไหม
- รองรับ self-update check จาก server (อนาคต)

### 4.2 Credentials

| ของ | เก็บที่ไหน |
|---|---|
| Seq API keys | ในระบบ dfw-sys (client มาขอตอนใช้) |
| Jaeger | **เปิดโล่งใน internal network ไม่มี auth** — LogTarget ยังออกแบบ auth เป็น optional (none / API key header / basic) เผื่ออนาคต |
| OpenShift | client เรียกผ่าน **`oc` CLI** ที่เครื่อง user (ต้อง `oc login` ก่อน — ถือเป็นการเช็คสิทธิ์ด้วย เพราะแต่ละคนเห็น service ไม่เท่ากัน) — ต้อง handle เคส oc ไม่ได้ติดตั้ง/ยังไม่ login ให้ฟ้องชัดเจน |
| Database production | **ตัดออก — ไม่ต่อ database จริงเลย** ป้องกัน model เขียน data; DB catalog มาจากการ scan code ล้วน ๆ |
| appsettings กลาง | เก็บในระบบ แยก environment (dev/sit/uat/production), **encrypt at rest**, ทุกคนที่ถูกเชิญเห็นได้หมด (ไม่ทำสิทธิ์รายคน — คุมยาก) |

### 4.3 Auth ของระบบ + Roles

- **Microsoft login (Entra ID), invite-only** — เชิญแล้วมี email แจ้ง
- **Admin emails config ใน `.env`** (หลาย email ได้) — login ได้โดยไม่ต้องเชิญ
- Roles:
  - **admin** — ทำได้ทุกอย่าง
  - **product editor** — แก้ข้อมูลของ product ที่ได้รับสิทธิ์ (ระบุเป็นราย product)
  - ทุกคน **view ได้ทั้งหมด**

## 5. Data Model (catalog เป็น graph)

### Nodes

| Entity | Key / หมายเหตุ |
|---|---|
| Zone | core, product 1–4 |
| Service | **key = repo URL** (เสถียร ไม่เปลี่ยนบ่อย), สังกัด zone, owner, จุดประสงค์, metadata เช่น มี tenant pattern ไหม |
| Submodule | key = repo URL (intercom, shared API, shared UI) |
| Endpoint (HTTP) | service + method + path |
| GrpcMethod | service + proto service + method |
| Function | หน่วยระดับ code (ชื่อ, ไฟล์, คำอธิบาย) — เก็บเบา ๆ รองรับ use case อนาคต: ให้ Claude implement โดยอ้างอิง data จากระบบนี้ |
| DbObject | ชนิด: table (จาก EF entity), view / table type (จาก migration script), sql-file (Dapper), stored-proc (โครงรองรับ แต่ยังไม่ scan), redis-key, mongo-collection — table หา service เจ้าของจาก prefix |
| ConfigItem | ประเภท + config ที่จุดไหน |
| AppSettings | project + environment → encrypted blob |
| LogTarget | Seq แต่ละ zone (URL + API key), Jaeger (auth optional) |
| DeployGroup | pod ไหนรัน service อะไร — ใช้เฉพาะฝั่ง monitoring |
| Case | ดูข้อ 8 |
| User / Role / Invitation / AuditLog | ตามข้อ 4.3 |

### Edges (relations)

`calls` (function/service → endpoint/grpc method) · `uses-submodule` (service → submodule **@ branch หรือ commit id**) · `reads` / `writes` (service/sql-file → db object) · `owns` · `configured-at` — ทุก edge มี `source: scanned | manual` + เวลา + commit ที่ scan เจอ

### สองชั้น auto / manual

ทุก entity แยก field เป็น **ชั้น scan** (scan ใหม่ทับได้: รายการ endpoint, signature ฯลฯ) กับ **ชั้น curated** (owner, จุดประสงค์, โน้ต — scan ห้ามทับ) ไม่มีขั้น review แต่ทุกการเปลี่ยนแปลงลง **audit log** (ใคร / เมื่อไหร่ / scan หรือมือ / commit ไหน)

## 6. Ingestion — Claude Code เป็นตัว scan

1. user เปิด Claude Code ใน repo ของ service → สั่ง scan
2. Claude เรียก MCP tool **`get_scan_instructions`** ก่อนเสมอ (บังคับใน description ของ `push_scan`) — **ตัว skill/prompt มาตรฐานเก็บในระบบ dfw-sys** แก้ได้ในหน้า admin มี version history → ทุกคนใช้เวอร์ชันล่าสุดเสมอ ไม่หลุด format
3. Claude อ่าน code:
   - controllers → HTTP endpoints
   - intercom submodule → gRPC methods + จุดที่เรียกใช้
   - shared submodule → HTTP calls ระหว่าง service
   - EF Core entities → tables
   - migration scripts → views, table types
   - SQL files (Dapper) → sql-file nodes + parse ว่าแตะ table/view ไหน
   - appsettings → config keys
   - `.gitmodules` / submodule refs → uses-submodule @ branch/commit
4. Claude เรียก `push_scan` → client แนบ PAT → server upsert ชั้น auto + เขียน audit log
5. เติม owner / คำอธิบาย / แก้เล็กน้อยผ่าน web UI (ชั้น manual)

ขอบเขต DB scan = **ทุกอย่างที่อยู่ใน repo** เท่านั้น; object ที่ถูกสร้าง/แก้ตรงใน database โดยไม่ผ่าน code (stored proc บางส่วน — เป็น pain point ที่รู้กัน) อยู่นอก scope ไว้ก่อน โครง data model รองรับแล้ว อนาคตค่อยหาทาง import

## 7. RAG

- **Index:** ทุก entity render เป็น "การ์ดข้อความ" → embed ด้วย bge-m3 → pgvector; **re-index อัตโนมัติเมื่อ entity เปลี่ยน** (event-driven — data เข้าทาง API เราอยู่แล้ว)
- **Query loop:** คำถาม → hybrid search (vector + Postgres full-text) → rerank ด้วย bge-reranker → Qwen3.6 ตอบพร้อมอ้างอิง entity (คลิกไปหน้า catalog ได้)
- **Agentic:** Qwen เรียก tool ภายใน (`search_catalog`, `get_service`, `trace_relations`) วน loop จนได้คำตอบ — เป็น tool ชุดเดียวกับที่ AI ภายนอกใช้ผ่าน MCP
- Case (ข้อ 8) ถูก index เข้า RAG ด้วย — ค้นด้วยอาการ/error message แบบหลวม ๆ ได้

## 8. Case Knowledge Base

เก็บ case จากการไล่ปัญหา monitor ที่ทำเสร็จแล้ว เพื่อ (1) ให้ AI รู้ทางลัดรอบหน้า (2) เป็น issue data สำหรับตัดสินใจแก้ถาวร

**Entity `Case`:** อาการ / error message, ระบบที่เกิด (link เข้า graph: service, endpoint), ขั้นตอนที่ใช้ตามหา (query Seq อะไร, trace ไหน), root cause, วิธีแก้ (ชั่วคราว/ถาวร), สถานะ (`open / recurring / fixed-permanently`), occurrences (จำนวนครั้ง + วันที่)

**Flow:** ไล่ปัญหาจบ → user สั่งเก็บ → Claude เรียก `save_case` / รอบหน้า skill การหา error มีขั้นแรกเป็น `search_cases` เสมอ — เจอ case เดิมซ้ำให้บันทึก occurrence เพิ่ม ไม่สร้างใหม่ / UI มีหน้า issue board เรียงตามความถี่

## 9. MCP Tools (ชุดแรก)

| กลุ่ม | Tools |
|---|---|
| Catalog | `search_catalog` (RAG), `get_service`, `list_endpoints`, `trace_relations`, `get_table_info`, `get_appsettings` |
| Ingest | `get_scan_instructions`, `push_scan` |
| Monitoring (production) | `query_seq` (เลือก zone — รองรับ scenario ตาม error ข้าม Seq product → Seq core), `search_traces` / `get_trace` (Jaeger), `get_pod_status` / `get_pod_logs` (OpenShift ผ่าน oc ของ user, ใช้ DeployGroup map ว่า service อยู่ pod ไหน) |
| Case | `search_cases`, `save_case` |

MCP server อยู่ที่ client → auth จุดเดียว (PAT) ใช้ได้กับ AI ทุกตัวที่รองรับ MCP

## 10. UI หลัก (Angular 22 + PrimeNG)

- Graph explorer — ไล่เส้นทาง call ทั้ง framework
- Service detail / Endpoint browser + search
- DB catalog / Config / AppSettings (แยก environment)
- Monitoring — log/trace/pod ผ่าน client
- Issue board (case knowledge base)
- AI search (chat กับ RAG)
- Admin — เชิญ user, จัด role, แก้ scan skill, ดู audit log, ตรวจสถานะ client

## 11. ลำดับการสร้าง (Phases)

1. **Foundation** — Postgres schema, .NET 10 API, Microsoft login + invite + roles, Angular shell + CRUD catalog พื้นฐาน
2. **Ingestion** — client + MCP (`get_scan_instructions`, `push_scan`) + scan skill → เทข้อมูล core + product แรก (~30 services) + graph explorer UI
3. **Monitoring** — MCP tools ฝั่งอ่าน + หน้า monitor (Seq / Jaeger / OpenShift, production เท่านั้น) + case knowledge base
4. **RAG** — index + AI search ใน UI + เปิด `search_catalog` ให้ MCP

เหตุผล: จบ phase 2 ระบบมีมูลค่าทันที (ตอบ "เส้นนี้ใครเป็นเจ้าของ ใครเรียกบ้าง" ได้) ก่อนลงทุนกับ monitoring และ AI

## 12. Open questions

- ~~Jaeger production expose ผ่านอะไร~~ → **ตอบแล้ว: เปิดโล่ง internal network ไม่มี auth**
- ~~รายละเอียด OpenShift~~ → **ตอบแล้ว: ผ่าน `oc` CLI ของ user, handle เคสไม่ได้ลง/ไม่ได้ login**
- ~~รูปแบบ repo จริง~~ → **ตอบแล้ว: ดู "Conventions ที่พบจาก repo ตัวอย่างจริง" ในข้อ 2**
- ส่วนอื่นที่ user อาจนึกออกเพิ่มในอนาคต

## 13. ขั้นต่อไป

ร่าง **database schema ฉบับเต็ม** (ตาราง + ความสัมพันธ์: catalog graph, case, appsettings, user/role, audit) และ **โครง solution** (server API, client, shared contracts, Angular workspace) ให้ review ก่อนเริ่ม code

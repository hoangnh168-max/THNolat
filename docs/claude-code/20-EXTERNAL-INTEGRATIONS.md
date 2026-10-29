# External Integrations Architecture Investigation

## Overview

This document provides a comprehensive analysis of OpenOLAT's external integration mechanisms, covering LTI 1.3, Basic LTI (1.0/1.1), SCORM 1.2/2004, and QTI 2.1. It includes end-to-end traces, security analysis, and an evaluation of four integration approaches for the fLMS PIX simulator.

---

## 1. Integration Mechanisms Discovery

### 1.1 LTI 1.3 (Learning Tools Interoperability)

**Package:** `org.olat.ims.lti13`
**Dispatcher:** `LTI13Dispatcher` (servlet at `/lti`)
**Modes:** OpenOLAT acts as **Platform** (launching external tools) and **Tool** (being launched by external LMS)

#### Key Components:
- `LTI13Module` - Configuration (enabled, platform ISS, deployment roles, role mapping)
- `LTI13Dispatcher` - Servlet dispatcher routing to platform/tool delegates
- `LTI13ToolDispatcherDelegate` - Tool mode: OIDC login initiation, ID token validation
- `LTI13PlatformDispatcherDelegate` - Platform mode: Authorization, JWT generation with claims
- `LTI13Tool` / `LTI13ToolDeployment` / `LTI13Context` - Deployment configuration entities
- Key resolvers: `LTI13ToolSigningKeyResolver`, `LTI13PlatformSigningPrivateKeyResolver`, `LTI13SharedToolSigningKeyResolver`

#### Supported LTI 1.3 Services:
- **OIDC/OAuth2** - Authentication flow
- **NRPS** (Names and Roles Provisioning Service) - Membership sync
- **AGS** (Assignment and Grading Service) - Grade passback (lineitems, scores, results)
- **Deep Linking** - Content item selection
- **Custom Claims** - OpenOLAT extensions (`OpenOlatClaims`)

---

### 1.2 Basic LTI (LTI 1.0/1.1)

**Package:** `org.olat.ims.lti`, `org.olat.course.nodes.basiclti`
**Course Node:** `BasicLTICourseNode`
**Run Controllers:** `LTIRunSegmentController` → `LTIRunController` → `LTI10DisplayController` or `LTI13DisplayController`

#### Key Components:
- `LTIManager` - OAuth 1.0a signing, launch data generation
- `LTIConfigForm` - Unified configuration for both LTI 1.1 and 1.3
- `CourseNodeOutcomeMapper` - Outcome service for grade passback
- `PostDataMapper` / `TalkBackMapper` - Launch delivery mappers
- `LTIAssessmentConfig` / `LTIAssessmentHandler` - Assessment configuration

#### Security:
- OAuth 1.0a with consumer key/secret
- Shared secret stored in course node configuration
- Nonce validation for replay protection (via `LTIManager`)

---

### 1.3 SCORM (1.2 and 2004)

**Package:** `org.olat.modules.scorm`, `org.olat.course.nodes.scorm`
**Course Node:** `ScormCourseNode`
**Core Runtime:** `ScormWrapperController` → `ScormAPIandDisplayController` → `ScormSessionController`

#### Key Components:
- `ScormMainManager` - Package configuration management (XStream)
- `ScormWrapperController` - Sandboxed delivery via `ControllerDeliveryMapper`
- `ScormAPIandDisplayController` - SCORM RTE (LMSInitialize/LMSFinish/LMSTimeout, CMI data)
- `ScormSessionController` - CMI data model persistence, score/status tracking
- `SettingsHandler` - Package settings, storage paths
- `ScormManager` - Manifest parsing, sequencing (SCORM 2004)

#### Delivery Isolation:
- **Sandboxed Mappers** (`ControllerDeliveryMapper` + `SandboxedMapper`)
- **Content Domain** separation when `Settings.isContentDomainNameEnabled()`
- Token-based access (`?token=<mapper-token>`)
- No REST access, relaxed framing headers for iframe delivery

---

### 1.4 QTI 2.1 (Assessment Integration)

**Package:** `org.olat.ims.qti21`
**Repository Handler:** `QTI21AssessmentTestHandler` (type: `imsqti_test_xmlv2p1`)
**Runtime:** `AssessmentTestDisplayController` + `TestSessionController` (JQTI+)

#### Key Components:
- `QTI21Module` - Configuration (digital signatures, correction workflows)
- `QTI21Service` - Package resolution, session management, scoring
- `QTI21ContentPackage` - IMS Content Package parsing (`imsmanifest.xml`)
- `AssessmentTestSession` / `AssessmentItemSession` - JPA entities
- `QTI21DeliveryOptions` - Test delivery configuration (formative/summative profiles)

#### External Exchange:
- **QTI XML Import/Export** - Standard IMS QTI 2.1 packages
- **Content Packaging** - IMS CP with QTI resources
- **Digital Signatures** - XML-DSig for assessment results
- **Outcomes Listener** - Integration with assessment service

---

### 1.5 External Tools & Grade Sync

#### LTI 1.3 AGS (Assignment and Grading Service):
- **LineItems** - Grade columns managed by OpenOLAT
- **Scores** - POST `/lineitems/{id}/scores` from tool to platform
- **Results** - GET `/lineitems/{id}/results` for grade retrieval
- **Scope:** `https://purl.imsglobal.org/spec/lti-ags/scope/lineitem`, `score`, `result.readonly`

#### Basic LTI Outcome Service:
- **LIS Outcome Management Service** - OAuth-signed POST to `lis_outcome_service_url`
- **Score Passback** - `replaceResult` operation with `score` element

#### SCORM Assessment:
- **Score/Status** - `cmi.core.score.raw`, `cmi.core.lesson_status`
- **Aggregation** - Sum of SCO scores or "all passed" logic
- **Course Assessment Integration** - `CourseAssessmentService` via `ScoreEvaluation`

---

### 1.6 Event Interfaces

#### EventBus (Cluster-wide):
- `LTI13ChooseResourceEvent` - Deep linking content selection
- `AssessmentSessionAuditEvent` - QTI audit logging
- `MultiUserEvent` - Cross-session notifications

#### Internal Events:
- `Event.DONE_EVENT` / `Event.CANCELLED_EVENT` - Controller lifecycle
- `StepsEvent.ACTIVATE_NEXT` - Wizard navigation
- `FormEvent.ONCHANGE` - Form field changes

---

## 2. LTI End-to-End Trace

### 2.1 Platform Mode (OpenOLAT launches external tool)

```
1. User clicks LTI course element
   └─ BasicLTICourseNode → LTIRunSegmentController → LTIRunController

2. LTIRunController.prepareLaunch()
   ├─ Creates LTI13Context (deployment, tool, target URL)
   ├─ Generates login_hint JWT (contextKey, deploymentKey, contentItemKey)
   ├─ Redirects to /lti/authorization with login_hint, lti_message_hint

3. LTI13Dispatcher → LTI13PlatformDispatcherDelegate.handleAuthorization()
   ├─ Validates login_hint (signed by platform private key)
   ├─ Verifies redirect_uri against tool's registered redirect URLs
   ├─ Generates id_token JWT with claims:
   │   ├─ iss: platform ISS (lti13.platform.iss)
   │   ├─ aud: tool client_id
   │   ├─ sub: hashed user ID (lti13Service.subIdentity())
   │   ├─ nonce: from request (replay protection)
   │   ├─ message_type: LtiResourceLinkRequest
   │   ├─ roles: Instructor/Learner based on course role
   │   ├─ context: course/group context (id, label, type)
   │   ├─ resource_link: id, title, description
   │   ├─ launch_presentation: iframe/window, dimensions
   │   ├─ custom: user props, course info, custom attributes
   │   ├─ NRPS endpoint: /lti/nrps/{contextId}/memberships/
   │   └─ AGS endpoint: /lti/ags/{contextId}/context/{resourceId}/lineitems/
   ├─ Signs with platform private key (RS256)
   └─ Returns HTML form POST redirect to tool's target URL

4. External Tool validates id_token
   ├─ Fetches platform JWKS from /lti/keyset
   ├─ Verifies signature, iss, aud, exp, nonce
   ├─ Creates local session for user
   └─ Launches tool content in iframe/window

5. Grade Passback (Tool → OpenOLAT)
   ├─ Tool obtains access_token via client_credentials grant (/lti/token)
   ├─ Tool POSTs score to /lti/ags/{contextId}/context/{resourceId}/lineitems/{subIdent}/lineitem/scores
   ├─ LTI13PlatformDispatcherDelegate.handleAgsScore()
   │   ├─ Validates Bearer token (platform private key)
   │   ├─ Loads identity via subIdentity → tool domain mapping
   │   ├─ Calls ltiManager.updateScore(identity, scoreGiven, course, subIdent)
   │   └─ Updates course assessment via CourseAssessmentService
   └─ Returns 200 OK

6. NRPS (Tool → OpenOLAT)
   ├─ Tool GETs /lti/nrps/{contextId}/memberships/
   ├─ LTI13PlatformDispatcherDelegate.handleNrps()
   │   ├─ Validates Bearer token
   │   ├─ Returns MembershipContainer with learners (status=Active, roles=[Learner])
   └─ Tool syncs roster
```

### 2.2 Tool Mode (OpenOLAT launched by external LMS)

```
1. External LMS initiates login
   └─ GET /lti/login_initiation?iss=...&client_id=...&lti_deployment_id=...&target_link_uri=...

2. LTI13Dispatcher → LTI13ToolDispatcherDelegate.handleInitiationLogin()
   ├─ Looks up LTI13Platform by iss + client_id
   ├─ Looks up LTI13SharedToolDeployment by deployment_id + target_link_uri
   ├─ Validates target_link_uri matches deployment's course/group
   ├─ Initiates OIDC auth code flow to platform's authorization endpoint
   ├─ Stores OAuth2 service in cache keyed by state
   └─ Redirects to platform authorization URL

3. Platform redirects back with id_token
   └─ POST /lti/login?id_token=...&state=...

4. LTI13ToolDispatcherDelegate.handleLogin()
   ├─ Retrieves OAuth2 service by state
   ├─ Parses id_token with LTI13SharedToolSigningKeyResolver (platform's JWKS)
   ├─ Validates: signature, iss, aud, exp, nonce (300s clock skew)
   ├─ Validates target_link_uri matches deployment
   ├─ Extracts: deployment_id, context_id, resource_link_id
   ├─ Updates NRPS/AGS service endpoints from claims
   ├─ Matches identity via lti13Service.matchIdentity() (email matching configurable)
   ├─ Determines role from roles claim (Instructor/Mentor → coach, else participant)
   ├─ Checks membership via lti13Service.checkMembership()
   ├─ Logs in user via AuthHelper.doLogin(identity, "LTI", ureq)
   └─ Redirects to target_link_uri?new-window=minimal

5. User interacts with OpenOLAT course content
```

### 2.3 Teacher Configuration UI

**Location:** `LTIConfigForm` (course editor)
**Configuration Options:**
- **LTI Version:** 1.1, 1.3, or external tool template
- **LTI 1.1:** Consumer Key, Shared Secret (password field)
- **LTI 1.3:** Client ID, Deployment ID, Public Key (inline or JWKS URL), Initiate Login URL, Redirect URLs
- **Launch:** Display (iframe/window/fullscreen), dimensions, skip launch page, skip accept page
- **Attributes:** Send name, send email, custom parameters (free text or user properties)
- **Roles:** Author/Coach/Participant → LTI role mapping (Learner, Instructor, Administrator, TeachingAssistant, ContentDeveloper, Mentor)
- **Assessment:** Assessable toggle, scale factor, cut value, include in course assessment, score scaling
- **Deep Linking:** Content item selection via LTI13ChooseResourceController

### 2.4 Logging/Auditing

- `LTI13Constants.QTI21LoggingAction` - LTI launch/grade events
- `AssessmentSessionAuditLogger` - QTI audit (file + OLog)
- `QTI21Constants` - Standard logging actions
- Debug mode in LTI config (`CONFIG_KEY_DEBUG`) logs OAuth signatures

---

## 3. SCORM Trace

### 3.1 Supported Versions
- **SCORM 1.2** - Basic sequencing, CMI data model
- **SCORM 2004 (3rd/4th Edition)** - Advanced sequencing, navigation controls, objectives

### 3.2 Package Import
```
1. Repository import via QTI21AssessmentTestHandler (for QTI) or ScormMainManager (for SCORM)
2. ScormMainManager.importPackage()
   ├─ Unzips to VFS (FileResourceManager.ZIPDIR)
   ├─ Parses imsmanifest.xml via ScormManager
   ├─ Validates SCORM compliance (metadata, organizations, resources)
   ├─ Creates ScormPackageConfig (XStream serialized to VFS)
   └─ Registers as ImsSCORMResource in repository
```

### 3.3 Runtime Launch Sequence
```
1. User accesses SCORM course element
   └─ ScormCourseNode → ScormRunController → ScormWrapperController

2. ScormWrapperController constructor
   ├─ Creates ControllerDeliveryMapper with ControllerDeliveryCreator
   ├─ registerSandboxedMapper(ureq, mapper) → MapperKey with token
   ├─ Determines base URI:
   │   ├─ If content domain enabled: Settings.createContentServerURI()
   │   └─ Else: Settings.createServerURI()
   ├─ Builds launch URL: baseUri + mapperKey.getUrl() + "?token=" + mapperKey.getToken()
   └─ Renders Velocity template with iframe pointing to launch URL

3. Browser requests launch URL
   ├─ SandboxedMapper intercepts (token validated, consumed)
   ├─ ControllerDeliveryMapper invokes ControllerDeliveryCreator
   ├─ Creates ScormAPIandDisplayController
   └─ Delivers SCORM content (HTML/JS) in sandboxed context

4. ScormAPIandDisplayController initialization
   ├─ ScormSessionController.init(cpRoot, repoId, courseId, storagePath, studentId, studentName, ...)
   ├─ Loads CMI data from persistent storage (_olat_score.properties, _olat_lesson_status.properties)
   ├─ Creates ScormManager (manifest parsing, sequencing)
   └─ Renders first SCO in iframe

5. SCORM API Communication (JavaScript → Java)
   ├─ LMSInitialize("") → ScormSessionController.lmsInitialize()
   ├─ LMSGetValue("cmi.core.score.raw") → status.getCmi()
   ├─ LMSSetValue("cmi.core.score.raw", "85") → status.putCmi()
   ├─ LMSCommit("") → ScormSessionController.lmsCommit()
   │   ├─ Updates total time (launch time + session time, capped at 24h)
   │   ├─ Persists CMI to VFS via LMSDataHandler
   │   ├─ Saves score/lesson_status to properties files
   │   └─ If assessable: calculateResults() → CourseAssessmentService.updateScoreEvaluation()
   ├─ LMSFinish("") → ScormSessionController.lmsFinish()
   │   ├─ Implicit commit
   │   ├─ Archives SCO data (ItemSequence.archiveScoData())
   │   └─ Removes launch time tracking
   └─ Navigation (Continue/Previous) → getNextSco()/getPreviousSco()
```

### 3.4 Learner Identity Mapping
- `studentId` = OpenOLAT username
- `studentName` = OpenOLAT display name (first + last)
- Passed via `cmi.core.student_id` and `cmi.core.student_name` (read-only in SERVER_READ_ONLY set)

### 3.5 Score/Status/Progress Persistence
- **Per-SCO Storage:** `_olat_score.properties` (key=SCO ID, value=raw score)
- **Per-SCO Status:** `_olat_lesson_status.properties` (key=SCO ID, value=passed/failed/completed/incomplete/browsed/not attempted)
- **Total Time:** Computed at commit (launch total + session time, capped)
- **Assessment Aggregation:**
  - **Passed-based:** All SCOs must be "passed" → boolean passed
  - **Score-based:** Sum of SCO scores ≥ cut value → numeric score + boolean passed
- **Advanced Score:** Only updates if higher than previous (config: `CONFIG_ADVANCESCORE`)

### 3.6 Attempt Resume
```
1. ScormSessionController.getScormLastAccessedItemId()
   └─ LMSDataHandler "boot" action → returns last accessed SCO ID

2. launchItem(lastScoId, force=false)
   ├─ Loads CMI from persistent storage
   ├─ Restores total_time from launchTotalTimes
   ├─ Sets session_time to 00:00:00
   └─ Resumes from last position
```

### 3.7 Data Retrieval for Reporting
- `getScoItemsStatus()` → Map<SCO ID, status> (not_attempted, incomplete, completed, passed, failed)
- `getScoCmis(scoId)` → String[][] of all CMI elements
- `isItemCompleted(itemId)` → boolean
- `hasItemPrerequisites(itemId)` → boolean (sequencing pre-conditions)
- `archiveScoData(scoId)` → Archives to ZIP for backup/export

---

## 4. QTI/Assessment Integration Trace

### 4.1 Package Import
```
1. RepositoryEntry import via QTI21AssessmentTestHandler.importResource()
   ├─ ImsQTI21Resource.evaluate() validates package (imsmanifest.xml + QTI resources)
   ├─ Copies package to VFS (FileResourceManager.ZIPDIR)
   ├─ Moves QTI21PackageConfig.xml to resource root
   ├─ Creates RepositoryEntry (status=preparation, runtime=embedded)
   └─ Returns entry for course integration
```

### 4.2 Test Delivery (Student)
```
1. IQTESTCourseNode → QTI21AssessmentRunController (participant mode)
   ├─ Creates/Resumes AssessmentTestSession via QTI21Service
   ├─ Loads ResolvedAssessmentTest (cached via QTI21Service)
   ├─ Creates TestSessionController (JQTI+)
   └─ Renders AssessmentTestDisplayController

2. AssessmentTestDisplayController
   ├─ Handles question navigation, response input
   ├─ Auto-save: temporary responses (TestSessionController)
   ├─ Submit: final responses → recordTestAssessmentResult()
   │   ├─ AssessmentResult from JQTI+
   │   ├─ Persists AssessmentTestSession, AssessmentItemSession, AssessmentResponse
   │   ├─ Updates AssessmentEntry via updateAssessmentEntry()
   │   ├─ Digital signature (if enabled)
   │   └─ Fire AssessmentNotificationsHandler
   └─ Results display via AssessmentResultController
```

### 4.3 External Assessment Exchange
- **Import:** QTI 2.1 XML packages (imsmanifest.xml + assessmentTest.xml + assessmentItems)
- **Export:** QTI21Service → QtiSerializer → IMS CP package
- **Digital Signatures:** XML-DSig on assessment results (certificate config in QTI21Module)
- **Correction Workflow:** Anonymous or named (config: `qti21.correction.workflow`)
- **Statistics:** QTI21StatisticsManager (item/test statistics, exports)

---

## 5. Security and Permissions Analysis

### 5.1 Tool Trust & Registration

| Mechanism | Trust Establishment | Registration |
|-----------|---------------------|--------------|
| **LTI 1.3 Platform** | Platform private key signs id_token; Tool validates via JWKS | Admin configures Tool (client_id, public key/JWKS URL, redirect URLs) |
| **LTI 1.3 Tool** | Tool validates platform's id_token via platform JWKS | Admin configures SharedToolDeployment (deployment_id, target_link_uri) |
| **Basic LTI** | Shared secret (consumer key/secret) | Course owner enters key/secret in course element config |
| **SCORM** | No external trust - content runs in OpenOLAT sandbox | Author uploads package; no external authentication |
| **QTI** | Internal - no external trust | Author creates/imports test in repository |

### 5.2 Identity & Role Mapping

#### LTI 1.3 Platform → Tool:
```java
// LTI13PlatformDispatcherDelegate.appendRolesClaim()
courseAdmin → editorToRoleV2(authorRolesList)  // e.g., Instructor, Administrator
coach       → editorToRoleV2(coachRolesList)    // e.g., TeachingAssistant, Mentor
participant → editorToRoleV2(participantRolesList) // e.g., Learner
```

#### LTI 1.3 Tool → Platform:
```java
// LTI13ToolDispatcherDelegate.getRolesFromClaims()
roles claim contains Instructor/Mentor/InstitutionInstructor → GroupRoles.coach
otherwise → GroupRoles.participant
```

#### Identity Matching (Tool Mode):
- Config: `lti13.platform.matching.by.email` (enabled/disabled)
- `lti13Service.matchIdentity()` - matches by email or subject claim
- Falls back to sub claim hashing: `lti13Service.subIdentity(identity, toolDomain)`

### 5.3 Launch Authentication

| Mechanism | Auth Method | Replay Protection |
|-----------|-------------|-------------------|
| **LTI 1.3** | OIDC ID Token (JWT, RS256) | `nonce` claim (validated with 300s clock skew), `state` parameter |
| **Basic LTI** | OAuth 1.0a signed POST | `oauth_nonce` + timestamp (LTIManager validates) |
| **SCORM** | Session cookie + sandbox token | Token consumed on first use (SandboxedMapper.consumeToken()) |
| **QTI** | OpenOLAT session | Standard session authentication |

### 5.4 Secret Storage

| Secret Type | Storage Location | Protection |
|-------------|------------------|------------|
| LTI 1.3 Platform Private Key | `LTI13KeyImpl` (DB, `o_lti13_key`) | PKCS#8, encrypted at rest via DB |
| LTI 1.3 Tool Public Key | `LTI13ToolImpl` (DB, `o_lti13_tool`) | JWKS or inline PEM |
| LTI 1.1 Consumer Secret | `ModuleConfiguration` (course node) | DB (`o_course_config`), not encrypted |
| SCORM | None (no secrets) | N/A |
| QTI Digital Signature Cert | `QTI21Module` (file in userdata/system/configuration) | File system permissions |

### 5.5 Course/Result Permissions

#### LTI 1.3 Deployment Permissions (LTI13Module):
```java
// Repository Entry Deployment
isAllowedToDeploy(roles, entry):
  - Admin/LearnResourceManager → always allowed (if in allowed roles config)
  - Author → if deploymentRepositoryEntryOwnerPermission == allResources
             OR (perResource AND entry.isLTI13DeploymentByOwnerWithAuthorRightsEnabled())

// Business Group Deployment  
isAllowedToDeploy(roles, group):
  - Admin/GroupManager → always allowed (if in allowed roles config)
  - Author → if deploymentBusinessGroupCoachPermission == allResources
             OR (perResource AND group.isLTI13DeploymentByCoachWithAuthorRightsEnabled())
```

#### Basic LTI:
- Course element permissions via standard course node access (NodeAccessService)
- Grade write via `CourseAssessmentService` (requires coach/author rights)

#### SCORM:
- Course element permissions via standard course node access
- Score write via `CourseAssessmentService` (assessment config on course node)

#### QTI:
- Test delivery: participant role in course
- Correction: coach/author role (correction workflow config)
- Results visibility: config `qti21.results.visible.after.correction`

### 5.6 Replay Protection

| Mechanism | Implementation |
|-----------|----------------|
| **LTI 1.3** | `nonce` in id_token (validated once, 300s clock skew), `state` in OIDC flow |
| **Basic LTI** | `oauth_nonce` + `oauth_timestamp` (LTIManager nonce store, 5 min window) |
| **SCORM** | SandboxedMapper token consumed on first request |
| **QTI** | Session-bound; TestSessionController prevents duplicate submission |

### 5.7 Content Isolation

| Mechanism | Isolation Technique |
|-----------|---------------------|
| **LTI 1.3 Tool Launch** | Iframe/window launch; `launch_presentation.document_target`; no shared cookies (cross-origin) |
| **LTI 1.3 Platform Services** | Bearer token auth (JWT); scope-limited (AGS/NRPS); context-bound endpoints |
| **Basic LTI** | Iframe launch; OAuth-signed launch data; outcome service callback URL validation |
| **SCORM** | **SandboxedMapper** + **Content Domain** (separate hostname); token-gated; no REST access; relaxed `X-Frame-Options` |
| **QTI** | Internal delivery; no external content |

#### SCORM Sandboxed Delivery Details:
```java
// ScormWrapperController
ControllerDeliveryMapper mapper = new ControllerDeliveryMapper(wControl, creator);
MapperKey mapperKey = registerSandboxedMapper(ureq, mapper);  // Creates SandboxedMapper
String baseUri = Settings.isContentDomainNameEnabled() 
    ? Settings.createContentServerURI()  // e.g., content.openolat.org
    : Settings.createServerURI();         // e.g., openolat.org
// Launch URL: baseUri + mapperKey.getUrl() + "?token=" + mapperKey.getToken()
```

- **Content Domain:** Separate DNS name (`contentDomainName ≠ domainName`)
- **Token:** Single-use, consumed on first request
- **No REST Access:** Sandboxed session lacks REST API permissions
- **Framing:** Relaxed headers for iframe embedding

### 5.8 Audit Capabilities

| Mechanism | Audit Log |
|-----------|-----------|
| **LTI 1.3** | `o_lti13_audit_log` (via EventBus), launch/grade events |
| **Basic LTI** | Standard OLAT logging (Tracing), OAuth signatures in debug mode |
| **SCORM** | `ScormSessionController` debug logs (CMI commits, score calculations) |
| **QTI** | `AssessmentSessionAuditLogger` → file (`o_olat_assessment_audit`) + OLog (`o_o_log`) |
| **All** | `o_api_audit_log` for REST API calls |

---

## 6. fLMS PIX Simulator Integration Comparison

The fLMS PIX simulator requires: **interactive coding environment**, **real-time assessment**, **competency tracking**, **score/grade passback**, **learner identity**, **attempt management**.

### Comparison Matrix

| Criterion | **A: LTI 1.3 External Tool** | **B: SCORM Package** | **C: Native Course Element** | **D: Custom REST API** |
|-----------|------------------------------|----------------------|------------------------------|------------------------|
| **Integration Complexity** | Medium (LTI 1.3 config, AGS/NRPS) | Low (standard SCORM package) | High (full controller development) | High (new REST endpoints, auth) |
| **Development Effort** | External tool development | SCORM package authoring | Full Java/Velocity development | Full REST + frontend development |
| **Real-time Interaction** | ✅ Full bidirectional (iframe + postMessage) | ⚠️ Limited (SCORM API only) | ✅ Full (native server-side) | ✅ Full (WebSocket/REST) |
| **Grade Passback** | ✅ AGS (standard, rich) | ✅ Basic (score/status only) | ✅ Native (CourseAssessmentService) | ✅ Custom endpoints |
| **Competency Tracking** | ✅ Custom claims + AGS lineitems | ❌ Not in SCORM 1.2/2004 | ✅ Native (CurriculumLearningProgress) | ✅ Custom data model |
| **Attempt Management** | ✅ Tool-controlled + NRPS roster | ✅ SCORM suspend/resume | ✅ Native (assessment attempts) | ✅ Custom logic |
| **Learner Identity** | ✅ Full (sub, email, name, roles) | ✅ Basic (student_id, name) | ✅ Full (Identity, roles, groups) | ✅ Full (token-authenticated) |
| **Content Isolation** | ✅ Cross-origin iframe | ✅ Sandboxed mapper + content domain | ✅ Native (same origin) | ⚠️ CORS/config required |
| **Security** | ✅ OIDC/OAuth2, JWT, scopes | ✅ Sandboxed, no external auth | ✅ Native authZ | ⚠️ Custom auth needed |
| **Standard Compliance** | ✅ LTI 1.3 Core, AGS, NRPS, DL | ✅ SCORM 1.2/2004 certified | N/A (proprietary) | N/A (proprietary) |
| **Portability** | ✅ Runs on any LTI 1.3 platform | ✅ Runs on any SCORM LMS | ❌ OpenOLAT only | ❌ OpenOLAT only |
| **Maintenance** | External tool maintained separately | SCORM package updated separately | Core codebase | Custom API maintained separately |
| **User Experience** | Seamless iframe launch | Seamless iframe launch | Native UI | Custom UI (may differ) |
| **Offline Support** | ❌ Requires platform connection | ✅ SCORM packages can work offline* | ❌ Requires server | ❌ Requires server |
| **Analytics/Reporting** | Via AGS + platform reports | SCORM CMI data + OpenOLAT reports | Full OpenOLAT analytics | Custom analytics |
| **PIX Simulator Fit** | ⭐⭐⭐⭐⭐ Best for external tool | ⭐⭐ Limited interactivity | ⭐⭐⭐⭐⭐ Best for native | ⭐⭐⭐ Good for headless |

*SCORM offline requires special packaging and LMS support.

### Detailed Analysis per Approach

#### Approach A: LTI 1.3 External Tool (Recommended for External PIX Simulator)
**Pros:**
- Industry standard - PIX simulator can be used in any LTI 1.3 LMS
- Rich grade passback via AGS (multiple lineitems, scores, results)
- NRPS for roster sync
- Deep Linking for content selection
- Secure OIDC/OAuth2 with scopes
- Content isolation via cross-origin iframe
- OpenOLAT as platform: minimal code changes (configuration only)

**Cons:**
- Requires developing/maintaining external PIX tool
- Network latency for iframe communication
- Complex LTI 1.3 implementation on tool side
- AGS requires tool to implement OAuth2 client credentials flow

**Implementation:**
1. Develop PIX simulator as LTI 1.3 tool (Node.js, Python, Java, etc.)
2. Register in OpenOLAT: Admin → LTI 1.3 → Tools → New External Tool
3. Configure: Client ID, Public Key/JWKS, Redirect URLs, Initiate Login URL
4. Add LTI course element, select tool, configure roles/assessment
5. Enable AGS in deployment for grade passback

#### Approach B: SCORM Package (Not Recommended for PIX)
**Pros:**
- Standard packaging
- Works offline (theoretically)
- Sandboxed delivery built-in
- Simple import process

**Cons:**
- **SCORM API is too limited** for interactive coding simulator
- No real-time communication (only GetValue/SetValue/Commit)
- No competency tracking in data model
- No rich grading (only score + status)
- SCORM 2004 sequencing complex, limited adoption
- JavaScript-only API - no server-side logic during session
- Difficult to implement real-time code execution/validation

**Verdict:** SCORM is designed for self-paced content, not interactive simulators.

#### Approach C: Native Course Element (Recommended for Native PIX Simulator)
**Pros:**
- Full access to OpenOLAT internals (services, DB, EventBus)
- Native competency tracking (CurriculumLearningProgress)
- Direct assessment integration (CourseAssessmentService)
- Single codebase, no network boundary
- Best performance (no iframe overhead)
- Full UI consistency
- Leverages existing course element patterns

**Cons:**
- OpenOLAT-specific (not portable)
- Requires Java/Velocity development
- Must follow OpenOLAT controller patterns
- Longer initial development

**Implementation Pattern:**
```java
// 1. Course Node
public class PIXCourseNode extends AbstractAccessableCourseNode { ... }

// 2. Edit Controller (config)
public class PIXEditController extends FormBasicController { ... }

// 3. Run Controller (participant)
public class PIXRunController extends BasicController {
    // Uses PIXSessionController for state
    // Integrates with CourseAssessmentService
    // Uses CurriculumService for competencies
}

// 4. Session Controller (state)
public class PIXSessionController {
    // Manages attempt, code execution, scoring
    // Persists to VFS/DB
}
```

**Key Extension Points:**
- `CourseNode` → `AbstractAccessableCourseNode`
- `CourseNodeRunController` → `BasicController` + `listenTo()`
- Assessment: `AssessmentConfig`, `CourseAssessmentService.updateScoreEvaluation()`
- Competencies: `CurriculumService`, `CurriculumLearningProgress`
- VFS: `VFSManager` for code artifacts
- EventBus: `MultiUserEvent` for real-time updates

#### Approach D: Custom REST API (For Headless/SPA Integration)
**Pros:**
- Technology-agnostic frontend (React, Vue, mobile)
- Can serve multiple consumers
- Standard REST patterns
- OpenAPI/Swagger documentation

**Cons:**
- Requires custom authentication (token, API key)
- No standard grade passback (custom integration needed)
- CORS/content domain configuration
- Duplicates controller logic
- No native course element UX

**Implementation:**
1. Create JAX-RS resource: `PIXWebservice` (extends `RestController`)
2. Endpoints: `POST /pix/sessions`, `POST /pix/sessions/{id}/execute`, `GET /pix/sessions/{id}/result`
3. Auth: Bearer token (LTI 1.3 AGS token or custom API key)
4. Frontend: Embedded via iframe or LTI launch with custom parameters
5. Grade sync: Custom REST endpoint called by frontend or LTI AGS

---

## 7. Recommendations

### For fLMS PIX Simulator:

| Scenario | Recommended Approach |
|----------|---------------------|
| **PIX simulator is external product** (used in multiple LMSs) | **A: LTI 1.3 External Tool** |
| **PIX simulator is fLMS-specific, deep integration needed** | **C: Native Course Element** |
| **PIX simulator needs React/Vue frontend, headless backend** | **D: Custom REST API + LTI launch** |
| **Quick prototype, minimal interactivity** | **B: SCORM** (not recommended for production) |

### Architecture Decision Factors:
1. **Portability requirement** → LTI 1.3
2. **Deep OpenOLAT integration** (competencies, curriculum, groups) → Native
3. **Modern SPA frontend** → REST API + LTI launch
4. **Team expertise** (Java vs external stack) → Native vs LTI tool
5. **Maintenance ownership** (frentix vs external vendor) → Native vs LTI tool

---

## 8. Key Source Files Reference

### LTI 1.3
- `org.olat.ims.lti13.LTI13Module` - Configuration
- `org.olat.ims.lti13.LTI13Dispatcher` - Servlet dispatcher
- `org.olat.ims.lti13.LTI13ToolDispatcherDelegate` - Tool mode
- `org.olat.ims.lti13.LTI13PlatformDispatcherDelegate` - Platform mode
- `org.olat.ims.lti13.LTI13ToolDeployment` - Deployment config
- `org.olat.ims.lti13.manager.LTI13ToolSigningKeyResolver` - JWT validation
- `org.olat.course.nodes.basiclti.LTIConfigForm` - Unified config UI

### Basic LTI
- `org.olat.ims.lti.LTIManager` - OAuth 1.0a signing
- `org.olat.course.nodes.basiclti.BasicLTICourseNode` - Course node
- `org.olat.course.nodes.basiclti.LTIRunController` - Launch controller
- `org.olat.course.nodes.basiclti.LTI10DisplayController` - LTI 1.1 launch

### SCORM
- `org.olat.modules.scorm.ScormMainManager` - Package management
- `org.olat.modules.scorm.ScormWrapperController` - Sandboxed delivery
- `org.olat.modules.scorm.ScormAPIandDisplayController` - RTE
- `org.olat.modules.scorm.ScormSessionController` - CMI persistence
- `org.olat.course.nodes.scorm.ScormCourseNode` - Course node

### QTI 2.1
- `org.olat.ims.qti21.QTI21Module` - Configuration
- `org.olat.ims.qti21.QTI21Service` - Service interface
- `org.olat.ims.qti21.QTI21ContentPackage` - Package parsing
- `org.olat.ims.qti21.repository.handlers.QTI21AssessmentTestHandler` - Repository handler
- `org.olat.ims.qti21.ui.AssessmentTestDisplayController` - Test delivery

### Security/Isolation
- `org.olat.core.dispatcher.mapper.manager.SandboxedMapper` - Sandbox wrapper
- `org.olat.core.dispatcher.mapper.sandbox.ControllerDeliveryMapper` - SCORM delivery
- `org.olat.core.helpers.Settings` - Content domain config (`isContentDomainNameEnabled()`)

---

## 9. Update Investigation Ledger

**Phase 5.3 - External Integrations Architecture Investigation: COMPLETED**

- ✅ Baseline established (repository, git status, prior docs)
- ✅ Integration mechanisms discovered (LTI 1.3, Basic LTI, SCORM, QTI)
- ✅ LTI end-to-end traced (registration, launch, auth, validation, grade passback, completion sync, teacher config, logging)
- ✅ SCORM traced (versions, import, launch, runtime comm, identity, score/status/progress, attempt resume, data retrieval)
- ✅ QTI/assessment integration traced (import, delivery, external exchange)
- ✅ Security/permissions analyzed (trust, identity mapping, auth, secrets, permissions, replay, isolation, audit)
- ✅ Four integration approaches evaluated for fLMS PIX simulator
- ✅ 20-EXTERNAL-INTEGRATIONS.md created
- ✅ Investigation ledger updated

**Next Phase:** Phase 6 - Extension-point analysis for fLMS customization requirements
# OpenOLAT REST API Architecture and Endpoint Investigation

## Phase 5.2 — REST API Architecture and Endpoint Investigation

**Date:** 2026-10-22  
**Commit:** 20e0b6b2f15333d3c785cce0e670ab5bd6b6c828  
**Branch:** master  
**Version:** 21.2-SNAPSHOT  
**Module Location:** `src/main/java/org/olat/restapi/`

---

## 1. Baseline Establishment

### 1.1 Repository State
- **Commit:** 20e0b6b2f15333d3c785cce0e670ab5bd6b6c828 (Merge remote-tracking branch 'origin/OpenOLAT_21.1')
- **Branch:** master
- **Version:** 21.2-SNAPSHOT (from pom.xml)
- **REST Module Root:** `src/main/java/org/olat/restapi/`

### 1.2 Module Structure
```
org.olat.restapi/
├── RestModule.java                    # Configuration module (enabled, auth, audit, rate limit)
├── RestApiModule.java                 # Spring module configuration
├── support/
│   ├── OlatRestApplication.java       # JAX-RS Application (CXF)
│   ├── RestRegistrationService.java   # Dynamic resource registration
│   ├── RestRegistrationServiceImpl.java
│   ├── MediaTypeVariants.java         # Pagination, ETag support
│   ├── MultipartReader.java           # Multipart form data parsing
│   └── vo/                            # Value Objects (CourseVO, UserVO, etc.)
├── security/
│   ├── RestApiLoginFilter.java        # Main authentication filter (1000+ lines)
│   ├── RestApiAuthenticationProvider.java
│   ├── RestSecurityHelper.java        # Helper constants & permission checks
│   └── RestSecurityBeanImpl.java      # Token management (DB + in-memory cache)
├── repository/
│   ├── RepositoryEntriesWebService.java
│   ├── RepositoryEntryWebService.java
│   └── course/
│       ├── CoursesWebService.java
│       ├── CourseWebService.java
│       ├── CourseGroupWebService.java
│       ├── CourseRightsWebService.java
│       └── CourseAssessmentWebService.java
├── user/restapi/
│   ├── UserWebService.java
│   ├── UserCoursesWebService.java
│   ├── UserFoldersWebService.java
│   └── GroupWebService.java
├── group/
│   ├── LearningGroupWebService.java
│   └── MyGroupWebService.java
├── core/commons/services/vfs/restapi/
│   └── VFSWebservice.java
└── modules/
    ├── curriculum/restapi/
    │   ├── CurriculumsWebService.java
    │   └── CurriculumElementsWebService.java
    └── taxonomy/restapi/
        ├── TaxonomyModuleWebService.java
        └── TaxonomyWebService.java
```

---

## 2. REST Architecture Discovery

### 2.1 Framework Stack
- **JAX-RS Implementation:** Apache CXF (configured in `restApiContext.xml`)
- **JSON/XML Serialization:** Jackson (via `JacksonJsonProvider`, `JacksonJaxbJsonProvider`)
- **Dependency Injection:** Spring 7 (`@Autowired` on `@Component` web services)
- **API Documentation:** OpenAPI/Swagger v3 annotations (`io.swagger.v3.oas.annotations`)
- **Validation:** Bean Validation (JSR-380) via `ValidationFeature`

### 2.2 CXF Configuration (`restApiContext.xml`)
```xml
<jaxrs:server id="restServer" address="/">
    <jaxrs:serviceBeans>
        <ref bean="repositoryEntriesWebService"/>
        <ref bean="userWebService"/>
        <!-- ... other services -->
    </jaxrs:serviceBeans>
    <jaxrs:providers>
        <bean class="org.apache.cxf.jaxrs.provider.jsrjsonp.JsonProcessingProvider"/>
        <bean class="org.olat.restapi.support.JacksonJsonProvider"/>
        <bean class="org.apache.cxf.jaxrs.provider.JAXBElementProvider"/>
        <bean class="org.apache.cxf.jaxrs.openapi.OpenApiFeature"/>
    </jaxrs:providers>
    <jaxrs:features>
        <bean class="org.apache.cxf.jaxrs.openapi.OpenApiFeature">
            <property name="prettyPrint" value="true"/>
            <property name="contact" value="frentix GmbH"/>
            <property name="title" value="OpenOLAT REST API"/>
            <property name="version" value="1.0"/>
        </bean>
        <bean class="org.apache.cxf.validation.BeanValidationFeature"/>
    </jaxrs:features>
    <jaxrs:properties>
        <entry key="javax.ws.rs.errorhandler" value-ref="restExceptionMapper"/>
    </jaxrs:properties>
</jaxrs:server>
```

### 2.3 Provider Chain (Request/Response)
1. **Request Filter:** `RestApiLoginFilter` (authentication, rate limiting, audit setup)
2. **CXF Inbound Interceptors:** Read entity, deserialize via Jackson
3. **Validation:** Bean Validation on parameters
4. **Resource Method:** Executes business logic
5. **CXF Outbound Interceptors:** Serialize via Jackson (JSON/XML)
6. **Response Filter:** Rate limit headers, audit logging completion

### 2.4 Subresource Locator Pattern
Collection resources return **new item service instances** for subresources:
```java
// RepositoryEntriesWebService (collection)
@Path("{repositoryEntryKey}")
public RepositoryEntryWebService getRepositoryEntryWebService(
    @PathParam("repositoryEntryKey") Long repositoryEntryKey) {
    RepositoryEntry re = repositoryManager.lookupRepositoryEntry(repositoryEntryKey);
    return new RepositoryEntryWebService(re);  // NEW instance per request
}

// CoursesWebService (collection) → CourseWebService (item)
@Path("{courseId}")
public CourseWebService getCourse(@PathParam("courseId") Long courseId) {
    ICourse course = loadCourse(courseId);
    CourseWebService ws = new CourseWebService(ores, course);
    CoreSpringFactory.autowireObject(ws);  // Inject @Autowired dependencies
    return ws;
}
```

**Benefits:** Each subresource instance is request-scoped, can hold state (`this.course`), and receives Spring DI.

---

## 3. REST Endpoints Inventory by Domain

### 3.1 Repository & Course Domain (`/restapi/repo/`)

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/repo/repositoryentries` | GET | Search repository entries (paginated) | Session/Token/Basic |
| `/repo/repositoryentries` | POST | Import repository entry (multipart) | Author+ |
| `/repo/repositoryentries/{key}` | GET | Get repository entry details | Session/Token/Basic |
| `/repo/repositoryentries/{key}` | PUT | Update repository entry | Manager |
| `/repo/repositoryentries/{key}` | DELETE | Delete repository entry | Manager |
| `/repo/repositoryentries/{key}/metadata` | GET | Get metadata (educational type, lifecycle) | Author+ |
| `/repo/repositoryentries/{key}/metadata` | PUT/POST | Update metadata | Manager |
| `/repo/repositoryentries/{key}/groups` | GET | Get course groups | Manager |
| `/repo/repositoryentries/{key}/groups` | POST | Create group | Manager |
| `/repo/repositoryentries/{key}/curriculum` | GET | Get curriculum | Manager |
| `/repo/repositoryentries/{key}/assessmentmodes` | GET/POST | Assessment modes | Manager |
| `/repo/courses` | GET | List courses (paginated, filterable) | Session/Token/Basic |
| `/repo/courses` | PUT/POST | Create/import course | Author+ |
| `/repo/courses/{courseId}` | GET | Get course details | Accessible check |
| `/repo/courses/{courseId}/resource` | GET | Get OLAT resource | Manager |
| `/repo/courses/{courseId}/image` | GET/HEAD/POST | Teaser image | Manager |
| `/repo/courses/{courseId}/file` | GET | Export course as ZIP | Manager/Author |
| `/repo/courses/{courseId}/publish` | POST | Publish course | Manager |
| `/repo/courses/{courseId}/status` | PUT/POST | Change status | Manager |
| `/repo/courses/{courseId}/configuration` | GET/PUT/POST | Course config | Manager |
| `/repo/courses/{courseId}/runstructure` | GET | Run structure XML | Manager |
| `/repo/courses/{courseId}/editortreemodel` | GET | Editor tree model XML | Manager |
| `/repo/courses/{courseId}/authors` | GET/PUT/POST/DELETE | Course authors/owners | Manager |
| `/repo/courses/{courseId}/tutors` | GET/PUT/POST/DELETE | Course coaches | Manager |
| `/repo/courses/{courseId}/participants` | GET/PUT/POST/DELETE | Course participants | Manager |
| `/repo/courses/{courseId}/organisations` | GET/PUT/DELETE | Course organisations | Manager |
| `/repo/courses/{courseId}/groups` | — | → CourseGroupWebService | Manager |
| `/repo/courses/{courseId}/assessmentmodes` | — | → CourseAssessmentModeWebService | Manager |
| `/repo/courses/{courseId}/calendar` | — | → CalWebService | Session/Token/Basic |
| `/repo/courses/{courseId}/rights` | — | → CourseRightsWebService | Manager |
| `/repo/courses/{courseId}/archives` | — | → CourseArchivesWebService | Manager |
| `/repo/courses/{courseId}/reminders` | — | → RemindersWebService | Manager |
| `/repo/courses/{courseId}/lectureblocks` | — | → LectureBlocksWebService | Manager+ |
| `/repo/courses/{courseId}/absencenotices` | — | → AbsenceNoticesWebService | Manager+ |
| `/repo/courses/{courseId}/invitations` | — | → RepositoryEntryInvitationsWebService | Manager |
| `/repo/courses/{courseId}/vitero/{subId}` | — | → ViteroBookingWebService | Session/Token/Basic |
| `/repo/courses/{courseId}/gotomeeting/{subId}` | — | → GoToTrainingWebService | Session/Token/Basic |
| `/repo/courses/{courseId}/assessments` | GET/POST/PUT | Course assessments | Manager |
| `/repo/courses/{courseId}/db/{category}` | GET/PUT/POST/DELETE | Course DB (key-value) | Session/Token/Basic |

### 3.2 Assessment Domain (`/restapi/repo/courses/{courseId}/assessments`, `/restapi/course/assessment/`)

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/repo/courses/{courseId}/assessments` | GET | All participant results (root node) | Manager |
| `/repo/courses/{courseId}/assessments/users/{identityKey}` | GET | Single participant results | Manager |
| `/repo/courses/{courseId}/assessments/{nodeId}` | GET | All participant results (node) | Manager |
| `/repo/courses/{courseId}/assessments/{nodeId}/users/{identityKey}` | GET | Single participant (node) | Manager |
| `/repo/courses/{courseId}/assessments/{nodeId}` | POST/PUT | Import results for node | Manager |
| `/course/assessment/modes` | GET/POST/PUT/DELETE | Repository-level assessment modes | Admin |
| `/course/assessment/modes/{modeKey}` | GET/PUT/DELETE | Assessment mode by key | Admin |
| `/course/assessment/efficiencystatements` | GET/POST/PUT/DELETE | User efficiency statements | Admin/Coach |

### 3.3 User & Group Domain (`/restapi/user/`, `/restapi/group/`)

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/user` | GET | Search users (paginated) | Admin |
| `/user` | POST | Create user | Admin |
| `/user/{identityKey}` | GET/PUT/DELETE | User CRUD | Admin/Self |
| `/user/{identityKey}/roles` | GET | User roles | Admin |
| `/user/{identityKey}/status` | PUT | Activate/deactivate user | Admin |
| `/user/{identityKey}/preferences` | GET/PUT | User preferences | Admin/Self |
| `/user/{identityKey}/portrait` | GET/POST/DELETE | User portrait image | Admin/Self |
| `/user/{identityKey}/lifecycle` | GET/PUT | User lifecycle | Admin |
| `/user/{identityKey}/username` | PUT | Rename username | Admin |
| `/user/{identityKey}/my/courses` | GET | My courses (participant/coach/owner) | Session/Token/Basic |
| `/user/{identityKey}/folders` | GET/POST | Personal/group/course folders | Session/Token/Basic |
| `/user/{identityKey}/folders/{folderId}` | GET/PUT/DELETE | Folder operations | Session/Token/Basic |
| `/group` | GET | Search groups | Admin/GroupManager |
| `/group` | POST | Create group | Admin/GroupManager |
| `/group/{groupKey}` | GET/PUT/DELETE | Group CRUD | Admin/GroupManager |
| `/group/{groupKey}/tools` | GET/POST/PUT/DELETE | Group tools | Admin/GroupManager |
| `/group/{groupKey}/members` | GET/POST/DELETE | Group members | Admin/GroupManager |
| `/my/groups` | GET | My groups (owner/participant) | Session/Token/Basic |
| `/my/groups/{groupKey}` | GET | Specific group | Session/Token/Basic |

### 3.4 VFS Domain (`/restapi/vfs/` — dynamic mount points)

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/vfs/{containerPath}` | GET | List files/folders | Session/Token/Basic |
| `/vfs/{containerPath}` | POST/PUT | Upload file (multipart/Base64) | Write callback |
| `/vfs/{containerPath}` | PUT (form) | Create folders | Write callback |
| `/vfs/{containerPath}` | DELETE | Delete file/folder | Delete callback |
| `/vfs/metadata/{path}` | GET | File metadata | Read callback |
| `/vfs/version` | GET | Version | Public |

**Security:** Uses `VFSContainer.getLocalSecurityCallback()` for `canRead()`, `canWrite()`, `canDelete()`

### 3.5 Curriculum & Taxonomy Domain (`/restapi/curriculum/`, `/restapi/taxonomy/`)

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/curriculum` | GET/POST | Curriculum list/create | CurriculumManager |
| `/curriculum/{curriculumKey}` | GET/PUT/DELETE | Curriculum CRUD | CurriculumManager |
| `/curriculum/{curriculumKey}/managers` | GET/POST/DELETE | Curriculum managers | CurriculumManager |
| `/curriculum/{curriculumKey}/statistics` | GET | Statistics | CurriculumManager |
| `/curriculum/{curriculumKey}/elements` | GET/POST | Elements list/create | CurriculumManager |
| `/curriculum/{curriculumKey}/elements/{elementKey}` | GET/PUT/DELETE | Element CRUD | CurriculumManager |
| `/curriculum/{curriculumKey}/elements/{elementKey}/children` | GET | Child elements | CurriculumManager |
| `/curriculum/{curriculumKey}/elements/{elementKey}/move` | POST | Reorder element | CurriculumManager |
| `/curriculum/{curriculumKey}/elements/{elementKey}/repositoryentries` | GET/POST/DELETE | Linked repository entries | CurriculumManager |
| `/curriculum/{curriculumKey}/elements/{elementKey}/members` | GET/POST/DELETE | Element members | CurriculumManager |
| `/curriculum/{curriculumKey}/elements/{elementKey}/taxonomy` | GET/POST/DELETE | Taxonomy levels | CurriculumManager |
| `/taxonomy` | GET | List taxonomies | Admin |
| `/taxonomy/{taxonomyKey}` | GET | Taxonomy details | Admin |
| `/taxonomy/{taxonomyKey}/levels` | GET/PUT/DELETE | Taxonomy levels | Admin |
| `/taxonomy/{taxonomyKey}/levels/{levelKey}/competences` | GET/POST/DELETE | Competences | Admin |
| `/taxonomy/{taxonomyKey}/competences/{identityKey}` | GET | User competences | Admin |
| `/taxonomy/{taxonomyKey}/levels/{levelKey}/competences/{identityKey}` | GET | User competences (level) | Admin |
| `/taxonomy/{taxonomyKey}/types` | GET/POST/PUT | Level types | Admin |
| `/taxonomy/{taxonomyKey}/types/{typeKey}` | GET | Level type | Admin |
| `/taxonomy/{taxonomyKey}/types/{typeKey}/allowedSubTypes` | GET/POST/DELETE | Sub-types | Admin |

### 3.6 Admin & System Domain (`/restapi/`)

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/ping` | GET | Health check | Public |
| `/i18n` | GET | Internationalization | Public |
| `/api` | GET | OpenAPI JSON | Public |
| `/api-docs/` | GET | Swagger UI | Public |
| `/system` | GET | System info | IP-protected |
| `/openmeetings` | — | OpenMeetings integration | Public |
| `/registration` | POST | User registration | Public |

---

## 4. Representative Request Lifecycles

### 4.1 Course Access via REST: Repository Entry → Course Details → Elements

```
HTTP Request: GET /restapi/repo/courses/123
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ RestApiLoginFilter.doFilter()                                    │
│ 1. Check REST module enabled (RestModule.isEnabled())           │
│ 2. Check API access mode (all/apikey)                           │
│ 3. Authenticate: Session → Token → Basic → IP → Open → Fail     │
│ 4. Create UserRequestImpl (sets requestURI, request, response)  │
│ 5. Set SEC_USER_REQUEST attribute on HttpServletRequest         │
│ 6. Apply rate limiting (per identity or per IP)                 │
│ 7. Set audit attributes (start time, auth provider)             │
│ 8. chain.doFilter() → CXF                                        │
└─────────────────────────────────────────────────────────────────┘
         ↓
CXF Dispatch: Matches CoursesWebService@Path("repo/courses")
         ↓
CoursesWebService.getCourse(@PathParam("courseId") Long courseId)
         ↓
CoursesWebService.loadCourse(courseId)
  → RepositoryService.loadByResourceId("CourseModule", courseId)
  → CourseFactory.loadCourse(entry)
         ↓
new CourseWebService(ores, course)  // Subresource locator
CoreSpringFactory.autowireObject(ws)  // Inject @Autowired deps
         ↓
CourseWebService.findById(@Context HttpServletRequest request)
         ↓
isCourseAccessible(course, request)
  → RepositoryService.hasRoleExpanded(identity, entry, [admin, learnresourcemanager, owner])
  → ACService.isAccessible(entry, identity, ...)  // Access control check
         ↓
ObjectFactory.get(course) → CourseVO
  → Populates: key, displayname, description, teaser, status, dates, 
               technicalType, educationalType, authors, externalId/Ref,
               managedFlags, canDownload, groups, curriculum, etc.
         ↓
Jackson serialization → JSON/XML Response
         ↓
RestApiLoginFilter.auditAfterRequest() → ApiAuditLogService.log()
```

**Key Objects:**
- `UserRequestImpl` — wraps HTTP request/response, holds `UserSession`, `Identity`, `Locale`
- `CourseVO` — Value Object with all course metadata (serializable)
- `RepositoryEntry` — JPA entity for course repository metadata
- `ICourse` — Course runtime interface (structure, config, environment)

---

### 4.2 Assessment Results Retrieval: Assessment Entry → Test Session → Responses → Scores

```
HTTP Request: GET /restapi/repo/courses/123/assessments/456/users/789
         ↓
RestApiLoginFilter (same as 4.1) → UserRequest with authenticated Identity
         ↓
CourseAssessmentWebService.getCourseNodeResultsOf()
         ↓
CoursesWebService.loadCourse(courseId) → ICourse
         ↓
isAuthorEditor(course, httpRequest)
  → getUserRequest().getIdentity()
  → CourseGroupManager.hasRight(identity, CourseRights.RIGHT_ASSESSMENT)
  → repositoryService.hasRoleExpanded([administrator, learnresourcemanager, owner])
         ↓
securityManager.loadIdentityByKey(identityKey) → Identity (assessed user)
         ↓
getNodeResult(userIdentity, course, nodeId)
  → CourseNode courseNode = course.getRunStructure().getNode(nodeId)
  → AssessmentHelper.createInitAndUpdateUserCourseEnvironment(identity, course)
    → UserCourseEnvironmentImpl with IdentityEnvironment
    → Initializes: scoreAccounting, learningPathStatus, nodeAccess
  → ScoreAccounting.evalCourseNode(courseNode) → AssessmentEvaluation
    → Aggregates: score, maxScore, weightedScore, passed, grade, 
                  completion, attempts, userVisible, assessmentStatus
  → getLastModificationDate() → AssessmentManager.getScoreLastModifiedDate()
         ↓
AssessableResultsVO populated with:
  - identityKey, identityExternalId, nodeIdent
  - score, maxScore, weightedScore, weightedMaxScore
  - passed, grade, performanceClassIdent
  - completion, attempts, userVisible
  - assessmentStatus, lastModifiedDate
  - lastUserModified, lastCoachModified
  - firstVisit, lastVisit, assessmentDone
  - fullyAssessed, fullyAssessedDate
         ↓
Jackson → JSON/XML Response
```

**Key Objects:**
- `AssessmentEvaluation` — Aggregated assessment result for a node
- `ScoreAccounting` — Calculates scores across course structure
- `UserCourseEnvironment` — User-specific course runtime state
- `AssessableResultsVO` — Assessment result VO (serializable)

**Assessment Flow (from assessment submission):**
```
Student submits test
  → QTI21AssessmentRunController.handleSubmit()
  → TestSessionController.finishTest() (JQTI+)
  → AssessmentTestSession persisted (QTI21Service)
  → AssessmentEntryOutcomesListener.onAssessmentCompleted()
    → AssessmentService.updateAssessmentEntry()
    → AssessmentEntryImpl persisted (score, passed, status)
  → CourseAssessmentService.updateScoreEvaluation()
    → ScoreEvaluation created with grade (if configured)
    → GradeService maps score → grade via GradeScale
  → EventBus: AssessmentEntryChangedEvent
```

---

### 4.3 User/Group Permission Checks: Role Hierarchy → Org Roles → Group Membership

```
HTTP Request: PUT /restapi/repo/courses/123/participants/789
         ↓
RestApiLoginFilter → Authenticated UserRequest (identity=currentUser)
         ↓
CourseWebService.addParticipant(@PathParam("identityKey") Long identityKey)
         ↓
isManager(httpRequest)
  → getUserRequest().getIdentity() → currentUser
  → course.getCourseEnvironment().getCourseGroupManager().getCourseEntry()
  → repositoryService.hasRoleExpanded(currentUser, entry, 
      [OrganisationRoles.administrator, OrganisationRoles.learnresourcemanager, GroupRoles.owner])
         ↓
securityManager.loadIdentityByKey(identityKey) → participantIdentity
         ↓
repositoryManager.addParticipants(currentUser, roles, IdentitiesAddEvent, entry, MailPackage)
  → RepositoryManager.addParticipants()
    → BusinessGroup participantGroup = getParticipantGroup(entry)
    → BusinessGroupService.addMembers(participantGroup, participants)
    → GroupMembershipImpl created (identity, group, role=participant)
    → EventBus: GroupMembershipAddedEvent
    → Mail sent (if configured)
         ↓
Response.ok().build()
```

**Role Hierarchy (highest → lowest):**
1. **System Roles** (global): `administrator`, `systemadmin`
2. **Organisation Roles** (per-org): `administrator`, `learnresourcemanager`, `author`, `lecturemanager`, `groupmanager`, `curriculummanager`
3. **Repository Entry Roles** (per-course): `owner`, `coach`, `participant`
4. **Business Group Roles** (per-group): `owner`, `coach`, `participant`, `waiting`

**Permission Check Pattern (used throughout REST):**
```java
// Course-level manager check
boolean isManager = repositoryService.hasRoleExpanded(identity, entry,
    OrganisationRoles.administrator.name(),
    OrganisationRoles.learnresourcemanager.name(),
    GroupRoles.owner.name());

// Course-level author check  
boolean isAuthor = repositoryService.hasRoleExpanded(identity, entry,
    OrganisationRoles.author.name());

// Course-level assessment right
boolean hasAssessmentRight = courseGroupManager.hasRight(identity, 
    CourseRights.RIGHT_ASSESSMENT, null);

// Group-level check
boolean isGroupManager = businessGroupService.isGroupAdministrator(identity, group);

// Self-action check
boolean isSelf = identityKey.equals(currentUser.getKey());
```

---

### 4.4 File Operations: Upload → VFS → Metadata → Download

```
HTTP Request: POST /restapi/vfs/course/123/files (multipart/form-data)
         ↓
RestApiLoginFilter → Authenticated UserRequest
         ↓
VFSWebservice.postFileToFolder(@PathParam("path") List<PathSegment> path,
                               @Context UriInfo uriInfo,
                               @Context HttpServletRequest request)
         ↓
addFileToFolder(uriInfo, path, request)
  → MultipartReader.read(request) → File tmpFile, filename, foldername
  → putFile(foldername, filename, inputStream, uriInfo, path)
         ↓
resolveContainer(path, true) → VFSContainer directory
  → Traverses path segments, creates missing containers
  → Respects MAX_FOLDER_DEPTH (20)
         ↓
Security Check: container.getLocalSecurityCallback().canWrite()
  → VFSContainer with SecurityCallback (e.g., CourseFolderSecurityCallback)
  → Checks: user role in course, group membership, quota
         ↓
directory.createChildLeaf(filename) → VFSLeaf newFile
         ↓
OutputStream out = newFile.getOutputStream(false)
FileUtils.cpio(inputStream, out, "Copy") → Streams content to VFS
         ↓
newFile.getMetaInfo() → Generates VFSMetadataImpl (size, mime-type, dates)
         ↓
createFileVO(newFile, uriInfo) → FileVO {rel, href, name, size}
         ↓
Response.ok(fileVO).build()
```

**Download Flow (GET /restapi/vfs/course/123/files/report.pdf):**
```
VFSWebservice.get(path, uriInfo, request)
  → resolveFile(path) → VFSItem (container or leaf)
  → If VFSContainer: list items → FileVO[] (links)
  → If VFSLeaf:
      Date lastModified = new Date(leaf.getLastModified())
      request.evaluatePreconditions(lastModified) → ETag/Last-Modified support
      String mimeType = WebappHelper.getMimeType(leaf.getName())
      Response.ok(leaf.getInputStream(), mimeType)
           .lastModified(lastModified).cacheControl(cc).build()
```

**Base64 Upload Alternative:**
```
POST /restapi/vfs/course/123/files (application/x-www-form-urlencoded)
  → postFile64ToFolder(foldername, filename, base64File, uriInfo, path)
  → Base64.decodeBase64(file) → byte[]
  → ByteArrayInputStream → putFile()
```

**Security Callback Pattern:**
```java
// In VFSContainer creation (e.g., CourseFolderFactory)
container.setLocalSecurityCallback(new VFSSecurityCallback() {
    public boolean canRead() { return hasReadAccess(ureq, course); }
    public boolean canWrite() { return hasWriteAccess(ureq, course); }
    public boolean canDelete() { return hasDeleteAccess(ureq, course); }
});
```

---

## 5. Authentication & Authorization Deep Dive

### 5.1 Authentication Methods (priority order in RestApiLoginFilter)

| Priority | Method | Header/Parameter | Description |
|----------|--------|------------------|-------------|
| 1 | **Session Cookie** | `JSESSIONID` | Existing authenticated web session |
| 2 | **Token (X-OLAT-TOKEN)** | `X-OLAT-TOKEN: <token>` | Stateless token from `/auth` login |
| 3 | **HTTP Basic (API Key)** | `Authorization: Basic base64(apikey:secret)` | API key authentication |
| 4 | **HTTP Basic (User/Pass)** | `Authorization: Basic base64(user:pass)` | Username/password (if `apiAccess=all`) |
| 5 | **IP-based** | — | Pre-configured IPs for `/system` endpoint |
| 6 | **Open/Unauthenticated** | — | Public endpoints (`/ping`, `/i18n`, `/api`, `/registration`) |

### 5.2 Token Authentication Flow

**Login (GET /restapi/auth):**
```
1. Client sends Basic Auth (user:pass) or API Key
2. RestApiLoginFilter.followForAuthentication()
   → Creates UserRequestImpl
   → AuthHelper.doHeadlessLogin(identity, provider, ureq, true)
   → RestSecurityBean.generateToken(identity, session)
   → Returns X-OLAT-TOKEN header + sets session
```

**Subsequent Requests:**
```
1. Client sends X-OLAT-TOKEN header
2. RestApiLoginFilter.isRequestTokenValid() 
   → RestSecurityBean.isTokenRegistrated(token, session)
3. followToken()
   → Creates UserRequestImpl
   → AuthHelper.doHeadlessLogin(identity, defaultProvider, ureq, true)
   → RestSecurityBean.renewToken(token) → New token in response header
   → Synchronized on UserSession (thread-safe)
```

**Token Management (RestSecurityBeanImpl):**
- **Storage:** Database (`o_restapi_token`) + In-memory `ConcurrentHashMap`
- **Expiry:** 120 seconds sliding window (renewed on each request)
- **Cleanup:** Scheduled job removes expired tokens
- **Scope:** Per-identity, per-session

### 5.3 API Key Authentication

**API Key Structure:**
- Stored as `Authentication` entity with `issuer=RESTAPI_AUTH`
- Credentials: `username=apikey`, `password=secret`
- Managed via `RestSecurityBean` (not exposed in UI)

**Flow:**
```
1. Client: Authorization: Basic base64(apikey:secret)
2. RestApiLoginFilter.isBasicAuthenticated()
   → Decodes credentials
   → authenticationDAO.getAuthentication(username, RESTAPI_AUTH, DEFAULT_ISSUER)
   → securityManager.checkCredentials(auth, password)
   → doHeadlessLogin(identity, RESTAPI_AUTH, ureq, true)
   → Generates X-OLAT-TOKEN for subsequent requests
```

### 5.4 Rate Limiting (RequestRateLimiter)

| Subject | Limit (default) | Key Pattern |
|---------|-----------------|-------------|
| Authenticated User | `rateLimitRequestsPerMinute` (60) | `rest:id:{identityKey}` |
| Anonymous/IP | `rateLimitAnonymousRequestsPerMinute` (20) | `rest:ip:{remoteAddr}` |

**Headers Returned:**
- `X-RateLimit-Limit` — Max requests per minute
- `X-RateLimit-Remaining` — Remaining in window
- `X-RateLimit-Reset` — Unix epoch seconds when window resets
- `Retry-After` — Seconds until retry (on 429)

**Exempt Endpoints:** `/ping`, `/i18n`, `/openmeetings`, `/drawio`, `/onlyoffice`, `/office365`, IP-protected `/system`

### 5.5 Audit Logging

**Table:** `o_api_audit_log`

| Field | Description |
|-------|-------------|
| `logDate` | Timestamp |
| `authProvider` | SESSION, TOKEN, API_KEY, PASSWORD, IP, NONE |
| `method` | HTTP method |
| `requestUri` | Request path |
| `statusCode` | HTTP response status |
| `remoteAddr` | Client IP |
| `identityKey` | Authenticated user (nullable) |
| `requestBody` | Request body (if enabled, max size configured) |
| `responseBody` | Response body (if enabled) |

**Configuration (RestModule):**
- `auditLogEnabled` — Enable/disable
- `auditLogBody` — Log request/response bodies
- `auditLogBodyMaxSize` — Max body size to log (default 10KB)

### 5.6 Role & Permission Model

**RestSecurityHelper Constants:**
```java
SEC_USER_REQUEST = "olat-user-request"  // UserRequest attribute key
SEC_TOKEN = "X-OLAT-TOKEN"              // Token header
SUB_CONTEXT = "/restapi"                 // Base path
```

**Helper Methods:**
- `getUserRequest(request)` — Extract UserRequest
- `getIdentity(request)` — Extract Identity
- `getRoles(request)` — Extract Roles (guest if unauthenticated)
- `getLocale(request)` — Negotiate locale
- `itself(identityKey, request)` — Check if requesting own resource
- `isCurriculumManager(request)` — Curriculum manager or admin
- `isGroupManager(request)` — Group manager or admin
- `isOwnerGrpManager(course, request)` — Course owner or group management right
- `isAuthorGrpManager(course, request)` — Author with group management right

---

## 6. fLMS Integration Assessment

### 6.1 Option A: Extend Existing REST API (Recommended)

**Use existing endpoints:**
- `GET /repo/courses/{courseId}/assessments` — Retrieve assessment results
- `POST /repo/courses/{courseId}/assessments/{nodeId}` — Import simulation results
- `GET /repo/courses/{courseId}/participants` — Get learners
- `PUT /repo/courses/{courseId}/participants/{identityKey}` — Enroll learners
- `GET /user/{identityKey}/my/courses` — Learner's course dashboard
- `GET /repo/repositoryentries` — Search courses by taxonomy/competency

**Extension Points:**
1. **Custom Assessment Modes** — Add PIX simulation mode via `/course/assessment/modes`
2. **Custom Result VO** — Extend `AssessableResultsVO` with simulation-specific fields
3. **EventBus Integration** — Listen to `AssessmentEntryChangedEvent` for real-time sync
4. **VFS for Simulation Artifacts** — Store simulation files via `/vfs/`

**Pros:** No new code, uses existing auth/rate-limit/audit, consistent with OpenOLAT
**Cons:** Limited to existing data model, may need VO extensions

---

### 6.2 Option B: New Dedicated REST Resource

**Create:** `fLMSSimulationWebService` at `/restapi/flms/simulations`

```java
@Path("flms/simulations")
@Component
public class FlmsSimulationWebService {
    
    @POST
    @Path("{simulationId}/launch")
    public Response launchSimulation(@PathParam("simulationId") String simId,
                                     LaunchRequest request) { ... }
    
    @POST
    @Path("{simulationId}/submit")
    public Response submitResults(@PathParam("simulationId") String simId,
                                  SimulationResultVO result) { ... }
    
    @GET
    @Path("{simulationId}/results")
    public Response getResults(@PathParam("simulationId") String simId) { ... }
}
```

**Register in `restApiContext.xml`:**
```xml
<ref bean="flmsSimulationWebService"/>
```

**Pros:** Clean separation, tailored data model, versioning control
**Cons:** New code to maintain, duplicate auth/rate-limit/audit config

---

### 6.3 Option C: Native Course Element (Deferred)

Create a **custom course element type** (like `IQTESTCourseNode`):
- Appears in course editor
- Has own run controller (`SimulationRunController`)
- Integrates with learning path, assessment, grading
- Uses existing course element framework

**Pros:** Full LMS integration, UI for authors, learning path support
**Cons:** Significant development effort, requires course element framework knowledge

---

### 6.4 Option D: LTI 1.3 / LTI Advantage (Deferred)

- OpenOLAT has LTI consumer/provider support
- fLMS simulations as LTI tools launched from OpenOLAT
- Grade passback via LTI Assignment and Grade Services

---

## 7. Versioning & Deprecation Strategy

### 7.1 Current Approach
- **No explicit API versioning in URLs** — All endpoints at `/restapi/`
- **Version in VO classes** — `CourseVO`, `CourseVOes` (collection wrapper with `totalCount`)
- **OpenAPI version:** `1.0` (in `OpenApiFeature` config)
- **Service version endpoints:** `/version` on each web service

### 7.2 Observed Patterns
1. **Additive changes only** — New fields added to VOs, never removed
2. **Collection wrappers** — `CourseVOes`, `UserVOes`, `TaxonomyVOes` for pagination metadata
3. **Media type variants** — `MediaTypeVariants.isPaged()` for pagination opt-in
4. **ETag/Last-Modified** — `Request.evaluatePreconditions()` for conditional requests

### 7.3 Recommendations for fLMS
- **Adopt URL versioning:** `/restapi/v1/flms/...` for new endpoints
- **Use collection wrappers** for paginated responses
- **Support `Accept: application/json;version=2`** for content negotiation
- **Deprecation headers:** `Sunset`, `Deprecation`, `Link: <new-url>; rel="successor-version"`

---

## 8. Performance Considerations

### 8.1 N+1 Query Prevention

**Problem Areas:**
- `CoursesWebService.toCourseVo()` — Loads course for each repository entry
- `CourseAssessmentWebService.getCourseRootResults()` — Loads all participants, then each result
- `UserWebService` — Lazy loading of roles, groups, preferences

**Mitigations in Code:**
```java
// CoursesWebService.toCourseVo() - commits every 33 entries
if(count++ % 33 == 0) {
    dbInstance.commitAndCloseSession();
}

// CourseAssessmentWebService - single query for all participants
List<Identity> courseUsers = loadAllParticipants(course);  // One query
for(Identity user: courseUsers) {
    getRootResult(user, course);  // Uses initialized UserCourseEnvironment
}
```

### 8.2 Connection Pooling
- **HikariCP** (Spring Boot default) via `DBFactory`
- **Pool size:** Configured in `olat.local.properties` (`hibernate.hikari.maximumPoolSize`)
- **Session-per-request:** Framework commits after dispatch, closes session

### 8.3 Serialization Optimization
- **VO Pattern:** Flat DTOs, no entity cycles
- **Jackson config:** `@JsonIgnore` on back-references, `@JsonView` for field filtering
- **Collection wrappers:** Avoids wrapper objects in JSON arrays

### 8.4 Caching Strategy

| Layer | Mechanism | Invalidation |
|-------|-----------|--------------|
| **HTTP** | `CacheControl`, `Last-Modified`, `ETag` | `Request.evaluatePreconditions()` |
| **Second-Level** | Infinispan (Hibernate) | Entity updates, `@Cache(usage=READ_WRITE)` |
| **Query** | Hibernate query cache | Not heavily used for REST |
| **Application** | `Cacher` (per-service caches) | `PersistedPropertiesChangedEvent`, manual eviction |

### 8.5 Batch Operations
- **Bulk user import:** `UserWebService` accepts `UserVO[]`
- **Bulk group operations:** `addAuthors(UserVO[])`, `addParticipants(UserVO[])`
- **Course DB:** Single key-value per request (no batch)
- **Assessment import:** Single node, single user per request

**Recommendation:** Add batch endpoints for fLMS simulation results (multiple users, multiple simulations).

---

## 9. Configuration Reference

### 9.1 RestModule Properties (`olat.local.properties`)

| Property | Default | Description |
|----------|---------|-------------|
| `restapi.enabled` | `false` | Enable REST API |
| `restapi.apiAccess` | `apikey` | `all` \| `apikey` |
| `restapi.rateLimitEnabled` | `true` | Enable rate limiting |
| `restapi.rateLimitRequestsPerMinute` | `60` | Authenticated user limit |
| `restapi.rateLimitAnonymousRequestsPerMinute` | `20` | Anonymous/IP limit |
| `restapi.ipsWithSystemAccess` | `""` | Comma-separated IPs for `/system` |
| `restapi.auditLogEnabled` | `true` | Enable audit logging |
| `restapi.auditLogBody` | `false` | Log request/response bodies |
| `restapi.auditLogBodyMaxSize` | `10240` | Max body size (bytes) |

### 9.2 Security Configuration

| Property | Default | Description |
|----------|---------|-------------|
| `security.restapi.token.timeout` | `120` | Token session timeout (seconds) |

---

## 10. OpenAPI/Swagger Documentation

### 10.1 Access Points
- **OpenAPI JSON:** `GET /restapi/openapi.json`
- **Swagger UI:** `GET /restapi/api-docs/`

### 10.2 Annotations Used
- `@Tag(name="Repo")` — Groups endpoints in UI
- `@Operation(summary, description)` — Endpoint documentation
- `@ApiResponse(responseCode, description, content)` — Response docs
- `@Schema(implementation=X.class)` — Request/response models
- `@Parameter(description)` — Parameter documentation

### 10.3 Generated Models
All VOs (`CourseVO`, `UserVO`, `AssessableResultsVO`, etc.) appear in `components/schemas` with full property documentation.

---

## 11. Summary & Recommendations

### 11.1 Architecture Strengths
1. **Clean separation:** Filter → CXF → Resource → Service → JPA
2. **Subresource pattern:** Natural REST hierarchy, request-scoped instances
3. **Multi-auth:** Session, token, API key, basic, IP — flexible integration
4. **Built-in cross-cutting:** Rate limiting, audit logging, OpenAPI
5. **VO pattern:** Stable serialization contract, no entity leakage

### 11.2 Areas for Improvement
1. **No API versioning in URL** — Breaking changes risk
2. **N+1 in some endpoints** — Course list loads each course individually
3. **No request/response compression** — Large payloads (course export)
4. **Synchronous only** — No async/webhook support for long operations
5. **Limited batch operations** — Single-item mutations dominate

### 11.3 fLMS Integration Recommendation

**Start with Option A (Extend Existing API):**
1. Use `/repo/courses/{courseId}/assessments/{nodeId}` for simulation results
2. Extend `AssessableResultsVO` with simulation-specific fields (via JSON ignore-unknown)
3. Add custom assessment mode `PIX_SIMULATION` via `/course/assessment/modes`
4. Use EventBus for real-time result propagation
5. Store simulation artifacts via VFS endpoints

**Future: Option B (Dedicated Resource) if:**
- Simulation data model diverges significantly
- Need webhook/async notifications
- Require independent versioning

---

## 12. Investigation Ledger Update

| Phase 5.2 Objective | Status | Notes |
|---------------------|--------|-------|
| 1. Baseline established | ✅ | Commit, branch, version, module location documented |
| 2. REST architecture discovered | ✅ | CXF, Spring, Jackson, providers, OpenAPI, subresource pattern |
| 3. Endpoints inventoried (7 domains) | ✅ | 100+ endpoints cataloged with auth requirements |
| 4. 4 request lifecycles traced | ✅ | Course access, assessment results, permissions, file ops |
| 5. Auth/authz deep dive | ✅ | 6 auth methods, rate limiting, audit, role hierarchy |
| 6. fLMS integration assessed | ✅ | 4 options analyzed with pros/cons |
| 7. Versioning/deprecation analyzed | ✅ | Current gaps and recommendations |
| 8. Performance considerations | ✅ | N+1, pooling, serialization, caching, batch |
| 9. Deliverable created | ✅ | This document |
| 10. Ledger updated | ✅ | Phase 5.2 complete |

---

*End of Phase 5.2 Investigation — Ready for Phase 5.3 (Build Procedures & Test Infrastructure)*
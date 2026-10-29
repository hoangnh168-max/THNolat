# OpenOLAT Extension Point Inventory

**Version:** 21.2-SNAPSHOT (commit 20e0b6b2f1)  
**Date:** 2026-10-22  
**Purpose:** Complete catalog of extension mechanisms for fLMS customization without upstream core modification

---

## Executive Summary

OpenOLAT provides **15 major extension mechanisms** across the application stack. All are **additive** (Class A - existing supported extension mechanisms) requiring no core code modification. The key patterns are:

1. **Spring Bean Registration** — XML or `@Component`/`@Service` discovery
2. **Extension Point Registration** — UI extensions via `GenericActionExtension`
3. **Interface Implementation + Auto-wiring** — Spring injects all implementations of an interface
4. **Singleton Registry** — `NewControllerFactory` runtime registration
5. **EventBus Pub/Sub** — Cluster-wide `MultiUserEvent` on `OLATResourceable`

---

## Classification Scheme

| Class | Definition | Upstream Change Required |
|-------|------------|-------------------------|
| **A** | Existing supported extension mechanism (documented, stable API) | No |
| **B** | Implementation pattern used consistently but not formally an "extension point" | No |
| **C** | Requires configuration file addition (XML context) | No |
| **D** | Requires subclassing core class (limited to specific areas) | Minimal |
| **E** | Requires core code modification (anti-pattern) | Yes — **avoid** |

All mechanisms documented here are **Class A or B**.

---

## 1. Course Node Registration (buildingblockContext.xml)

**Source:** `src/main/java/org/olat/course/nodes/_spring/buildingblockContext.xml:1-198`  
**Factory:** `CourseNodeFactory.getCourseNodes()` → `CoreSpringFactory.getBeansOfType(CourseNodeConfiguration.class)`  
**Interface:** `CourseNodeConfiguration` (extends `AbstractCourseNodeConfiguration`)

### How It Works
```xml
<bean id="wiki" class="org.olat.course.nodes.wiki.WikiCourseNodeConfiguration" scope="prototype">
    <property name="order" value="60" />
</bean>
```

### Required Implementation
```java
public class MyCourseNodeConfiguration extends AbstractCourseNodeConfiguration {
    @Override public CourseNode getInstance() { return new MyCourseNode(); }
    @Override public String getAlias() { return MyCourseNode.TYPE; }
    @Override public String getGroup() { return CourseNodeGroup.collaboration.name(); }
    @Override public String getLinkText(Locale locale) { ... }
    @Override public String getIconCSSClass() { return MyCourseNode.CSS_CLASS_ICON; }
    @Override public boolean isEnabled() { return MyModule.isEnabled() && super.isEnabled(); }
}
```

### fLMS Usage for PIX Simulator
- Create `PIXSimulatorCourseNodeConfiguration` bean in a custom context XML
- Implement `PIXSimulatorCourseNode` extending `AbstractAccessableCourseNode`
- Implement `PIXSimulatorRunController` for participant view
- Register bean in custom `fLMSContext.xml` imported via `mainContext.xml`

**Classification: A** — Fully supported, zero core modification

---

## 2. Module System (AbstractSpringModule)

**Source:** `src/main/java/org/olat/core/configuration/AbstractSpringModule.java:1-379`  
**Discovery:** `@Service` + component scan in `modulesContext.xml:11`  
**Base Class:** `AbstractSpringModule` (implements `InitializingBean`, `DisposableBean`, `GenericEventListener`)

### How It Works
```java
@Service
public class MyModule extends AbstractSpringModule {
    @Autowired public MyModule(CoordinatorManager cm) { super(cm); }
    
    @Override public void init() { 
        // Read defaults from olat.properties via @Value("${my.prop:default}")
        // Or from persisted config via moduleConfigProperties 
    }
    @Override protected void initFromChangedProperties() { ... }
}
```

### Configuration Persistence
- Properties stored in `{userdata}/system/configuration/{FQCN}.properties`
- Cluster-aware via `PersistedPropertiesChangedEvent` on EventBus
- Secrets via `setSecretStringProperty()` (encrypted)

### fLMS Usage
- `PIXSimulatorModule` for feature toggles, API keys, external service config
- `CompetencyModule` for competency framework settings
- Admin UI via `GenericActionExtension` (see #5)

**Classification: A** — Fully supported, zero core modification

---

## 3. UI Extensions — Admin Menus & Personal Tools (GenericActionExtension)

**Source:** `src/main/java/org/olat/core/extensions/action/GenericActionExtension.java:1-243`  
**Interface:** `ActionExtension` → `ExtensionElement`  
**Registration:** Spring bean with `init-method="initExtensionPoints"`

### How It Works
```xml
<bean class="org.olat.core.extensions.action.GenericActionExtension" init-method="initExtensionPoints">
    <property name="order" value="8209" />
    <property name="actionController">
        <bean class="org.olat.core.gui.control.creator.AutoCreator" scope="prototype">
            <property name="className" value="org.olat.my.module.ui.MyAdminController"/>
        </bean>
    </property>
    <property name="navigationKey" value="myfeature" />
    <property name="parentTreeNodeIdentifier" value="externalToolsParent" />
    <property name="extensionPoints">
        <list><value>org.olat.admin.SystemAdminMainController</value></list>
    </property>
    <property name="translationPackage" value="org.olat.my.module.ui" />
</bean>
```

### Extension Point Types
| Parent Identifier | Location | Example |
|-------------------|----------|---------|
| `modulesParent` | Admin → Modules | Forum, Wiki, Portfolio |
| `externalToolsParent` | Admin → External Tools | LTI, BigBlueButton, Zoom |
| `eAssessmentParent` | Admin → eAssessment | Question Pool, Certificates |
| `HomeMainController` | Personal Menu (top-right) | Portfolio, To-Do, Media Center |

### Security Callback
```xml
<property name="securityCallbackClassName" value="org.olat.core.extensions.security.UserOnlyExtensionSecurityCallback" />
```
Custom callbacks implement `ActionExtensionSecurityCallback`.

### fLMS Usage
- Admin config for PIX Simulator (API endpoints, scoring rules)
- Personal tool for learner dashboard (competency view, simulator history)
- Coach tool extensions

**Classification: A** — Fully supported, zero core modification

---

## 4. Controller Factory — ContextEntryControllerCreator

**Source:** `src/main/java/org/olat/NewControllerFactory.java:1-267`  
**Interface:** `ContextEntryControllerCreator`  
**Registry:** `NewControllerFactory.getInstance().addContextEntryControllerCreator(key, creator)`

### How It Works
```java
// At startup (e.g., in Module.init() or Spring @PostConstruct)
NewControllerFactory.getInstance().addContextEntryControllerCreator(
    "myresource", 
    new MyContextEntryControllerCreator()
);

// Business path: [myresource:123] → launches MyRunController
```

### Required Implementation
```java
public class MyContextEntryControllerCreator implements ContextEntryControllerCreator {
    @Override public ContextEntryControllerCreator clone() { return new MyContextEntryControllerCreator(); }
    @Override public boolean isResumable() { return true; }
    @Override public Controller createController(List<ContextEntry> ces, UserRequest ureq, WindowControl wControl) {
        return new MyRunController(ureq, wControl, ces);
    }
    @Override public String getSiteClassName(List<ContextEntry> entries, UserRequest ureq) { return null; }
    @Override public boolean validateContextEntryAndShowError(ContextEntry ce, UserRequest ureq, WindowControl wControl) { return true; }
    @Override public TabContext getTabContext(UserRequest ureq, OLATResourceable ores, ContextEntry mainEntry, List<ContextEntry> entries) {
        return new TabContext("My Tab", ores);
    }
}
```

### fLMS Usage
- Custom resource types (simulator instances, competency records)
- Deep linking into simulator from external systems
- LTI launch targets

**Classification: A** — Runtime registration API, zero core modification

---

## 5. EventBus — Cluster-Wide Pub/Sub

**Source:** `src/main/java/org/olat/core/util/event/EventBus.java:1-86`, `MultiUserEvent.java:1-101`  
**Access:** `coordinatorManager.getCoordinator().getEventBus()`

### How It Works
```java
// Register listener (in controller constructor)
OLATResourceable ores = OresHelper.createOLATResourceableInstance("CourseModule", courseId);
eventBus.registerFor(this, ureq.getIdentity(), ores);

// Fire event (anywhere)
eventBus.fireEventToListenersOf(new MultiUserEvent("simulator.completed"), ores);

// Handle in listener
@Override public void event(Event event) {
    if (event instanceof MultiUserEvent mue && "simulator.completed".equals(mue.getCommand())) {
        // Handle cross-session notification
    }
}

// MUST deregister in doDispose()
eventBus.deregisterFor(this, ores);
```

### Built-in Events
- `MultiUserEvent` — Generic command-based
- `NewIdentityCreatedEvent` — User provisioning
- `BusinessGroupModifiedEvent` — Group changes
- `RepositoryEntryLifecycleEvent` — Course status changes

### fLMS Usage
- Real-time simulator state sync across cluster nodes
- Competency achievement notifications
- LTI grade passback callbacks
- Cross-course analytics triggers

**Classification: A** — Fully supported, zero core modification

---

## 6. REST API Resources (JAX-RS + CXF)

**Source:** `src/main/java/org/olat/restapi/_spring/restApiContext.xml:1-149`  
**Discovery:** `<context:component-scan base-package="org.olat.restapi,..." />` + explicit package list for OpenAPI

### How It Works
```java
@Path("/pix/simulators")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
@Service
public class PIXSimulatorWebService {
    
    @GET @Path("/{id}")
    public Response getSimulator(@PathParam("id") Long id, @Context SecurityContext sc) { ... }
    
    @POST
    public Response createSimulator(SimulatorDTO dto, @Context SecurityContext sc) { ... }
}
```

### Authentication (6 methods)
1. **Session Cookie** — Standard web session
2. **Bearer Token** — `Authorization: Bearer <token>` (REST API tokens)
3. **API Key** — `X-API-Key` header
4. **Basic Auth** — `Authorization: Basic <base64>`
5. **IP Whitelist** — Configured IP ranges
6. **Open** — No auth (public endpoints)

### fLMS Usage
- Headless simulator API for external LMS (LTI Advantage)
- Competency/evidence CRUD
- Analytics data export
- Webhook callbacks for LTI AGS

**Classification: A** — Fully supported, zero core modification

---

## 7. Assessment Services & QTI 2.1 Integration

**Source:** `src/main/java/org/olat/ims/qti21/manager/QTI21Service.java`, `CourseAssessmentServiceImpl.java`

### Key Interfaces
| Service | Purpose |
|---------|---------|
| `QTI21Service` | Package import, test session management, response persistence |
| `AssessmentService` | Score persistence, `AssessmentEntry` lifecycle |
| `CourseAssessmentService` | Course-level assessment orchestration |
| `ScoreAccounting` | Score calculation, weighting, aggregation |

### Extension Points
- **Custom QTI Interaction** — Implement `QTIInteractionHandler` for PIX-specific interaction types
- **Scoring Hook** — `AssessmentEntryOutcomesListener` → custom score processing
- **Delivery Options** — `QTI21DeliveryOptions` for simulator-specific behavior (timing, attempts, navigation)

### fLMS Usage
- PIX simulator as QTI 2.1 package with custom interactions
- Custom scoring service for partial credit, adaptive scoring
- AssessmentEntry extension for simulator metadata

**Classification: A/B** — QTI extension via JQTI+ SPI (A); Assessment hooks via listeners (B)

---

## 8. VFS Providers & Context Info Resolvers

**Source:** `src/main/java/org/olat/core/commons/services/vfs/VFSContextInfoResolver.java:1-55`  
**Injection:** `@Autowired void setVfsContextInfoResolvers(List<VFSContextInfoResolver>)` in `VFSRepositoryServiceImpl.java:2338-2341`

### How It Works
```java
@Service
public class PIXSimulatorVFSContextInfoResolver implements VFSContextInfoResolver {
    @Override public String resolveContextTypeName(String path, Locale locale) {
        if (path.contains("/pix-simulator/")) return translate("pix.simulator.type");
        return null;
    }
    @Override public VFSContextInfo resolveContextInfo(String path, Locale locale) {
        if (path.contains("/pix-simulator/")) {
            return new VFSContextInfo(...); // course, simulator, attempt info
        }
        return null;
    }
}
```

### Security Callbacks
- `VFSRepositoryService` uses `SecurityCallback` for access control
- `FullAccessWithQuotaCallback` — quota enforcement
- `SandboxedMapper` — separate content domain for untrusted content (SCORM, LTI)

### fLMS Usage
- Custom VFS context for simulator assets (HTML/JS/CSS bundles)
- Quota policies for simulator uploads
- Content domain isolation for PIX iframes

**Classification: A** — Auto-wired list injection, zero core modification

---

## 9. LTI 1.3 Tool Registration & Launch

**Source:** `src/main/java/org/olat/ims/lti13/_spring/lti13Context.xml:1-34`, `LTI13Module.java`, `LTI13ToolDeployment.java`

### Platform Mode (OpenOLAT launches external tools)
- Admin UI: `LTI13AdminController` → tool deployment config (client_id, keyset_url, scopes)
- Launch: `LTI13LaunchController` → OIDC flow → JWT validation → `LTI13LaunchPresentationController`
- Grade Passback: `LTI13AssignmentGradeService` → AGS LineItems/Scores
- NRPS: `LTI13NamesRoleProvisioningService` → roster sync

### Tool Mode (OpenOLAT launched by external LMS)
- OIDC Login: `LTI13OIDCLoginController` → nonce/state validation
- Launch: `LTI13ToolLaunchController` → JWT verification → identity matching
- Deep Linking: `LTI13DeepLinkingController` → content item selection

### fLMS Usage
- **Option A:** PIX Simulator as LTI 1.3 Tool (external LMS launches it)
- **Option B:** PIX Simulator consumes external LTI tools (OpenOLAT as platform)
- **Option C:** Hybrid — simulator embedded via LTI, grades via AGS

**Classification: A** — Configuration-driven, zero core modification

---

## 10. Curriculum, Taxonomy & Competency Services

**Source:** `org.olat.modules.curriculum.CurriculumService`, `org.olat.modules.taxonomy.TaxonomyModule`, `org.olat.modules.creditpoint.CreditPointModule`

### Key Services
| Service | Purpose |
|---------|---------|
| `CurriculumService` | Curriculum/element CRUD, enrollment, progress tracking |
| `TaxonomyModule` | Hierarchical taxonomies (levels, competencies, skills) |
| `CreditPointModule` | ECTS/credit point accounting |
| `CurriculumLearningProgress` | Per-user progress on curriculum elements |

### Extension Points
- **Taxonomy Levels** — Custom level types via `TaxonomyLevelTypeManagedFlag`
- **Competency Mapping** — Link simulator outcomes to taxonomy levels
- **Progress Listeners** — `CurriculumElementUserProgress` updates on simulator completion

### fLMS Usage
- Map PIX simulator tasks to competency taxonomy levels
- Auto-update `CurriculumElementUserProgress` on simulator completion
- Credit point awarding via `CreditPointModule`

**Classification: A** — Service APIs, zero core modification

---

## 11. Internationalization (i18n) — Translation Bundles

**Source:** `src/main/java/org/olat/core/util/i18n/I18nManager.java`, `_i18n/LocalStrings_XX.properties`

### Fallback Chain
```
de_CH__customizing → de_CH → de__customizing → de → en__customizing → en (default) → en (fallback)
```

### Overlay Mechanism
- Client customization: `{userData}/customizing/lang/overlay/{package}/_i18n/LocalStrings_XX__customizing.properties`
- No core file modification needed

### Cross-Referencing
```properties
# Same package
my.key = $\:other.key

# Cross package
my.key = $org.olat.other.package:other.key
```

### fLMS Usage
- Add `LocalStrings_de.properties`, `LocalStrings_en.properties` in fLMS module `_i18n/`
- Override via customizing overlay for client-specific terminology
- Reference core keys for consistency

**Classification: A** — Standard Java properties, zero core modification

---

## 12. Permission & Authorization Services

**Source:** `org.olat.resource.accesscontrol.ACService`, `org.olat.basesecurity.BaseSecurityManager`, `org.olat.course.CourseGroupManager`

### Key Interfaces
| Service | Purpose |
|---------|---------|
| `ACService` | Resource access control (courses, groups, curriculum) |
| `BaseSecurityManager` | Identity/User/Role/Group management |
| `CourseGroupManager` | Course-specific rights (`CourseRights`, `GroupRights`) |
| `RepositoryService` | Repository entry permissions |

### Permission Model
- **Roles:** `author`, `coach`, `participant`, `observer`, `owner`, `tutor`
- **Rights:** Fine-grained (`read`, `write`, `delete`, `grade`, `coach`, `manageMembers`, etc.)
- **Context:** `UserCourseEnvironment` encapsulates all rights for a user in a course

### Extension Points
- Custom `SecurityCallback` for VFS/mappers
- `AccessResult` for custom resource types
- Role extensions via `Roles` enum (requires core change — avoid)

### fLMS Usage
- Simulator-specific rights (launch, view results, configure)
- Competency evidence access control
- Coach dashboard permissions

**Classification: A** — Service APIs; Role enum extension = D (avoid)

---

## 13. Form Elements & FlexiTable Components

**Source:** `org.olat.core.gui.components.form.flexible.*`, `FlexiTableDataModelFactory`

### New in 21.1.0
- `FormSection` — Collapsible form sections with persisted state
- `SearchElement` — Unified search with typeahead (`SearchFormEvent`)
- `FactSheet`, `Sections`, `ComponentList` — Layout components
- `labelIconCss` — Visual cues on form items

### FlexiTable Extension
```java
FlexiTableColumnModel model = FlexiTableDataModelFactory.createFlexiTableColumnModel();
model.addFlexiColumnModel(new DefaultFlexiColumnModel(Cols.name));
model.addFlexiColumnModel(new DefaultFlexiColumnModel("action", translate("action.edit"), "edit"));
tableEl.setAndLoadPersistedPreferences(ureq, "my-table-v1");
```

### fLMS Usage
- Simulator configuration forms
- Competency mapping UI
- Coach result tables with row actions

**Classification: A** — Component library, zero core modification

---

## 14. Scheduler / Background Jobs (Quartz + TaskExecutor)

**Source:** `courseContext.xml:184-193`, `TaskExecutorManager`, `LongRunnable`

### Cluster-Singleton Jobs
```xml
<bean id="myJobTrigger" class="org.springframework.scheduling.quartz.CronTriggerFactoryBean">
    <property name="jobDetail" ref="myJob.${cluster.singleton.services}" />
    <property name="cronExpression" value="0 30 2 * * ?" />
</bean>
<bean id="myJob.enabled" class="org.springframework.scheduling.quartz.JobDetailFactoryBean" lazy-init="true">
    <property name="jobClass" value="org.olat.my.module.jobs.MyJob" />
</bean>
<bean id="myJob.disabled" class="org.springframework.scheduling.quartz.JobDetailFactoryBean" lazy-init="true">
    <property name="jobClass" value="org.olat.core.commons.services.scheduler.DummyJob" />
</bean>
```

### Async Tasks
```java
taskExecutorManager.execute(
    new MyLongRunnable(simulatorId), 
    identity, resource, "pix-simulator", null
);
```
Queues: `standard`, `sequential`, `lowPriority`, `external`, `aiInteractive`, `aiBatch`

### fLMS Usage
- Simulator session cleanup (expired attempts)
- Competency progress batch updates
- Analytics aggregation jobs
- LTI grade sync retry logic

**Classification: A** — Configuration-driven, zero core modification

---

## 15. Wizard Framework (StepsMainRunController)

**Source:** `org.olat.core.gui.control.wizard.StepsMainRunController`, `BasicStep`, `StepFormBasicController`

### How It Works
```java
wizardCtrl = new StepsMainRunController(ureq, getWindowControl(), 
    new MyStep00(ureq), finishCallback, null, translate("wizard.title"), "o_sel_my_wizard");
listenTo(wizardCtrl);
getWindowControl().pushAsModalDialog(wizardCtrl.getInitialComponent());
```

### Steps
- Extend `BasicStep` → `setNextStep()`, `getStepController()`
- Step controllers extend `StepFormBasicController`
- Shared root form across steps
- Data via `addToRunContext()` / `getFromRunContext()`
- Commit only in finish callback

### fLMS Usage
- Simulator setup wizard (LTI config, scoring rules, competency mapping)
- Multi-step assessment creation

**Classification: A** — Framework API, zero core modification

---

## Summary Matrix: PIX Simulator Requirements → Extension Mechanisms

| PIX Simulator Requirement | Extension Mechanism(s) | Class | Effort |
|---------------------------|------------------------|-------|--------|
| New course element type | Course Node Registration (#1) | A | Medium |
| Admin configuration UI | GenericActionExtension (#3) | A | Low |
| Learner launch & run | ContextEntryControllerCreator (#4) + Course Node | A | Medium |
| Real-time state sync | EventBus (#5) | A | Low |
| Headless API for LTI | REST Resources (#6) | A | Medium |
| QTI 2.1 delivery | Assessment Services (#7) | A/B | Medium |
| Asset storage & isolation | VFS Context Resolver (#8) | A | Low |
| LTI 1.3 launch (tool/platform) | LTI Registration (#9) | A | Medium |
| Competency mapping | Taxonomy/Curriculum (#10) | A | Medium |
| Multi-language UI | i18n Overlays (#11) | A | Low |
| Access control | ACService / SecurityCallbacks (#12) | A | Low |
| Configuration forms | Form Elements (#13) | A | Low |
| Background processing | Scheduler/Tasks (#14) | A | Low |
| Multi-step setup | Wizard Framework (#15) | A | Low |

---

## Anti-Patterns to Avoid (Class E)

| Anti-Pattern | Why Avoid | Alternative |
|--------------|-----------|-------------|
| Modifying `buildingblockContext.xml` directly | Lost on upgrade | Create `fLMSContext.xml` imported in `mainContext.xml` |
| Subclassing `AbstractCourseNode` internals | Brittle, breaks on upgrade | Use `CourseNodeConfiguration` + composition |
| Adding to `Roles` enum | Core schema change | Use `GroupRights` / custom permissions |
| Direct `bcroot/` file access | Bypasses VFS, quota, security | Use `VFSManager`, `VFSRepositoryService` |
| String concatenation in JPQL | SQL injection, cache bypass | Named parameters (`:paramName`) |
| `java.net.http.HttpClient` directly | No proxy, timeout, audit config | Use `HttpClientService` |
| Skipping `listenTo()` / `removeAsListenerAndDispose()` | Memory leaks, zombie controllers | Always use controller lifecycle |

---

## Implementation Roadmap for fLMS PIX Simulator

### Phase 1: Foundation (Week 1-2)
1. Create `fLMSModule` extending `AbstractSpringModule`
2. Create `fLMSContext.xml` with course node bean + import in `mainContext.xml`
3. Implement `PIXSimulatorCourseNodeConfiguration` + `PIXSimulatorCourseNode`
4. Add i18n bundles in `fLMSModule` package

### Phase 2: UI & Launch (Week 2-3)
5. `PIXSimulatorRunController` for participant view
6. `GenericActionExtension` for admin config + personal tool
7. `ContextEntryControllerCreator` for deep linking

### Phase 3: Integration (Week 3-4)
8. LTI 1.3 Tool Deployment config (if external launch)
9. REST API for headless access
10. VFS Context Resolver for simulator assets
11. EventBus listeners for cross-session sync

### Phase 4: Assessment & Competency (Week 4-5)
12. QTI 2.1 package with custom interactions OR native scoring
13. `AssessmentEntryOutcomesListener` for score persistence
14. Taxonomy competency mapping + `CurriculumLearningProgress` updates

### Phase 5: Operations (Week 5-6)
15. Quartz jobs for cleanup/analytics
16. LongRunnable for async simulator operations
17. Security callbacks for content isolation

---

## Source Files Reference

| Mechanism | Key Files |
|-----------|-----------|
| Course Nodes | `buildingblockContext.xml`, `CourseNodeFactory.java`, `CourseNodeConfiguration.java`, `AbstractCourseNodeConfiguration.java` |
| Modules | `AbstractSpringModule.java`, `modulesContext.xml`, `WikiModule.java` |
| UI Extensions | `GenericActionExtension.java`, `AbstractExtension.java`, `ActionExtension.java` |
| Controller Factory | `NewControllerFactory.java`, `ContextEntryControllerCreator.java` |
| EventBus | `EventBus.java`, `MultiUserEvent.java`, `CoordinatorManager.java` |
| REST API | `restApiContext.xml`, `OlatRestApplication.java`, `RepositoryEntriesWebService.java` |
| Assessment | `QTI21Service.java`, `AssessmentService.java`, `CourseAssessmentServiceImpl.java` |
| VFS | `VFSContextInfoResolver.java`, `VFSRepositoryServiceImpl.java`, `VFSManager.java` |
| LTI 1.3 | `lti13Context.xml`, `LTI13Module.java`, `LTI13ToolDeployment.java`, `LTI13LaunchController.java` |
| Curriculum/Taxonomy | `CurriculumService.java`, `TaxonomyModule.java`, `CurriculumLearningProgress.java` |
| i18n | `I18nManager.java`, `I18nModule.java`, `_i18n/LocalStrings_XX.properties` |
| Permissions | `ACService.java`, `BaseSecurityManager.java`, `CourseGroupManager.java` |
| Forms/Tables | `FlexiTableDataModelFactory.java`, `UIFactory.java`, `FormSection.java` |
| Scheduler | `coordinateContext.xml`, `TaskExecutorManager.java`, `LongRunnable.java` |
| Wizard | `StepsMainRunController.java`, `BasicStep.java`, `StepFormBasicController.java` |

---

## Verification Checklist

For each extension point used in fLMS:

- [ ] Spring bean discovered (component scan or explicit XML)
- [ ] Interface contract implemented correctly
- [ ] Lifecycle methods called (`init()`, `doDispose()`, `afterPropertiesSet()`)
- [ ] EventBus listeners deregistered
- [ ] Child controllers managed via `listenTo()` / `removeAsListenerAndDispose()`
- [ ] User-facing text escaped in Velocity (`$r.escapeHtml()`)
- [ ] VFS accessed via `VFSManager` / `VFSRepositoryService` only
- [ ] JPQL uses named parameters only
- [ ] Outbound HTTP via `HttpClientService`
- [ ] Database access completes before render phase
- [ ] Configuration via `@Value` + persisted properties (not hardcoded)
- [ ] Admin UI via `GenericActionExtension` (not menu hacking)

---

*Generated as part of Phase 6.1 Extension-Point Analysis for fLMS Customization*
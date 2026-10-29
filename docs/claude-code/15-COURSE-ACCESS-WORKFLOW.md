# OpenOlat Course Access Workflow — Phase 4.2

**Date:** 2026-10-22  
**Status:** Complete  
**Scope:** Trace the course access workflow from authenticated HTTP request through course rendering to first meaningful course-element interaction

---

## Overview

This document traces the complete course access workflow in OpenOlat 21.1.0, from an authenticated HTTP request arriving at the servlet, through course loading and controller initialization, to the first meaningful course-element interaction (clicking a Wiki course element).

**Architecture Pattern:** Server-centric UI — all state lives on the server, browser receives HTML fragments via AJAX. No client-side framework.

---

## 1. HTTP Request Entry Point

### 1.1 AuthenticatedDispatcher

**File:** `src/main/java/org/olat/dispatcher/AuthenticatedDispatcher.java`

The `AuthenticatedDispatcher` handles all requests to `/auth/*` URLs. It is registered in `dispatcherContext.xml`:

```xml
<bean id="dispatcher" class="org.olat.core.dispatcher.DispatcherModule">
  <property name="dispatchers">
    <list>
      <ref bean="authenticatedDispatcher"/>
    </list>
  </property>
</bean>
```

**Key responsibilities:**
- Validates user session (`UserSession`)
- Extracts business path from URL
- Creates or reuses ChiefController (main window)
- Delegates to `NewControllerFactory` for controller launching

**Request processing flow in `execute()`:**

```java
// 1. Get/create UserSession
UserSession usess = UserSessionManager.getUserSession(request);

// 2. Create UserRequest
UserRequest ureq = new UserRequestImpl(uriPrefix, request, response);

// 3. Check authentication
if (!auth) {
  // Store business path for post-login redirect
  usess.putEntryInNonClearedStore(AUTHDISPATCHER_BUSINESSPATH, businessPath);
  forwardToDefaultDispatcher(); // redirects to login
  return;
}

// 4. Process business path (after auth)
String businessPath = usess.removeEntryFromNonClearedStore(AUTHDISPATCHER_BUSINESSPATH);
if (businessPath != null) {
  processBusinessPath(businessPath, request, response, ureq, usess);
}
```

### 1.2 Business Path Extraction

**Method:** `extractBusinessPath(UserRequest, HttpServletRequest, String)`

URL formats handled:
- **REST-style:** `/auth/[RepositoryEntry:123][CourseNode:456]` → parsed as key-value pairs
- **Jump-in URL:** `/auth/repo/go?rid=123&par=789` → converted to `[RepositoryEntry:123][Part:789]`

```java
String restPart = request.getRequestURI().substring(uriPrefix.length());
// Format: /type1/id1/type2/id2/...
String[] split = restPart.split("/");
if (split.length > 0 && split.length % 2 == 0) {
  return BusinessControlFactory.getInstance().formatFromSplittedURI(split);
}
```

---

## 2. Business Path Parsing

### 2.1 BusinessControlFactory

**File:** `src/main/java/org/olat/core/id/context/BusinessControlFactory.java`

Parses business path strings like `[RepositoryEntry:123][CourseNode:456]` into a `BusinessControl` object containing a stack of `ContextEntry` objects.

```java
public BusinessControl createFromString(String businessPath) {
  // Parses [Type:ID][Type:ID]... format
  // Each segment becomes a ContextEntry with OLATResourceable
}
```

**ContextEntry structure:**
- `OLATResourceable` — typed resource identifier (type name + ID)
- Optional state entries for deep linking

---

## 3. Controller Factory & Launch

### 3.1 NewControllerFactory

**File:** `src/main/java/org/olat/NewControllerFactory.java`

Singleton factory that maps resourceable type names to `ContextEntryControllerCreator` implementations.

**Registration (Spring configuration):**
```xml
<bean id="newControllerFactory" class="org.olat.NewControllerFactory" factory-method="getInstance">
  <property name="contextEntryControllerCreators">
    <map>
      <entry key="RepositoryEntry" value-ref="repositoryEntryControllerCreator"/>
      <entry key="CourseNode" value-ref="courseNodeControllerCreator"/>
      <!-- ... -->
    </map>
  </property>
</bean>
```

**Launch flow in `launch(UserRequest, WindowControl)`:**

```java
BusinessControl bc = wControl.getBusinessControl();
ContextEntry mainCe = bc.popLauncherContextEntry(); // First entry: RepositoryEntry
OLATResourceable ores = mainCe.getOLATResourceable();

// Special handling for RepositoryEntry
if (ores.getResourceableTypeName().equals(OresHelper.calculateTypeName(RepositoryEntry.class))) {
  RepositoryEntry re = RepositoryManager.getInstance().lookupRepositoryEntry(ores.getResourceableId());
  mainCe.upgradeOLATResourceable(re); // Replace with full entity
}

// Get creator for the resource type
ContextEntryControllerCreator typeHandler = getContextEntryControllerCreator(firstType);

// Validate access
if (!typeHandler.validateContextEntryAndShowError(mainCe, ureq, wControl)) {
  return false;
}

// Build full context entry chain
List<ContextEntry> ces = new ArrayList<>();
ces.add(mainCe);
while(bc.hasContextEntry()) {
  ces.add(bc.popLauncherContextEntry());
}

// Create controller
TabContext context = typeHandler.getTabContext(ureq, ores, mainCe, entries);
Controller launchC = typeHandler.createController(ces, ureq, bwControl);
```

---

## 4. RepositoryEntry Controller Creation

### 4.1 RepositoryEntryControllerCreator

**File:** `src/main/java/org/olat/repository/ui/RepositoryEntryControllerCreator.java`

Implements `ContextEntryControllerCreator` for `RepositoryEntry` type.

```java
@Override
public Controller createController(List<ContextEntry> entries, UserRequest ureq, WindowControl wControl) {
  RepositoryEntry re = (RepositoryEntry) entries.get(0).getOLATResourceable();
  
  // Determine runtime controller type based on resource type
  if (re.getOlatResource().getResourceableTypeName().equals("Course")) {
    return createCourseRuntimeController(ureq, wControl, re, entries);
  }
  // ... other types (Group, Curriculum, etc.)
}
```

**Course runtime controller creation:**

```java
private Controller createCourseRuntimeController(UserRequest ureq, WindowControl wControl, 
                                                 RepositoryEntry re, List<ContextEntry> entries) {
  RepositoryEntrySecurity reSecurity = RepositoryManager.getInstance().getRepositoryEntrySecurity(re, ureq.getIdentity());
  
  RuntimeControllerCreator creator = (u, wc, entry, sec, offerBookmark, showConfig) -> 
    new CourseRuntimeController(u, wc, entry, sec, offerBookmark, showConfig);
  
  return creator.createController(ureq, wControl, re, reSecurity, true, true);
}
```

---

## 5. CourseRuntimeController Initialization

**File:** `src/main/java/org/olat/course/run/CourseRuntimeController.java`

Extends `RepositoryEntryRuntimeController` → `BaseFullWebappController` → `ChiefController`.

### 5.1 Constructor

```java
public CourseRuntimeController(UserRequest ureq, WindowControl wControl,
    RepositoryEntry re, RepositoryEntrySecurity reSecurity, 
    RuntimeControllerCreator runtimeControllerCreator,
    boolean offerBookmark, boolean showCourseConfigLink) {
    
  super(ureq, wControl, re, reSecurity, runtimeControllerCreator, offerBookmark, showCourseConfigLink);
  
  if (!corrupted) {
    // Load course (with caching)
    ICourse course = CourseFactory.loadCourse(getRepositoryEntry());
    addLoggingResourceable(LoggingResourceable.wrap(course));
    
    // Register for course-level events
    coordinatorManager.getCoordinator().getEventBus().registerFor(this, getIdentity(), getOlatResourceable());
    coordinatorManager.getCoordinator().getEventBus().registerFor(this, getIdentity(), getRepositoryEntry());
    
    // Fire JOINED event for participant count
    if (courseModule.displayParticipantsCount()) {
      coordinatorManager.getCoordinator().getEventBus().fireEventToListenersOf(new MultiUserEvent(JOINED), getOlatResourceable());
      updateCurrentUserCount();
    }
  }
  
  setAssessmentModeMessage(ureq);
}
```

### 5.2 Key Initialization Steps

1. **Load Course** — `CourseFactory.loadCourse(re)` (cached)
2. **Load Rights** — `loadRights()` populates `courseRightsCache` from `CourseGroupManager`
3. **Create Runtime Controller** — Delegates to `RunMainController` via `RuntimeControllerCreator`
4. **Initialize Toolbar** — `initToolbar()` builds tools menu, my-course menu, general tools
5. **Register EventBus listeners** — For group modifications, assessment mode changes

### 5.3 Runtime Controller Creator

The `RuntimeControllerCreator` functional interface creates the `RunMainController`:

```java
@FunctionalInterface
public interface RuntimeControllerCreator {
  Controller createController(UserRequest ureq, WindowControl wControl,
      RepositoryEntry entry, RepositoryEntrySecurity reSecurity,
      boolean offerBookmark, boolean showCourseConfigLink);
}
```

In `CourseRuntimeController` constructor, this creates:
```java
RunMainController runMainController = new RunMainController(
    ureq, getSubWindowControl("CourseRun"), 
    getRepositoryEntry(), reSecurity, 
    offerBookmark, showCourseConfigLink);
```

---

## 6. RunMainController Initialization

**File:** `src/main/java/org/olat/course/run/RunMainController.java`

### 6.1 Constructor Key Steps

```java
public RunMainController(UserRequest ureq, WindowControl wControl,
    RepositoryEntry courseRepositoryEntry, RepositoryEntrySecurity reSecurity,
    boolean offerBookmark, boolean showCourseConfigLink) {
    
  super(ureq, wControl, LAYOUT_CUSTOM, "course-run");
  
  // 1. Load course
  this.course = CourseFactory.loadCourse(courseRepositoryEntry);
  this.courseRepositoryEntry = courseRepositoryEntry;
  
  // 2. Create UserCourseEnvironment (central permission/state object)
  this.uce = loadUserCourseEnvironment(ureq, reSecurity);
  
  // 3. Initialize NavigationHandler (handles node access, tree building)
  this.navHandler = new NavigationHandler(uce, visibilityFilter, false);
  
  // 4. Build initial tree model
  this.treeModel = navHandler.createTreeModel();
  luTree.setTreeModel(treeModel);
  
  // 5. Navigate to initial node (from business path or root)
  CourseNode startNode = getStartCourseNode(entries); // From ContextEntry chain
  currentCourseNode = updateTreeAndContent(ureq, startNode, null);
  
  // 6. Create content panel with glossary markup wrapper
  glossaryMarkerCtr = CourseGlossaryFactory.createGlossaryMarkupWrapper(ureq, wControl, contentP, cc);
  
  // 7. Set up pagination, breadcrumbs, etc.
}
```

### 6.2 UserCourseEnvironment

Central object holding:
- `CourseEnvironment` — course config, group manager, structure
- User roles (admin, coach, participant)
- Read-only status (by role, by course status, by override)
- Score accounting
- Identity environment

---

## 7. Course Element Navigation (Tree Click)

### 7.1 User Clicks Course Element in Tree

Event flow:
1. Browser sends AJAX request with component ID (tree node) and event command
2. `AuthenticatedDispatcher.processValidDispatchURI()` finds window, dispatches to `Window`
3. `Window` finds component by ID, fires event to owning controller (`RunMainController`)
4. `RunMainController.event()` handles `TreeEvent`

```java
@Override
public void event(UserRequest ureq, Component source, Event event) {
  if (source == luTree) {
    TreeEvent te = (TreeEvent) event;
    if (MenuTree.COMMAND_TREENODE_CLICKED.equals(te.getCommand())) {
      String nodeid = te.getNodeId();
      updateTreeAndContent(ureq, nodeid); // Navigate to course element
    }
  }
}
```

### 7.2 updateTreeAndContent

```java
protected CourseNode updateTreeAndContent(UserRequest ureq, String nodeId) {
  CourseNode identNode = course.getRunStructure().getNode(nodeId);
  CourseNode node = updateTreeAndContent(ureq, identNode, null);
  if (node != null) {
    currentCourseNode = node;
  } else {
    getWindowControl().setWarning(translate("msg.nodenotavailableanymore"));
  }
  return currentCourseNode;
}

private CourseNode updateTreeAndContent(UserRequest ureq, CourseNode calledCourseNode, 
    String nodecmd, List<ContextEntry> entries, StateEntry state) {
  
  // 1. Dispose old node controller
  if (currentNodeController != null && !currentNodeController.isDisposed()) {
    currentNodeController.dispose();
  }
  
  // 2. Ask NavigationHandler to evaluate jump
  NodeClickedRef nclr = navHandler.evaluateJumpToCourseNode(
      ureq, getWindowControl(), calledCourseNode, this, nodecmd);
  
  // 3. Handle access denied
  if (!nclr.isVisible()) {
    // Show no-access message
    return null;
  }
  
  // 4. Update tree model
  treeModel = nclr.getTreeModel();
  luTree.setTreeModel(treeModel);
  luTree.setSelectedNodeId(nclr.getSelectedNodeId());
  luTree.setOpenNodeIds(nclr.getOpenNodeIds());
  
  // 5. Get and set new run controller
  currentNodeController = nclr.getRunController();
  addToHistory(ureq, currentNodeController);
  
  // 6. Activate if Activateable2 (for deep linking)
  if (currentNodeController instanceof TitledWrapperController) {
    Controller contentcontroller = ((TitledWrapperController)currentNodeController).getContentController();
    if (contentcontroller instanceof Activateable2) {
      ((Activateable2)contentcontroller).activate(ureq, entries, state);
    }
  }
  
  return nclr.getCalledCourseNode();
}
```

---

## 8. NavigationHandler — Access Evaluation & Controller Creation

**File:** `src/main/java/org/olat/course/run/navigation/NavigationHandler.java`

### 8.1 evaluateJumpToCourseNode

```java
public NodeClickedRef evaluateJumpToCourseNode(UserRequest ureq, WindowControl wControl,
    CourseNode calledCourseNode, ControllerEventListener listeningController, String nodecmd) {
  
  CourseNode cn = (calledCourseNode == null) 
    ? userCourseEnv.getCourseEnvironment().getRunStructure().getRootNode()
    : calledCourseNode;
    
  return doEvaluateJumpTo(ureq, wControl, cn, listeningController, nodecmd, null, null);
}
```

### 8.2 doEvaluateJumpTo — Core Logic

```java
private NodeClickedRef doEvaluateJumpTo(UserRequest ureq, WindowControl wControl,
    CourseNode courseNode, ControllerEventListener listeningController,
    String nodecmd, String nodeSubCmd, Controller currentNodeController) {
  
  // 1. Build fresh tree model
  GenericTreeModel treeModel = createTreeModel();
  CourseTreeNode newCalledTreeNode = (CourseTreeNode) treeModel.getNodeById(courseNode.getIdent());
  
  // 2. Check visibility
  if (!newCalledTreeNode.isVisible()) {
    return new NodeClickedRef(treeModel, false, null, null, null, null, false);
  }
  
  // 3. Check additional conditions (time limits, prerequisites, etc.)
  AdditionalConditionManager addMan = null;
  if (courseNode instanceof AbstractAccessableCourseNode) {
    addMan = new AdditionalConditionManager((AbstractAccessableCourseNode)courseNode, courseId, identityEnv);
  }
  
  if (!newCalledTreeNode.isAccessible() || (addMan != null && !addMan.evaluateConditions())) {
    // Access denied — show NoAccessController or condition input controller
    Controller controller = addMan != null && newCalledTreeNode.getNodeEvaluation().oldStyleConditionsOk()
      ? addMan.nextUserInputController(ureq, wControl, userCourseEnv)
      : new NoAccessController(ureq, wControl, courseNode, userCourseEnv);
    
    return new NodeClickedRef(treeModel, true, nodeId, null, courseNode, 
      new NodeRunConstructionResult(controller), false);
  }
  
  // 4. Check if building block is enabled
  if (!CourseNodeFactory.getInstance().getCourseNodeConfigurationEvenForDisabledBB(courseNode.getType()).isEnabled()) {
    return new NodeClickedRef(treeModel, true, nodeId, null, courseNode,
      new NodeRunConstructionResult(MessageUIFactory.createInfoMessage(...)), false);
  }
  
  // 5. ACCESS OK — Create business context for this node
  Class<CourseNode> oresC = CourseNode.class;
  Long oresK = Long.valueOf(courseNode.getIdent());
  OLATResourceable ores = OresHelper.createOLATResourceableInstance(oresC, oresK);
  
  ContextEntry ce = BusinessControlFactory.getInstance().createContextEntry(ores);
  WindowControl bwControl = BusinessControlFactory.getInstance().createBusinessWindowControl(ce, wControl);
  
  // 6. Update module config defaults
  CourseNode parent = courseNode.getParent() instanceof CourseNode ? (CourseNode)courseNode.getParent() : null;
  courseNode.updateModuleConfigDefaults(false, parent, NodeAccessType.of(userCourseEnv), ureq.getIdentity());
  
  // 7. DELEGATE TO COURSE NODE — Each node type creates its own run controller
  NodeRunConstructionResult ncr = courseNode.createNodeRunConstructionResult(
      ureq, bwControl, userCourseEnv, nodeSecCallback, nodecmd, visibilityFilter);
  
  // 8. Wrap in TitledWrapperController for breadcrumbs/title
  Controller titledCtrl = TitledWrapperHelper.getWrapper(ureq, wControl, ncr.getRunController(), 
      userCourseEnv, courseNode, courseNode.getIconCssClass());
  
  // 9. Build NodeClickedRef with tree model and controller
  return new NodeClickedRef(treeModel, true, newSelectedNodeId, openCourseNodeIds, 
      courseNode, new NodeRunConstructionResult(titledCtrl), false);
}
```

**Key Design Point:** Each `CourseNode` subclass implements `createNodeRunConstructionResult()` to create its specific run controller. This is the **extension point** for new course element types.

---

## 9. Wiki Course Element Interaction (Representative Example)

### 9.1 WikiCourseNode.createNodeRunConstructionResult

**File:** `src/main/java/org/olat/course/nodes/WikiCourseNode.java`

```java
@Override
public NodeRunConstructionResult createNodeRunConstructionResult(UserRequest ureq, WindowControl wControl,
    UserCourseEnvironment userCourseEnv, CourseNodeSecurityCallback nodeSecCallback,
    String nodecmd, VisibilityFilter visibilityFilter) {
  
  NodeRunConstructionResult ncr;
  WikiRunController wikiController = null;
  
  if (nodeSecCallback.isAccessible()) {
    // Create the Wiki-specific run controller
    wikiController = new WikiRunController(wControl, ureq, this, userCourseEnv, 
        nodeSecCallback.getNodeEvaluation());
    ncr = wikiController.createNodeRunConstructionResult();
  } else {
    Controller controller = MessageUIFactory.createInfoMessage(ureq, wControl, null, getNoAccessExplanation());
    ncr = new NodeRunConstructionResult(controller);
  }
  
  // Wrap with title/breadcrumbs
  if (ncr == null && wikiController != null) {
    Controller titledCtrl = TitledWrapperHelper.getWrapper(ureq, wControl, wikiController, 
        this, "o_wiki_icon");
    ncr = new NodeRunConstructionResult(titledCtrl);
  }
  
  return ncr;
}
```

### 9.2 WikiRunController Constructor

**File:** `src/main/java/org/olat/course/nodes/wiki/WikiRunController.java`

```java
public WikiRunController(WindowControl wControl, UserRequest ureq, WikiCourseNode wikiCourseNode,
    UserCourseEnvironment userCourseEnv, NodeEvaluation ne) {
  super(ureq, wControl);
  this.courseEnv = userCourseEnv.getCourseEnvironment();
  this.config = wikiCourseNode.getModuleConfiguration();
  
  // 1. Get wiki RepositoryEntry from course node config
  RepositoryEntry wikiEntry = WikiEditController.getWikiRepoReference(config, true);
  
  // 2. Check wiki entry status
  if (wikiEntry.getEntryStatus() == RepositoryEntryStatusEnum.deleted || ...) {
    putInitialPanel(EmptyStateFactory.create(...)); // Show deleted message
    return;
  }
  
  // 3. Determine permissions
  boolean isAdmininstrator = userCourseEnv.isAdmin();
  boolean isGuestOnly = usess.getRoles().isGuestOnly();
  boolean isResourceOwner = isAdmininstrator || repositoryService.hasRole(getIdentity(), wikiEntry, GroupRoles.owner.name());
  
  // 4. Check for deep link to specific wiki page (from business path)
  BusinessControl bc = wControl.getBusinessControl();
  ContextEntry ce = bc.popLauncherContextEntry();
  
  // 5. Create security callback & assessment provider
  SubscriptionContext subsContext = WikiManager.createTechnicalSubscriptionContextForCourse(courseEnv, wikiCourseNode);
  WikiSecurityCallback callback;
  WikiAssessmentProvider assessmentProvider;
  
  if (userCourseEnv.isCourseReadOnly()) {
    callback = new WikiReadOnlySecurityCallback(isGuestOnly, (isAdmininstrator || isResourceOwner));
    assessmentProvider = DryRunAssessmentProvider.create();
  } else {
    Boolean courseEditRight = hasEditRights(wikiCourseNode, userCourseEnv, ne);
    callback = new WikiSecurityCallbackImpl(courseEditRight, isAdmininstrator, isGuestOnly, false,
        isResourceOwner, subsContext);
    assessmentProvider = userCourseEnv.isParticipant()
      ? PersistingAssessmentProvider.create(wikiEntry, getIdentity())
      : DryRunAssessmentProvider.create(learningPath);
  }
  
  // 6. Create WikiMainController (actual wiki UI from wiki module)
  if (ce != null) { // Deep link to specific page
    String page = extractPageFromContextEntry(ce);
    wikiCtr = WikiManager.getInstance().createWikiMainController(ureq, wControl, 
        wikiEntry.getOlatResource(), callback, assessmentProvider, page);
  } else {
    wikiCtr = WikiManager.getInstance().createWikiMainController(ureq, wControl,
        wikiEntry.getOlatResource(), callback, assessmentProvider, null);
  }
  
  listenTo(wikiCtr);
  
  // 7. Wrap with title bar
  Controller wrappedCtr = TitledWrapperHelper.getWrapper(ureq, wControl, wikiCtr,
      userCourseEnv, wikiCourseNode, Wiki.CSS_CLASS_WIKI_ICON);
  putInitialPanel(wrappedCtr.getInitialComponent());
}
```

### 9.3 WikiRunController.createNodeRunConstructionResult

```java
@Override
public NodeRunConstructionResult createNodeRunConstructionResult() {
  if (wikiCtr != null) {
    // Wiki has its own internal tree (page hierarchy)
    TreeModel wikiTreeModel = wikiCtr.getAndUseExternalTree();
    String selNodeId = wikiTreeModel.getRootNode().getChildAt(0).getIdent();
    return new NodeRunConstructionResult(this, wikiTreeModel, selNodeId, wikiCtr);
  }
  return null;
}
```

---

## 10. Complete Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. HTTP REQUEST                                                             │
│    GET /auth/[RepositoryEntry:123][CourseNode:456]                          │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. AuthenticatedDispatcher.execute()                                        │
│    - Validate UserSession                                                   │
│    - Extract business path from URL                                         │
│    - processBusinessPath(businessPath, ...)                                 │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. BusinessControlFactory.createFromString()                                │
│    - Parse "[RepositoryEntry:123][CourseNode:456]" → BusinessControl        │
│    - Stack of ContextEntry objects                                          │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. NewControllerFactory.launch()                                            │
│    - Pop first ContextEntry (RepositoryEntry)                               │
│    - Lookup ContextEntryControllerCreator for "RepositoryEntry"             │
│    - RepositoryEntryControllerCreator.createController()                    │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. RepositoryEntryControllerCreator.createCourseRuntimeController()         │
│    - Check RepositoryEntrySecurity (RBAC)                                   │
│    - new CourseRuntimeController(ureq, wControl, re, reSecurity, ...)       │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 6. CourseRuntimeController Constructor                                      │
│    - CourseFactory.loadCourse(re) — loads ICourse (cached)                  │
│    - loadRights() — populates courseRightsCache from CourseGroupManager     │
│    - Register EventBus listeners (course, repository entry)                 │
│    - Create RunMainController via RuntimeControllerCreator                  │
│    - initToolbar() — builds tools menu, my-course menu                      │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 7. RunMainController Constructor                                            │
│    - Load course & create UserCourseEnvironment (permissions, roles)        │
│    - new NavigationHandler(uce, visibilityFilter, false)                    │
│    - Build initial tree model                                               │
│    - updateTreeAndContent(startNode) — navigate to initial node             │
│    - Create glossary markup wrapper for content                             │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 8. USER CLICKS COURSE ELEMENT IN TREE (e.g., Wiki)                          │
│    - AJAX request with tree node ID                                         │
│    - RunMainController.event() → updateTreeAndContent(nodeId)               │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 9. NavigationHandler.doEvaluateJumpTo()                                     │
│    - Build fresh tree model                                                 │
│    - Check visibility & additional conditions (time, prerequisites)         │
│    - If denied: return NoAccessController                                   │
│    - If allowed:                                                            │
│        a) Create ContextEntry for CourseNode                                │
│        b) Call courseNode.createNodeRunConstructionResult()                 │
│        c) Wrap in TitledWrapperController                                   │
│        d) Return NodeClickedRef with tree model & controller                │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 10. WikiCourseNode.createNodeRunConstructionResult()                        │
│     - new WikiRunController(wControl, ureq, this, uce, nodeEval)            │
│     - wikiController.createNodeRunConstructionResult()                      │
│     - Wrap in TitledWrapperHelper                                           │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 11. WikiRunController Constructor                                           │
│     - Get wiki RepositoryEntry from node config (soft key)                  │
│     - Check wiki entry status (deleted/trash)                               │
│     - Determine permissions (admin, coach, participant, guest)              │
│     - Check for deep link to specific wiki page (business path)             │
│     - Create WikiSecurityCallback & AssessmentProvider                      │
│     - WikiManager.createWikiMainController() — delegates to Wiki module     │
│     - listenTo(wikiCtr)                                                     │
│     - Wrap with title/breadcrumbs via TitledWrapperHelper                   │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 12. RunMainController Receives NodeClickedRef                               │
│     - Dispose old currentNodeController                                     │
│     - Set new treeModel, selected node, open nodes                          │
│     - currentNodeController = nclr.getRunController()                       │
│     - addToHistory() for browser back button                                │
│     - Activate if Activateable2 (restore deep link state)                   │
│     - Render phase: dirty components → JSON/HTML response                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Safe Extension Points for fLMS Development

Based on this trace, here are the safe, read-only extension points for fLMS customization:

### 11.1 Course Element Types (Adding New Course Elements)

**Location:** `src/main/java/org/olat/course/nodes/` + module

To add a new course element type:
1. Create `NewCourseNode` extending `AbstractAccessableCourseNode` (or `CourseNode`)
2. Implement `createNodeRunConstructionResult()` returning your `NewCourseRunController`
3. Register in `CourseNodeFactory` (Spring config)
4. Add i18n keys in `_i18n/LocalStrings.properties`

**No core modification needed** — purely additive.

### 11.2 Course Tool Extensions (Global Course Tools)

**Location:** `CourseRuntimeController.initToolsMenu()`, `doOpenTool()`

Tools are defined in `CourseTool` enum. To add a tool:
1. Add entry to `CourseTool` enum
2. Add link field in `CourseRuntimeController`
3. Add `case` in `doOpenTool()` calling your `doYourTool()`
4. Create your tool controller

**Extension point:** `OpenCourseToolEvent` fired from `RunMainController` → handled in `CourseRuntimeController.event()`

### 11.3 Navigation/Access Control Customization

**Location:** `NavigationHandler`, `AdditionalConditionManager`, `NodeAccessService`

- **Additional Conditions:** Implement custom `Condition` types for prerequisites
- **Node Access:** Extend `NodeAccessService` for custom visibility rules
- **Node Evaluation:** `NodeEvaluation` captures computed access state

### 11.4 EventBus Integration (Cross-Cutting)

**Location:** `coordinatorManager.getCoordinator().getEventBus()`

Listen for:
- `MultiUserEvent` — "joined", "left" (participant count)
- `BusinessGroupModifiedEvent` — group changes
- `AssessmentModeStatusEvent` — assessment mode changes
- `CourseNodeEvent` — node-specific events
- Custom `MultiUserEvent` types

### 11.5 VFS for Course File Access

**Never access `bcroot/` directly.** Use VFS:

```java
VFSContainer courseFolder = VFSManager.olatRootContainer("/course/" + courseId + "/files");
VFSLeaf file = courseFolder.createChildLeaf("document.pdf");
VFSManager.copyContent(inputStream, file, identity);
```

### 11.6 Custom Course Configuration

**Location:** `CourseConfig` (XML in course VFS), `ModuleConfiguration` per node

Access via:
```java
CourseConfig cc = userCourseEnv.getCourseEnvironment().getCourseConfig();
ModuleConfiguration config = courseNode.getModuleConfiguration();
```

---

## 12. Key Classes Reference

| Class | Purpose | File |
|-------|---------|------|
| `AuthenticatedDispatcher` | Authenticated request entry point | `dispatcher/AuthenticatedDispatcher.java` |
| `BusinessControlFactory` | Business path parsing | `id/context/BusinessControlFactory.java` |
| `NewControllerFactory` | Controller launcher | `NewControllerFactory.java` |
| `RepositoryEntryControllerCreator` | RepositoryEntry → Controller | `repository/ui/RepositoryEntryControllerCreator.java` |
| `CourseRuntimeController` | Main course runtime controller | `course/run/CourseRuntimeController.java` |
| `RunMainController` | Course content & navigation | `course/run/RunMainController.java` |
| `NavigationHandler` | Node access & tree building | `course/run/navigation/NavigationHandler.java` |
| `UserCourseEnvironment` | User permissions & state | `course/run/userview/UserCourseEnvironmentImpl.java` |
| `CourseNode` | Base course element | `course/nodes/CourseNode.java` |
| `WikiCourseNode` | Wiki course element | `course/nodes/WikiCourseNode.java` |
| `WikiRunController` | Wiki run-time controller | `course/nodes/wiki/WikiRunController.java` |
| `WikiMainController` | Wiki module UI controller | `modules/wiki/WikiMainController.java` |
| `NodeRunConstructionResult` | Controller + tree model carrier | `course/run/navigation/NodeRunConstructionResult.java` |
| `CourseTool` | Global course tools enum | `course/run/tools/CourseTool.java` |

---

## 13. Security Checkpoints in Flow

1. **AuthenticatedDispatcher** — Session validation, authentication check
2. **RepositoryEntrySecurity** — Entry-level RBAC (owner, coach, participant, guest)
3. **CourseRuntimeController.loadRights()** — Course-group-level rights (CourseRights enum)
4. **NavigationHandler.doEvaluateJumpTo()** — Node visibility + additional conditions
5. **CourseNodeSecurityCallback** — Per-node access evaluation (NodeEvaluation)
6. **WikiSecurityCallback** — Wiki-specific permissions (edit, read, assess)
7. **VFS** — File access controlled by repository entry roles

All checks happen **before render phase** — no business logic during rendering.

---

## 14. Related Documentation

- `14-LOGIN-WORKFLOW.md` — Authentication flow (precedes this)
- `04-COURSE-STRUCTURE.md` — Course package structure overview
- `doc/openolat-architecture.md` — Full architecture documentation
- `.claude/openolat-architecture-knowledge.md` — Condensed architecture reference
- `doc/i18n-translation-reference.yaml` — Translation reference

---

## 15. Investigation Ledger Update

This completes **Phase 4.2: Course Access Workflow**.

**Next phases:**
- Phase 4.3: Assessment Submission Workflow
- Phase 4.4: File Upload Workflow
- Phase 4.5: Course Creation/Editing Workflow
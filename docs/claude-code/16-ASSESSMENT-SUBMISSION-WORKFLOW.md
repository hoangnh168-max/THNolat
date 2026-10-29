# Phase 4.3 — Assessment Submission Workflow Trace

**Date:** 2026-10-22  
**Objective:** Trace the complete assessment submission workflow from student opening an assessment to submitting responses, persisting results, and retrieving completion status.

---

## Executive Summary

This document traces the assessment submission workflow in OpenOlat using **QTI 2.1** (IMS Question & Test Interoperability) as the standard, with **IQTESTCourseNode** as the representative course element and **QTI21AssessmentRunController** / **AssessmentTestDisplayController** as the core controllers.

**Key Files Analyzed:**
- `src/main/java/org/olat/course/nodes/IQTESTCourseNode.java` — Course node entry point
- `src/main/java/org/olat/course/nodes/iq/QTI21AssessmentRunController.java` — Run controller for participants
- `src/main/java/org/olat/ims/qti21/ui/AssessmentTestDisplayController.java` — Core assessment controller (2,939 lines)
- `src/main/java/org/olat/ims/qti21/QTI21Service.java` — Service interface for persistence
- `src/main/java/org/olat/ims/qti21/manager/AssessmentTestSessionDAO.java` — DAO layer
- `src/main/java/org/olat/ims/qti21/model/jpa/AssessmentTestSessionImpl.java` — JPA entity
- `src/main/java/org/olat/ims/qti21/ui/AssessmentEntryOutcomesListener.java` — Score persistence bridge

---

## 1. Workflow Overview

```
Student clicks "Start Assessment" on IQTest course element
         │
         ▼
IQTESTCourseNode.getRunController() 
         │
         ▼
QTI21AssessmentRunController (if participant) 
         │
         ├── "Start" clicked ──► Creates AssessmentTestDisplayController
         │
         ▼
AssessmentTestDisplayController (core assessment experience)
         │
         ├── Loads QTI test package via QTI21Service
         ├── Creates/resumes AssessmentTestSession
         ├── Initializes JQTI+ TestSessionController
         │
         ▼
QtiWorksController (inner controller for rendering)
         │
         ├── Renders questions via AssessmentTestFormItem
         ├── Handles navigation (next, prev, tree)
         ├── Handles responses (tmpResponse, fullTmpResponse, response)
         │
         ▼
Submission Events (response → handleResponse)
         │
         ├── Maps string/file responses → ResponseData
         ├── Binds to JQTI+ ItemSessionController
         ├── Computes scores via Response Processing (RP) / Outcome Processing (OP)
         ├── Persists AssessmentResponse entities
         ├── Updates AssessmentTestSession (score, completion, duration)
         │
         ▼
AssessmentEntryOutcomesListener.submit()
         │
         ├── Updates AssessmentEntry (score, passed, status, attempts)
         ├── Triggers digital signature if enabled
         │
         ▼
AssessmentTestDisplayController shows results (AssessmentResultController)
         │
         ▼
Student clicks "Close Results" ──► Exits test, fires QTI21Event.CLOSE_RESULTS
```

---

## 2. Detailed Step-by-Step Trace

### Step 1: Course Element Entry Point — `IQTESTCourseNode`

**File:** `src/main/java/org/olat/course/nodes/IQTESTCourseNode.java`

The IQTESTCourseNode is the course element for QTI 2.1 assessments. It determines which controller to return based on user role:

```java
@Override
public CourseNodeRunController getRunController(UserRequest ureq, WindowControl wControl,
        UserCourseEnvironment userCourseEnv) {
    
    if(userCourseEnv.isCourseRunByTeacherOrCoach()) {
        // Teacher/coach view - grading/monitoring
        return new IQIdentityListCourseNodeController(ureq, wControl, userCourseEnv, this, getCourseNode());
    } else {
        // Participant view - taking the test
        return new QTI21AssessmentRunController(ureq, wControl, userCourseEnv, getCourseNode());
    }
}
```

**Key Decision Points:**
- **Participant** → `QTI21AssessmentRunController`
- **Teacher/Coach** → `IQIdentityListCourseNodeController` (grading interface)

---

### Step 2: Participant Run Controller — `QTI21AssessmentRunController`

**File:** `src/main/java/org/olat/course/nodes/iq/QTI21AssessmentRunController.java` (1,291 lines)

This controller manages the **assessment lifecycle** for a participant:

**Responsibilities:**
1. **Start assessment** — Creates `AssessmentTestDisplayController`
2. **Show results** — Displays `AssessmentResultController` after completion
3. **Handle cancel/suspend** — User can cancel or suspend the test
4. **Manage attempts** — Respects `maxAttempts` from delivery options
4. **Digital signatures** — Handles confirmation signing

**Key Methods:**
- `doStartAssessment(ureq)` — Creates `AssessmentTestDisplayController`
- `doOpenResults(ureq)` — Shows results via `AssessmentResultController`
- `doConfirmCancel(ureq)` / `doCancel(ureq)` — Cancel handling
- `doConfirmSuspend(ureq)` / `doSuspend(ureq)` — Suspend handling

**Start Assessment Flow:**
```java
private void doStartAssessment(UserRequest ureq) {
    // 1. Get/create assessment entry
    AssessmentEntry assessmentEntry = assessmentService.getOrCreateAssessmentEntry(
        getIdentity(), courseEntry, subIdent, testEntry, true);
    
    // 2. Check attempt limits
    if (maxAttempts > 0 && assessmentEntry.getAttempts() >= maxAttempts) {
        showError("error.max.attempts.reached");
        return;
    }
    
    // 3. Create display controller
    AssessmentTestDisplayController displayCtrl = new AssessmentTestDisplayController(
        ureq, getWindowControl(), outcomesListener,
        testEntry, courseEntry, subIdent,
        deliveryOptions, overrideOptions,
        scoreScale, showCloseResults, authorMode, anonym);
    
    listenTo(displayCtrl);
    mainPanel.setContent(displayCtrl.getInitialComponent());
}
```

---

### Step 3: Core Assessment Controller — `AssessmentTestDisplayController`

**File:** `src/main/java/org/olat/ims/qti21/ui/AssessmentTestDisplayController.java` (2,939 lines)

This is the **main controller** for the student assessment experience. It implements `CandidateSessionContext` and `GenericEventListener`.

#### 3.1 Constructor Initialization

```java
public AssessmentTestDisplayController(UserRequest ureq, WindowControl wControl, 
        OutcomesListener listener, RepositoryEntry testEntry, RepositoryEntry entry, 
        String subIdent, QTI21DeliveryOptions deliveryOptions, 
        QTI21OverrideOptions overrideOptions, BigDecimal scoreScale, 
        boolean showCloseResults, boolean authorMode, boolean anonym) {
    
    // 1. Load and resolve QTI test package
    fUnzippedDirRoot = FileResourceManager.getInstance().unzipFileResource(testEntry.getOlatResource());
    resolvedAssessmentTest = qtiService.loadAndResolveAssessmentTest(fUnzippedDirRoot, false, false);
    
    // 2. Initialize marks (bookmarking items for review)
    initMarks();
    
    // 3. Create or resume AssessmentTestSession
    initOrResumeAssessmentTestSession(ureq, authorMode);
    
    // 4. Register resource mapper for QTI assets (images, media)
    URI assessmentObjectUri = qtiService.createAssessmentTestUri(fUnzippedDirRoot);
    File submissionDir = qtiService.getSubmissionDirectory(candidateSession);
    mapperUri = registerCacheableMapper(ureq, "QTI21Resources::" + testEntry.getKey(),
            new ResourcesMapper(assessmentObjectUri, fUnzippedDirRoot, submissionDir));
    
    // 5. Register for EventBus (for cross-session events)
    OLATResourceable sessionOres = OresHelper.createOLATResourceableInstance(
        AssessmentTestSession.class, candidateSession.getKey());
    coordinator.getEventBus().registerFor(this, getIdentity(), sessionOres);
    
    // 6. Initialize QtiWorksController (inner controller for UI)
    initQtiWorks(ureq);
}
```

#### 3.2 Session Creation/Resumption

```java
private void initOrResumeAssessmentTestSession(UserRequest ureq, boolean authorMode) {
    // Get or create AssessmentEntry
    AssessmentEntry assessmentEntry = assessmentService.getOrCreateAssessmentEntry(
        assessedIdentity, anonymousIdentifier, entry, subIdent, rootEntry, testEntry, false);
    
    // Create OutcomesListener if not provided
    if(outcomesListener == null) {
        boolean manualCorrections = AssessmentTestHelper.needManualCorrection(resolvedAssessmentTest);
        outcomesListener = new AssessmentEntryOutcomesListener(
            entry, testEntry, assessmentEntry, scoreScale, manualCorrections, 
            assessmentService, authorMode);
    }
    
    // Check for disadvantage compensation
    if(StringHelper.containsNonWhitespace(subIdent)) {
        DisadvantageCompensation compensation = disadvantageCompensationService
            .getActiveDisadvantageCompensation(getIdentity(), entry, subIdent);
        if(compensation != null) compensationExtraTime = compensation.getExtraTime();
    }
    
    // Try to resume existing session
    AssessmentTestSession lastSession = qtiService.getResumableAssessmentTestSession(
        assessedIdentity, anonymousIdentifier, entry, subIdent, testEntry, authorMode);
    
    if(lastSession == null) {
        // NEW SESSION
        initNewAssessmentTestSession(ureq, assessmentEntry, compensationExtraTime, authorMode);
    } else {
        // RESUME EXISTING
        candidateSession = lastSession;
        extraTime = lastSession.getExtraTime();
        candidateAuditLogger = qtiService.getAssessmentSessionAuditLogger(candidateSession, authorMode);
        testSessionController = resumeSession(ureq);
    }
}
```

**New Session Creation:**
```java
private void initNewAssessmentTestSession(UserRequest ureq, AssessmentEntry assessmentEntry, 
        Integer compensationTime, boolean authorMode) {
    candidateSession = qtiService.createAssessmentTestSession(
        assessedIdentity, anonymousIdentifier, assessmentEntry,
        entry, subIdent, testEntry, compensationTime, authorMode);
    
    candidateAuditLogger = qtiService.getAssessmentSessionAuditLogger(candidateSession, authorMode);
    testSessionController = enterSession(ureq);  // Creates JQTI+ TestSessionController
    
    // Clear instant messaging channel
    imService.clearChannel(entry.getOlatResource(), subIdent, getIdentity().getKey().toString());
}
```

#### 3.3 JQTI+ TestSessionController Integration

The `enterSession()` method creates the **JQTI+ TestSessionController** which is the reference implementation for QTI 2.1:

```java
private TestSessionController enterSession(UserRequest ureq) {
    // 1. Create TestProcessingMap from resolved assessment test
    TestProcessingMap testProcessingMap = getTestProcessingMap();
    
    // 2. Generate test plan
    TestPlanner testPlanner = new TestPlanner(testProcessingMap);
    TestPlan testPlan = testPlanner.generateTestPlan();
    
    // 3. Create TestSessionState
    TestSessionState testSessionState = new TestSessionState(testPlan);
    
    // 4. Create TestSessionController
    TestSessionControllerSettings settings = new TestSessionControllerSettings();
    settings.setTemplateProcessingLimit(computeTemplateProcessingLimit());
    
    testSessionController = new TestSessionController(
        qtiService.jqtiExtensionManager(), settings, testProcessingMap, testSessionState);
    
    // 5. Initialize and enter test
    testSessionController.initialize(ureq.getRequestTimestamp());
    int testPartCount = testSessionController.enterTest(ureq.getRequestTimestamp());
    
    if(testPartCount == 1) {
        testSessionController.enterNextAvailableTestPart(ureq.getRequestTimestamp());
    }
    
    // 6. Record ENTER_TEST event
    CandidateEvent candidateEvent = qtiService.recordCandidateTestEvent(
        candidateSession, testEntry, entry, CandidateTestEventType.ENTER_TEST,
        testSessionState, notificationRecorder);
    candidateAuditLogger.logCandidateEvent(candidateEvent);
    this.lastEvent = candidateEvent;
    
    return testSessionController;
}
```

#### 3.4 QtiWorksController — UI Rendering & Interaction

The inner class `QtiWorksController` (extends `AbstractQtiWorksController`) handles the actual UI:

**Form Components:**
- `AssessmentTestFormItem qtiEl` — Main test rendering component
- `AssessmentTreeFormItem qtiTreeEl` — Navigation tree
- `AssessmentTestTimerFormItem timerEl` — Timer display
- `ProgressBarItem scoreProgress` / `questionProgress` — Progress indicators
- Buttons: `endTestPartButton`, `closeTestButton`, `cancelTestButton`, `suspendTestButton`, `closeResultsButton`, `restartTest`

**Key Event Flow:**
```java
@Override
protected void formInnerEvent(UserRequest ureq, FormItem source, FormEvent event) {
    if(closeResultsButton == source) {
        doCloseResults(ureq);
    } else if(restartTest == source) {
        restartTest(ureq);
    } else if(!timeLimitBarrier(ureq) && !sessionReseted(ureq)) {
        if(endTestPartButton == source) {
            doEndTestPart(ureq);
        } else if(closeTestButton == source) {
            doCloseTest(ureq);
        } else if(cancelTestButton == source) {
            doCancelTest(ureq);
        } else if(suspendTestButton == source) {
            doSuspendTest(ureq);
        } else if(chatButton == source) {
            doChat();
        } else if(messagesButton == source) {
            doOpenMessages(ureq, messagesButton);
        } else if(source == qtiEl || source == qtiTreeEl) {
            if(event instanceof QTIWorksAssessmentTestEvent) {
                QTIWorksAssessmentTestEvent qwate = (QTIWorksAssessmentTestEvent)event;
                if(qwate.getEvent() == Event.tmpResponse) {
                    processPartialTemporaryResponse(ureq);  // Auto-save
                    return;
                } else if(qwate.getEvent() == Event.fullTmpResponse) {
                    processFullTemporaryResponse(ureq);     // Full auto-save
                    return;
                } else if(qwate.getEvent() == Event.mark) {
                    fireEvent(ureq, event);  // Toggle bookmark
                    return;
                } else {
                    fireEvent(ureq, event);  // Other navigation events
                }
            }
        } else if(source instanceof FormLink) {
            FormLink formLink = (FormLink)source;
            if("read".equals(formLink.getCmd())) {
                // Do nothing
            } else {
                processResponse(ureq, formLink);  // FINAL SUBMISSION
            }
        }
    }
    updateStatusAndResults(ureq);
}
```

#### 3.5 Response Handling — Core Submission Logic

**Three Response Types:**

| Event Type | Method | Purpose |
|------------|--------|---------|
| `tmpResponse` | `handleTemporaryResponse(..., true)` | Partial auto-save (e.g., typing in text field) |
| `fullTmpResponse` | `handleTemporaryResponse(..., false)` | Full auto-save (e.g., file upload) |
| `response` | `handleResponse()` | **Final submission** (user clicks Submit/Next) |

**Final Response Processing (`handleResponse`):**

```java
private void handleResponse(UserRequest ureq, Map<Identifier, ResponseInput> stringResponseMap,
        Map<Identifier, ResponseInput> fileResponseMap, String candidateComment) {
    
    // 1. Validate session state
    if(checkConcurrentExit(ureq)) return;
    
    TestSessionState testSessionState = testSessionController.getTestSessionState();
    TestPlanNodeKey currentItemKey = testSessionState.getCurrentItemKey();
    
    // 2. Validate the presented item matches (prevent stale submissions)
    if(!qtiWorksCtrl.validatePresentedItem(currentItemKey)) {
        logError("Response send by browser doesn't match current item key");
        return;
    }
    
    // 3. Map response data from UI to QTI ResponseData
    Map<Identifier, ResponseData> responseDataMap = new HashMap<>();
    Map<Identifier, File> fileSubmissionMap = new HashMap<>();
    mapStringResponseData(stringResponseMap, responseDataMap, fileSubmissionMap);
    mapFileResponseDate(fileResponseMap, responseDataMap, fileSubmissionMap);
    
    // 4. Get or create AssessmentItemSession
    ParentPartItemRefs parentParts = getParentSection(currentItemKey);
    String assessmentItemIdentifier = currentItemKey.getIdentifier().toString();
    AssessmentItemSession itemSession = qtiService.getOrCreateAssessmentItemSession(
        candidateSession, parentParts, assessmentItemIdentifier, null);
    
    // 5. Map to AssessmentResponse entities (for persistence)
    Map<Identifier, AssessmentResponse> candidateResponseMap = qtiService
        .getAssessmentResponses(itemSession);
    for (Entry<Identifier, ResponseData> responseEntry : responseDataMap.entrySet()) {
        mapCandidateResponse(responseEntry.getKey(), responseEntry.getValue(),
            itemSession, candidateResponseMap, fileSubmissionMap);
    }
    
    // 6. BIND RESPONSE IN JQTI+ (performs Response Processing)
    testSessionController.handleResponsesToCurrentItem(timestamp, responseDataMap);
    
    // 7. Classify event type based on submission mode
    SubmissionMode submissionMode = testSessionController.getCurrentTestPart().getSubmissionMode();
    CandidateItemEventType candidateItemEventType;
    if (allResponsesValid) {
        candidateItemEventType = (submissionMode == SubmissionMode.INDIVIDUAL)
            ? CandidateItemEventType.ATTEMPT_VALID 
            : CandidateItemEventType.RESPONSE_VALID;
    } else {
        candidateItemEventType = allResponsesBound
            ? CandidateItemEventType.RESPONSE_INVALID 
            : CandidateItemEventType.RESPONSE_BAD;
    }
    
    // 8. Record candidate event (audit log)
    CandidateEvent candidateEvent = qtiService.recordCandidateTestEvent(
        candidateSession, testEntry, entry,
        CandidateTestEventType.ITEM_EVENT, candidateItemEventType,
        currentItemKey, testSessionState, notificationRecorder);
    candidateAuditLogger.logCandidateEvent(candidateEvent, candidateResponseMap);
    this.lastEvent = candidateEvent;
    
    // 9. Compute and record test assessment result (scoring)
    AssessmentResult assessmentResult = computeAndRecordTestAssessmentResult(
        timestamp, testSessionState, false);
    
    // 10. Update item session metadata
    ItemSessionState itemSessionState = testSessionState.getCurrentItemSessionState();
    itemSession.setDuration(itemSessionState.getDurationAccumulated());
    itemSession.setAttempts(itemSessionState.getNumAttempts());
    ItemResult itemResult = assessmentResult.getItemResult(assessmentItemIdentifier);
    collectOutcomeVariablesForItemSession(itemResult, itemSession);
    
    // 11. Persist AssessmentResponse entities
    qtiService.recordTestAssessmentResponses(itemSession, candidateResponseMap.values());
    
    // 12. Save session state
    candidateSession = qtiService.updateAssessmentTestSession(candidateSession);
    
    // 13. Auto-advance if allowed
    nextItemIfAllowed(ureq);
}
```

#### 3.6 Assessment Result Computation

```java
private AssessmentResult computeAndRecordTestAssessmentResult(
        Date requestTimestamp, TestSessionState testSessionState, boolean submit) {
    
    // 1. Compute assessment result via JQTI+
    AssessmentResult assessmentResult = computeTestAssessmentResult(requestTimestamp, candidateSession);
    
    // 2. Update session metadata (question counts, max score)
    TestPlanInfos testPlanInfos = new TestPlanInfos();
    testSessionController.visitTestPlan(testPlanInfos);
    candidateSession.setNumOfQuestions(testPlanInfos.getNumOfItems());
    candidateSession.setNumOfAnsweredQuestions(testPlanInfos.getNumOfAnsweredItems());
    candidateSession.setMaxScore(BigDecimal.valueOf(testPlanInfos.getMaxScore()));
    
    // 3. Persist via QTI21Service (synchronized)
    synchronized(this) {
        candidateSession = qtiService.recordTestAssessmentResult(
            candidateSession, testSessionState, assessmentResult, candidateAuditLogger);
    }
    
    // 4. Process outcome variables (score, pass) → OutcomesListener
    processOutcomeVariables(assessmentResult.getTestResult(), testPlanInfos, submit);
    
    return assessmentResult;
}
```

**Outcome Variable Processing:**
```java
private void processOutcomeVariables(TestResult resultNode, TestPlanInfos testPlanInfos, boolean submit) {
    Float score = null;
    Boolean pass = null;
    double completion = testPlanInfos.getCompletion();
    
    for (ItemVariable itemVariable : resultNode.getItemVariables()) {
        if (itemVariable instanceof OutcomeVariable) {
            OutcomeVariable outcomeVariable = (OutcomeVariable) itemVariable;
            Identifier identifier = outcomeVariable.getIdentifier();
            
            if (QTI21Constants.SCORE_IDENTIFIER.equals(identifier)) {
                Value value = itemVariable.getComputedValue();
                if (value instanceof NumberValue) {
                    score = (float) ((NumberValue) value).doubleValue();
                }
            } else if (QTI21Constants.PASS_IDENTIFIER.equals(identifier)) {
                Value value = itemVariable.getComputedValue();
                if (value instanceof BooleanValue) {
                    pass = ((BooleanValue) value).booleanValue();
                }
            }
        }
    }
    
    if (submit) {
        // FINAL SUBMISSION — updates AssessmentEntry
        outcomesListener.submit(score, pass, candidateSession.getCreationDate(), 
            completion, candidateSession.getKey());
    } else if(candidateSession != null && candidateSession.getFinishTime() == null) {
        // INTERIM UPDATE — doesn't change AssessmentEntry status
        outcomesListener.updateOutcomes(score, pass, candidateSession.getCreationDate(), completion);
    }
}
```

---

### Step 4: Outcomes Listener — `AssessmentEntryOutcomesListener`

**File:** `src/main/java/org/olat/ims/qti21/ui/AssessmentEntryOutcomesListener.java`

This bridges the QTI assessment result to the OpenOlat **AssessmentEntry** (course grade book):

```java
@Override
public void submit(Float submittedScore, Boolean submittedPass, Date startTime, 
        Double completion, Long assessmentId) {
    
    // 1. Determine status based on manual correction requirement
    AssessmentEntryStatus assessmentStatus;
    if(needManualCorrection) {
        assessmentStatus = AssessmentEntryStatus.inReview;  // Needs human grading
    } else {
        assessmentStatus = AssessmentEntryStatus.done;      // Auto-graded complete
    }
    assessmentEntry.setAssessmentStatus(assessmentStatus);
    
    // 2. Set score (scaled to course score scale)
    if(submittedScore == null) {
        assessmentEntry.setScore(null);
        assessmentEntry.setWeightedScore(null);
        assessmentEntry.setScoreScale(null);
    } else {
        assessmentEntry.setScore(new BigDecimal(Float.toString(submittedScore)));
        assessmentEntry.setWeightedScore(
            ScoreScalingHelper.getWeightedScore(submittedScore, scoreScale));
        assessmentEntry.setScoreScale(scoreScale);
    }
    
    // 3. Set pass/fail and completion
    assessmentEntry.setPassed(submittedPass);
    assessmentEntry.setCompletion(completion);
    assessmentEntry.setAssessmentId(assessmentId);  // Links to AssessmentTestSession
    
    // 4. Increment attempt counter (only once per session)
    if(incrementAttempts.getAndSet(false)) {
        int currentAttempts = assessmentEntry.getAttempts() == null ? 0 
            : assessmentEntry.getAttempts().intValue();
        assessmentEntry.setAttempts(currentAttempts + 1);
        assessmentEntry.setLastAttempt(new Date());
    }
    
    // 5. Persist
    assessmentEntry = assessmentService.updateAssessmentEntry(assessmentEntry);
    
    // 6. Digital signature handling
    boolean firstClose = close.getAndSet(false);
    if(firstClose && !authorMode) {
        ThreadLocalUserActivityLogger.log(QTI21LoggingAction.QTI_CLOSE_AS_RESOURCE, getClass());
    }
}
```

---

### Step 5: Test Completion & Exit

#### 5.1 Finishing a Test Part
```java
private void processEndTestPart(UserRequest ureq) {
    // End current test part in JQTI+
    testSessionController.endCurrentTestPart(requestTimestamp);
    
    TestSessionState testSessionState = testSessionController.getTestSessionState();
    TestPlanNode nextTestPart = testSessionController.findNextEnterableTestPart();
    
    // Record final result for this part
    AssessmentResult assessmentResult = computeAndRecordTestAssessmentResult(
        requestTimestamp, testSessionState, nextTestPart == null);
    
    if(nextTestPart == null) {
        // NO MORE PARTS — FINISH ENTIRE TEST
        candidateSession = qtiService.finishTestSession(
            candidateSession, testSessionState, assessmentResult,
            requestTimestamp, getDigitalSignatureOptions(), getIdentity());
        
        // If no feedback to show, exit immediately
        if(!qtiWorksCtrl.willShowSomeAssessmentTestFeedbacks()) {
            testSessionController.enterNextAvailableTestPart(requestTimestamp);
            testSessionController.exitTest(requestTimestamp);
            candidateSession.setTerminationTime(requestTimestamp);
            candidateSession = qtiService.updateAssessmentTestSession(candidateSession);
            
            // Record EXIT_TEST event
            CandidateEvent candidateTestEvent = qtiService.recordCandidateTestEvent(...);
            candidateAuditLogger.logCandidateEvent(candidateTestEvent);
            
            qtiWorksCtrl.updateStatusAndResults(ureq);
            doExitTest(ureq);  // Fire EXIT event
        }
    } else if(!qtiWorksCtrl.willShowSomeTestPartFeedbacks()) {
        // More parts but no feedback — auto-advance
        processAdvanceTestPart(ureq);
    }
}
```

#### 5.2 Time Limit Handling
```java
private void processExitTestAfterTimeLimit(UserRequest ureq) {
    synchronized(testSessionController) {
        TestSessionState testSessionState = testSessionController.getTestSessionState();
        if(testSessionState.isEnded() || testSessionState.isExited()) return;
        
        // Close duration tracking
        testSessionController.touchDurations(testSessionController.getCurrentRequestTimestamp());
        
        // Exit incomplete
        testSessionController.exitTestIncomplete(requestTimestamp);
        candidateSession.setTerminationTime(requestTimestamp);
        
        // Final scoring
        AssessmentResult assessmentResult = computeAndRecordTestAssessmentResult(
            requestTimestamp, testSessionState, true);
        candidateSession = qtiService.finishTestSession(
            candidateSession, testSessionState, assessmentResult,
            requestTimestamp, getDigitalSignatureOptions(), getIdentity());
        
        // Record TIME_LIMIT exit event
        CandidateEvent candidateTestEvent = qtiService.recordCandidateTestEvent(
            candidateSession, testEntry, entry,
            CandidateTestEventType.EXIT_DUE_TIME_LIMIT, testSessionState, notificationRecorder);
        candidateAuditLogger.logCandidateEvent(candidateTestEvent);
        
        qtiWorksCtrl.updateStatusAndResults(ureq);
        doExitTest(ureq);
    }
}
```

#### 5.3 Results Display
When the test ends and `deliveryOptions.isShowAssessmentResultsOnFinish()` is true:

```java
private boolean updateStatusAndResults(UserRequest ureq) {
    if(testSessionController.getTestSessionState().isEnded()
            && deliveryOptions.isShowAssessmentResultsOnFinish()
            && deliveryOptions.getAssessmentResultsOptions() != null
            && !deliveryOptions.getAssessmentResultsOptions().none()) {
        
        removeAsListenerAndDispose(resultCtrl);
        AssessmentTestSession cSession = getCandidateSession(true);
        
        resultCtrl = new AssessmentResultController(
            ureq, getWindowControl(), assessedIdentity, true,
            cSession, fUnzippedDirRoot, mapperUri, null,
            deliveryOptions.getAssessmentResultsOptions(), false, true, true);
        listenTo(resultCtrl);
        flc.add("qtiResults", resultCtrl.getInitialFormItem());
        
        if(cSession.isAuthorMode() && cSession.getTestEntry().equals(cSession.getRepositoryEntry())) {
            restartTest.setVisible(true);
        }
        resultsVisible = true;
    }
    // ... button visibility updates
}
```

---

### Step 6: Persistence Layer — Data Model

#### 6.1 AssessmentTestSession Entity (`AssessmentTestSessionImpl`)

**Table:** `o_qti_assessmenttest_session`

| Field | Column | Description |
|-------|--------|-------------|
| `key` | `id` | Primary key |
| `creationDate` | `creationdate` | Session creation timestamp |
| `lastModified` | `lastmodified` | Last update timestamp |
| `assessmentEntry` | `fk_assessment_entry` | Link to course grade book entry |
| `testEntry` | `fk_reference_entry` | The test (QTI package) repository entry |
| `repositoryEntry` | `fk_entry` | Course repository entry (if in course) |
| `subIdent` | `q_subident` | Course element identifier |
| `identity` | `fk_identity` | Assessed user (null for anonymous) |
| `anonymousIdentifier` | `q_anon_identifier` | Anonymous session ID |
| `authorMode` | `q_author_mode` | Author preview mode |
| `storage` | `q_storage` | VFS path for session files |
| `finishTime` | `q_finish_time` | QTI "finished" (reached end) |
| `terminationTime` | `q_termination_time` | Session terminated (closed) |
| `duration` | `q_duration` | Total duration in milliseconds |
| `passed` | `q_passed` | Pass/fail result |
| `score` | `q_score` | Computed score |
| `manualScore` | `q_manual_score` | Manual override score |
| `maxScore` | `q_max_score` | Maximum possible score |
| `numOfQuestions` | `q_num_questions` | Total questions |
| `numOfAnsweredQuestions` | `q_num_answered_questions` | Answered questions |
| `extraTime` | `q_extra_time` | Extra time granted (seconds) |
| `compensationExtraTime` | `q_compensation_extra_time` | Disadvantage compensation time |
| `exploded` | `q_exploded` | Session failed/corrupted |
| `cancelled` | `q_cancelled` | User cancelled |

#### 6.2 AssessmentItemSession
- One per assessment item (question) in the test
- Stores: response data, duration, attempts, score, pass status
- Linked to `AssessmentTestSession` and `AssessmentItemSessionRef`

#### 6.3 AssessmentResponse
- One per response variable (interaction) in an item
- Stores: response identifier, legality (VALID/INVALID), stringified response
- File submissions stored in VFS under session storage

#### 6.4 Storage Path Structure
```
bcroot/qtiassessment/
├── {courseRepositoryEntryKey}/
│   └── {courseNodeSubIdent}/
│       └── {identityKey}_{timestamp}_{testRepositoryEntryKey}/
└── {testRepositoryEntryKey}/
    └── {identityKey}_{timestamp}/
```

---

## 3. Key Configuration — `QTI21DeliveryOptions`

Controls the test behavior and UI:

| Option | Default | Description |
|--------|---------|-------------|
| `enableCancel` | false | Allow user to cancel test |
| `enableSuspend` | false | Allow user to suspend/resume |
| `displayScoreProgress` | false | Show score progress bar |
| `displayQuestionProgress` | false | Show question progress bar |
| `displayMaxScoreItem` | true | Show max score per item |
| `showMenu` | true | Show navigation tree |
| `showTitles` | true | Show item titles |
| `hideFeedbacks` | false | Hide immediate feedback |
| `blockAfterSuccess` | false | Block retakes after pass |
| `maxAttempts` | 0 | Max attempts (0 = unlimited) |
| `digitalSignature` | false | Require digital signature on finish |
| `digitalSignatureMail` | false | Email signature confirmation |
| `showAssessmentResultsOnFinish` | false | Show results after completion |
| `assessmentResultsOptions` | none | What results to show (none/compact/sections/details) |
| `passedType` | manually | How pass/fail determined (cutValue/manually) |
| `chatCoaches` / `chatOwners` | false | Enable chat with coaches/owners |
| `pageMode` | false | Page-by-page navigation |
| `lastQuestion` | false | Show "last question" indicator |

**Presets:**
- `defaultSettings()` — Standard settings
- `formativeSettings()` — Practice mode (suspend, cancel, show results)
- `summativeSettings()` — Exam mode (no suspend, no results, 1 attempt)

---

## 4. Events & Audit Trail

### 4.1 CandidateEvent Types (Test Level)
- `ENTER_TEST` — Session started
- `SELECT_MENU` — Non-linear item selection
- `NEXT_ITEM` — Linear next item
- `FINISH_ITEM` — Linear finish item
- `FINISH_FINAL_ITEM` — Last item finished
- `ADVANCE_TEST_PART` — Move to next test part
- `REVIEW_TEST_PART` — Review completed test part
- `EXIT_TEST` — Normal exit
- `EXIT_DUE_TIME_LIMIT` — Time expired
- `SUSPEND` — Session suspended
- `RESTART` — Author restart

### 4.2 CandidateItemEventType (Item Level)
- `RESPONSE_TEMPORARY` — Auto-save
- `RESPONSE_VALID` — Valid final response
- `RESPONSE_INVALID` — Invalid response
- `RESPONSE_BAD` — Bad response
- `ATTEMPT_VALID` — Valid attempt (individual submission mode)
- `RESPONSE_REMOVED` — Response deleted
- `ITEM_EVENT` — Generic item event

### 4.3 Audit Logging
All events logged via `AssessmentSessionAuditLogger` to:
- Database (via `CandidateEvent` entity)
- File system (`bcroot/qtiassessment/{session}/audit.log`)

---

## 5. Extension Points for fLMS / PIX Simulators

### 5.1 Custom QTI Interactions
OpenOlat uses **JQTI+** (uk.ac.ed.ph.jqtiplus) as the QTI 2.1 engine. Custom interactions can be added via:
- `QTI21Service.jqtiExtensionManager()` → `JqtiExtensionManager`
- Register custom `Interaction` types, `ResponseProcessing` extensions
- Location: `src/main/java/org/olat/ims/qti21/` extensions

### 5.2 Custom Delivery Options
Extend `QTI21DeliveryOptions` with:
- `PIXSimulatorOptions` — PIX-specific configuration
- Custom `TestType` enum values
- Custom `AssessmentResultsOptions` for PIX result presentation

### 5.3 Scoring & Grading Hooks
- `AssessmentEntryOutcomesListener` — Override `submit()` for custom grade processing
- `OutcomesListener` interface — Implement custom score/pass handling
- `AssessmentTestHelper.needManualCorrection()` — Flag items needing human review

### 5.4 Result Presentation
- `AssessmentResultController` — Customize result rendering
- `QTI21AssessmentResultsOptions` — Control what results are shown
- Velocity templates in `_content/` for result display

### 5.5 Event Bus Integration
- `CandidateEvent` fired on `EventBus` for cross-session notifications
- Register listeners for: `ENTER_TEST`, `EXIT_TEST`, `SUSPEND`, `FINISH_FINAL_ITEM`
- Use `coordinator.getEventBus().registerFor(this, identity, sessionOres)`

### 5.6 Disadvantage Compensation
- `DisadvantageCompensationService` — Query extra time per user/course element
- Applied automatically in `AssessmentTestDisplayController.initOrResumeAssessmentTestSession()`

### 5.7 Digital Signatures
- `DigitalSignatureOptions` — Configure signature on test completion
- `QTI21Service.signAssessmentResult()` — Generate XML-DSig
- `AssessmentEntryOutcomesListener.decorateConfirmation()` — Customize email

### 5.8 VFS Storage
- Session files stored in `bcroot/qtiassessment/`
- `QTI21Service.getSubmissionDirectory()` — Access submission files
- `QTI21Service.importFileSubmission()` — Handle file uploads

---

## 6. Data Ownership & Flow Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                     STUDENT BROWSER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Question    │  │  Response    │  │  Submit/Next Button  │  │
│  │  Rendering   │──►│  Input       │──►│  (Form POST)         │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ASSESSMENTTESTDISPLAYCONTROLLER                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  QtiWorksController (AbstractQtiWorksController)         │  │
│  │  ├── AssessmentTestFormItem ← Renders QTI via JQTI+     │  │
│  │  ├── AssessmentTreeFormItem ← Navigation tree           │  │
│  │  └── Form event handling (tmpResponse, response, etc.)  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  handleResponse() / handleTemporaryResponse()            │  │
│  │  ├── Map UI responses → QTI ResponseData                 │  │
│  │  ├── testSessionController.handleResponsesToCurrentItem()│  │
│  │  │    (JQTI+ Response Processing & Outcome Processing)  │  │
│  │  ├── Create/update AssessmentResponse entities           │  │
│  │  ├── computeAndRecordTestAssessmentResult()              │  │
│  │  │    ├── testSessionController.computeAssessmentResult()│  │
│  │  │    ├── qtiService.recordTestAssessmentResult()        │  │
│  │  │    └── outcomesListener.submit() / updateOutcomes()   │  │
│  │  └── qtiService.updateAssessmentTestSession()            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      QTI21SERVICE (Spring Bean)                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────┐   │
│  │ AssessmentTest  │  │ AssessmentItem  │  │ Assessment    │   │
│  │ SessionDAO      │  │ SessionDAO      │  │ ResponseDAO   │   │
│  └─────────────────┘  └─────────────────┘  └───────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DATABASE (Hibernate/JPA)                 │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────────┐  │
│  │ o_qti_         │ │ o_qti_         │ │ o_qti_             │  │
│  │ assessmenttest │ │ assessmentitem │ │ assessmentresponse │  │
│  │ _session       │ │ _session       │ │                    │  │
│  └────────────────┘ └────────────────┘ └────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ o_as_assessmententry (Course Grade Book)                 │  │
│  │   score, weightedScore, passed, status, attempts, ...   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      VFS (bcroot/qtiassessment/)                │
│  • Session serialization (JQTI+ state)                          │
│  • File submissions (uploads, drawings)                         │
│  • Audit logs                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Completion Status Retrieval

### For Students (Course Run)
```java
// In RunMainController → NavigationHandler → CourseNodeRunController
// The course element shows status via:
// - AssessmentEntry status (inProgress, inReview, done)
// - AssessmentEntry score/passed
// - AssessmentEntry completion percentage
```

### For Teachers/Coaches (Grading)
```java
// IQIdentityListCourseNodeController
// Shows all participant sessions with:
// - AssessmentTestSession list (running, finished, terminated)
// - AssessmentTestSessionStatistics (num corrected items)
// - AssessmentEntry status and scores
// Actions: reopen, pull (terminate), grant extra time, digital signature
```

### For Reporting/Analytics
```java
// QTI21Service.getAssessmentTestSessionsStatistics()
// Returns AssessmentTestSessionStatistics with:
// - Session key, test entry, creation date, finish time
// - Score, max score, passed, num corrected items
// - Duration, extra time
```

---

## 8. Critical Implementation Notes

### 8.1 Thread Safety
- `AssessmentTestDisplayController` uses `synchronized(this)` for result computation
- `TestSessionController` from JQTI+ is NOT thread-safe — stored per-session in cache
- `qtiService.putCachedTestSessionController()` / `getCachedTestSessionController()` manage cache

### 8.2 Session Lifecycle States
| State | finishTime | terminationTime | Meaning |
|-------|------------|-----------------|---------|
| In Progress | null | null | Active session |
| Finished (reviewing) | set | null | Reached end, can review |
| Terminated | set | set | Closed, no more access |
| Cancelled | null | null | `cancelled=true` |
| Exploded | null | null | `exploded=true` (error) |

### 8.3 Time Tracking
- `TestSessionState.getDurationAccumulated()` — Server-side accumulated time
- `getRequestTimeStampDifferenceToNow()` — Client-server delta per request
- `extraTime` + `compensationExtraTime` added to test time limit

### 8.4 Cleanup on Dispose
```java
@Override
protected void doDispose() {
    // Deregister window resource
    resourcesList.deregisterResourceable(entry, subIdent, getWindow());
    
    // Suspend session (save state for resume)
    candidateSession = qtiService.reloadAssessmentTestSession(candidateSession);
    testSessionController = qtiService.getCachedTestSessionController(candidateSession, testSessionController);
    suspendAssessmentTest(new Date());
    
    // Deregister EventBus
    OLATResourceable sessionOres = OresHelper.createOLATResourceableInstance(
        AssessmentTestSession.class, candidateSession.getKey());
    coordinator.getEventBus().deregisterFor(this, sessionOres);
}
```

---

## 9. Files Referenced

| File | Purpose |
|------|---------|
| `IQTESTCourseNode.java` | Course element entry point |
| `QTI21AssessmentRunController.java` | Participant run controller |
| `AssessmentTestDisplayController.java` | Core assessment controller |
| `AssessmentEntryOutcomesListener.java` | Score persistence bridge |
| `QTI21Service.java` | Service interface |
| `AssessmentTestSessionDAO.java` | DAO implementation |
| `AssessmentTestSessionImpl.java` | JPA entity |
| `QTI21DeliveryOptions.java` | Test configuration |
| `AssessmentResultController.java` | Results display |
| `DigitalSignatureOptions.java` | Signature configuration |
| `DisadvantageCompensationService.java` | Extra time for disabilities |

---

## 10. Conclusion

The OpenOlat assessment submission workflow is a **well-architected, standards-compliant** implementation of **QTI 2.1** using the **JQTI+** reference engine. Key strengths:

1. **Clear separation of concerns** — UI (`AssessmentTestDisplayController`), QTI engine (`TestSessionController`), persistence (`QTI21Service`/DAO), grade book (`AssessmentEntryOutcomesListener`)
2. **Full audit trail** — Every interaction logged as `CandidateEvent`
3. **Resume capability** — Sessions persisted and resumable
4. **Flexible configuration** — `QTI21DeliveryOptions` supports formative/summative modes
5. **Extensibility** — Multiple hooks for custom interactions, scoring, results, events

**Safe fLMS/PIX Extension Points:**
- Custom QTI interactions via JQTI+ extensions
- Custom `OutcomesListener` for PIX scoring
- Custom `AssessmentResultController` for PIX result presentation
- EventBus listeners for PIX progress tracking
- Delivery options for PIX-specific test behavior
- VFS storage for PIX simulator artifacts

---

*Document generated as part of Phase 4.3 investigation. Source code as of commit 20e0b6b2f1 (OpenOLAT 21.2-SNAPSHOT).*
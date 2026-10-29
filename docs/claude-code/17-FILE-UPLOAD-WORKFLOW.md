# Phase 4.4 — File Upload Workflow Trace

**Date:** 2026-10-22  
**Objective:** Trace the complete file upload workflow from user selecting a file through browser to file persistence in VFS, including quota management, validation, and course element integration.

---

## Executive Summary

This document traces the file upload workflow in OpenOlat, focusing on the **Task (TA) Course Node** as the primary example, which includes **Dropbox** for student submissions, **Returnbox** for teacher feedback, and **Solution** folders. The core upload mechanism uses the **FlexiForm FileElement** with multipart handling, temporary file storage, and VFS (Virtual File System) persistence.

**Key Files Analyzed:**
- `src/main/java/org/olat/core/gui/components/form/flexible/elements/FileElement.java` — File upload interface
- `src/main/java/org/olat/core/gui/components/form/flexible/impl/elements/FileElementImpl.java` — File upload implementation (multipart handling, temp storage, VFS move)
- `src/main/java/org/olat/course/nodes/ta/DropboxController.java` — Student submission upload controller
- `src/main/java/org/olat/course/nodes/ta/FileChooserController.java` — Upload form controller
- `src/main/java/org/olat/course/nodes/ta/TaskController.java` — Task selection and file delivery
- `src/main/java/org/olat/course/nodes/ta/ReturnboxController.java` — Teacher feedback file access
- `src/main/java/org/olat/course/nodes/ta/SolutionController.java` — Published solutions access
- `src/main/java/org/olat/core/util/vfs/VFSManager.java` — VFS operations (copy, resolve, quota)
- `src/main/java/org/olat/core/util/vfs/LocalFolderImpl.java` / `LocalFileImpl.java` — Local FS implementation

---

## 1. Workflow Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STUDENT BROWSER                                    │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────────────────┐    │
│  │  Dropbox UI  │──►│  FileChooser │──►│  Multipart Form POST             │    │
│  │  (Upload btn)│   │  (Modal)     │   │  (file + metadata)               │    │
│  └──────────────┘   └──────────────┘   └──────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         OPENOLAT SERVER (Servlet)                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  Dispatcher → Window (synchronized) → Form → FileElementImpl.evalFormRequest() │   │
│  │  1. Parse multipart request                                              │   │
│  │  2. Move file from servlet temp → OpenOlat temp (WebappHelper.getTmpDir()) │   │
│  │  3. Validate (size, mime type, max files)                                │   │
│  │  4. Fire UploadFileElementEvent (ONCHANGE)                               │   │
│  │  5. FormBasicController.formOK() → DONE_EVENT                            │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      DROPBOXCONTROLLER (Event Handler)                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  1. Get UploadFile from FileChooserController                            │   │
│  │  2. Get/Calculate upload limit via QuotaManager                          │   │
│  │  3. VFSManager.olatRootContainer(dropboxPath) → LocalFolderImpl          │   │
│  │  4. Check quota via FullAccessWithQuotaCallback                          │   │
│  │  5. FileElement.moveUploadFileTo(VFSContainer)                           │   │
│  │     → VFSManager.copyContent(tempFile, targetLeaf, identity)             │   │
│  │  6. Update UI (file list, count)                                         │   │
│  │  7. Send notification email if configured                                │   │
│  │  8. Fire EventBus notification (DropboxFileUploadNotificationHandler)    │   │
│  │  9. Increment assessment attempts counter                                │   │
│  │ 10. Audit log entry (UserNodeAuditManager)                               │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           VFS / FILESYSTEM (bcroot/)                            │
│  /bcroot/course/{courseId}/                                                     │
│    ├── dropboxes/{nodeIdent}/{userName}/{filename}      ← Student submissions  │
│    ├── returnboxes/{nodeIdent}/{userName}/{filename}    ← Teacher feedback     │
│    ├── solutions/{nodeIdent}/{filename}                 ← Published solutions  │
│    └── taskfolders/{nodeIdent}/{filename}               ← Available tasks      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Detailed Step-by-Step Trace

### Step 1: Browser → Multipart Form Submission

**HTML Form (Velocity Template):**
```velocity
## dropbox.html template
<form method="post" enctype="multipart/form-data" ...>
  <input type="file" name="file" ...>
  <input type="hidden" name="dispatchuri" value="...formDispatchId...">
  <button type="submit" name="save">Upload</button>
</form>
```

The form uses `enctype="multipart/form-data"` for file uploads. The `dispatchuri` identifies which `FormElement` should handle the upload.

---

### Step 2: Servlet → Form → FileElementImpl.evalFormRequest()

**File:** `FileElementImpl.java:136-177`

```java
@Override
public void evalFormRequest(UserRequest ureq) {
    Form form = getRootForm();
    
    String dispatchuri = form.getRequestParameter("dispatchuri");
    String uploadDirectory = form.getRequestParameter("upload-folder");
    String dropped = form.getRequestParameter("dropped-filename");

    // Handle drag-drop or delete events
    if (dispatchuri != null && dispatchuri.equals(component.getFormDispatchId())) {
        if("delete".equals(form.getRequestParameter("delete"))) {
            // Handle delete
        } else if(StringHelper.containsNonWhitespace(uploadDirectory) && StringHelper.containsNonWhitespace(dropped)) {
            // Handle drag-drop
            return;
        }
    }
    
    // GET MULTIPART FILE INFOS
    List<MultipartFileInfos> list = form.getRequestMultipartFileInfosList(component.getFormDispatchId());
    if (!list.isEmpty()) {
        // Remove old files first (single file mode)
        if (!multiFileUpload && !tempUploadFiles.isEmpty()) {
            deleteTempUploadFiles();
        }
        
        // PROCESS EACH UPLOADED FILE
        long uploadLimit = multiFileUpload? Long.MAX_VALUE: Long.valueOf(1);
        List<File> tempUploadFileList = list.stream()
            .limit(uploadLimit)
            .map(fileInfos -> evaluateFile(fileInfos, ureq.getUserSession()))
            .collect(Collectors.toList());
        
        // Mark component dirty for re-render
        component.setDirty(true);
        validate();
        
        // Fire event to parent controller
        getRootForm().fireFormEvent(ureq, new UploadFileElementEvent(this, tempUploadFileList,
                List.copyOf(tempUploadFiles), uploadDirectory, FormEvent.ONCHANGE));
    }
}
```

**Key Point:** The servlet container parses multipart request and stores files in its temp directory. `FileElementImpl` moves them to OpenOlat's own temp directory for controlled lifecycle.

---

### Step 3: FileElementImpl.evaluateFile() — Temp File Creation

**File:** `FileElementImpl.java:179-225`

```java
private File evaluateFile(MultipartFileInfos fileInfos, UserSession usess) {
    // 1. CREATE OPENOLAT TEMP FILE
    File tempUploadFile = new File(WebappHelper.getTmpDir(), CodeHelper.getUniqueID());
    
    // 2. MOVE FROM SERVLET TEMP TO OPENOLAT TEMP
    boolean success = fileInfos.file().renameTo(tempUploadFile);
    if (!success) {
        // Cross-volume fallback: copy instead of rename
        FileUtils.copyFileToFile(fileInfos.file(), tempUploadFile, true);
    }

    // 3. CLEAN FILENAME
    String uploadFilename = fileInfos.fileName();
    uploadFilename = FileUtils.cleanFilename(uploadFilename, maxFilenameLength);
    
    // 4. DETERMINE MIME TYPE
    String uploadMimeType = WebappHelper.getMimeType(uploadFilename);
    if (uploadMimeType == null) {
        uploadMimeType = fileInfos.contentType();  // Browser fallback
    }
    if (uploadMimeType == null) {
        uploadMimeType = "application/octet-stream";  // Final fallback
    }

    // 5. CREATE PREVIEW (for images/videos)
    ImageFormItem previewEl = null;
    if (preview && uploadMimeType != null
            && (uploadMimeType.startsWith("image/") || uploadMimeType.startsWith("video/"))
            && (!checkForMimeTypes || (isMimeTypeAllowed(uploadMimeType)))) {
        VFSLeaf media = new LocalFileImpl(tempUploadFile);
        previewEl = new ImageFormItem(usess, getName() + "_PREVIEW");
        previewEl.setRootForm(getRootForm());
        previewEl.setMedia(media, uploadMimeType);
        previewEl.setCropSelectionEnabled(cropSelectionEnabled);
        previewEl.setMaxWithAndHeightToFitWithin(300, 200);
        previewEl.setVisible(true);
    }
    
    // 6. STORE IN TEMP LIST
    tempUploadFiles.add(new FileElementInfos(tempUploadFile, uploadFilename, tempUploadFile.length(), uploadMimeType, previewEl));
    return tempUploadFile;
}
```

**Temp File Lifecycle:**
- Created in `WebappHelper.getTmpDir()` (typically `java.io.tmpdir`/olat/)
- Unique name via `CodeHelper.getUniqueID()`
- Cleaned up on `FileElementImpl.dispose()` or form disposal
- Moved to final destination via `moveUploadFileTo()`

---

### Step 4: FormBasicController → FormOK → DONE_EVENT

**File:** `FileChooserController.java:98-105`

```java
@Override
protected void formOK(UserRequest ureq) {
    fireEvent(ureq, Event.DONE_EVENT);
}

@Override
protected void formCancelled(UserRequest ureq) {
    fireEvent(ureq, Event.CANCELLED_EVENT);
}
```

The `FileChooserController` (extends `FormBasicController`) fires `DONE_EVENT` when upload form is submitted successfully.

---

### Step 5: DropboxController — Event Handler

**File:** `DropboxController.java:217-331`

```java
@Override
public void event(UserRequest ureq, Controller source, Event event) {
    if (source == fileChooserController) {
        cmc.deactivate();  // Close modal
        
        if (event.equals(Event.DONE_EVENT)) {
            boolean success = false;
            File fIn = fileChooserController.getUploadFile();      // Temp file
            VFSContainer fDropbox = getDropBox(ureq.getIdentity()); // Target VFS container
            String filename = fileChooserController.getUploadFileName();

            // HANDLE DUPLICATE FILENAMES
            VFSLeaf fOut;
            if (fDropbox.resolve(filename) != null) {
                fOut = fDropbox.createChildLeaf(getNewUniqueName(filename));
            } else {
                fOut = fDropbox.createChildLeaf(filename);
            }
            
            // COPY TO VFS (PERSISTENCE)
            success = VFSManager.copyContent(fIn, fOut, getIdentity());
            
            if (success) {
                // UPDATE UI
                int numFiles = fDropbox.getItems(new VFSSystemItemFilter()).size();
                myContent.contextPut("numfiles", new String[] {Integer.toString(numFiles)});
                myContent.contextPut("filelist", fDropbox.getItems());
                
                // EMAIL CONFIRMATION
                Boolean sendEmail = (Boolean)config.get(TACourseNode.CONF_DROPBOX_ENABLEMAIL);
                if (sendEmail != null && sendEmail.booleanValue()) {
                    sendConfirmationEmail(ureq, fOut.getName());
                }
                
                // NOTIFICATION EVENT
                if (subsContext != null) {
                    notificationsManager.markPublisherNews(subsContext, ureq.getIdentity(), true);
                }
                
                // ASSESSMENT ATTEMPT INCREMENT
                courseAssessmentService.incrementAttempts(node, userCourseEnv, Role.user);
                
                // AUDIT LOG
                UserNodeAuditManager am = userCourseEnv.getCourseEnvironment().getAuditManager();
                am.appendToUserNodeLog(node, identity, identity, "FILE UPLOADED: " + filename, null);
                
                // SUCCESS MESSAGE
                getWindowControl().setInfo(confirmation);
            } else {
                showInfo("dropbox.upload.failed");
            }
        }
    }
}
```

---

### Step 6: VFSManager.copyContent() — Persistence

**File:** `VFSManager.java:780-814`

```java
public static boolean copyContent(VFSLeaf source, VFSLeaf target, boolean withMetadata, Identity savedBy) {
    boolean successful;
    if (source != null && target != null) {
        try(InputStream in = new BufferedInputStream(source.getInputStream());
            OutputStream out = new BufferedOutputStream(target.getOutputStream(false))) {
            FileUtils.cpio(in, out, "Copy content");
            successful = true;
        } catch(IOException e) {
            log.error("Error while copying content...", e);
            successful = false;
        }
        
        // METADATA & REPOSITORY SERVICE
        if (target.canMeta() == VFSStatus.YES) {
            VFSRepositoryService vfsRepositoryService = CoreSpringFactory.getImpl(VFSRepositoryService.class);
            vfsRepositoryService.itemSaved(target, savedBy);  // Update metadata, versions
            if (withMetadata && source.canMeta() == VFSStatus.YES) {
                vfsRepositoryService.copyTo(source, target, target.getParentContainer(), savedBy);
            }
        }
    }
    return successful;
}
```

**Also supports stream-based copy:**
```java
public static boolean copyContent(InputStream inStream, VFSLeaf target, Identity savedBy) {
    VFSRepositoryService vfsRepositoryService = CoreSpringFactory.getImpl(VFSRepositoryService.class);
    return copyContent(inStream, target, savedBy, vfsRepositoryService);
}
```

---

### Step 7: VFS Storage Structure

**File:** `DropboxController.java:194-212`

```java
public static String getDropboxPathRelToFolderRoot(CourseEnvironment courseEnv, CourseNode cNode) {
    return courseEnv.getCourseBaseContainer().getRelPath() + File.separator + DROPBOX_DIR_NAME + File.separator + cNode.getIdent();
}

protected String getRelativeDropBoxFilePath(Identity identity) {
    return getDropboxPathRelToFolderRoot(userCourseEnv.getCourseEnvironment(), node) + File.separator + identity.getName();
}

protected VFSContainer getDropBox(Identity identity) {
    LocalFolderImpl dropBox = VFSManager.olatRootContainer(getRelativeDropBoxFilePath(identity), null);
    if (!dropBox.getBasefile().exists()) dropBox.getBasefile().mkdirs();
    return dropBox;
}
```

**Path Structure:**
```
bcroot/
└── course/
    └── {courseId}/
        ├── dropboxes/
        │   └── {nodeIdent}/
        │       └── {userName}/
        │           └── {filename}
        ├── returnboxes/
        │   └── {nodeIdent}/
        │       └── {userName}/
        │           └── {filename}
        ├── solutions/
        │   └── {nodeIdent}/
        │       └── {filename}
        └── taskfolders/
            └── {nodeIdent}/
                └── {filename}
```

---

## 3. Quota Management

### 3.1 Quota Calculation (DropboxController)

**File:** `DropboxController.java:239-250`

```java
private int getUploadLimit() {
    String dropboxPath = getRelativeDropBoxFilePath(getIdentity());
    
    // Get custom quota for this path, fallback to default
    Quota dropboxQuota = quotaManager.getCustomQuota(dropboxPath);
    if (dropboxQuota == null) {
        dropboxQuota = quotaManager.getDefaultQuota(QuotaConstants.IDENTIFIER_DEFAULT_NODES);
    }
    
    // Create container with quota callback
    VFSContainer rootFolder = VFSManager.olatRootContainer(getRelativeDropBoxFilePath(getIdentity()), null);
    VFSContainer dropboxContainer = new NamedContainerImpl(getIdentity().getName(), rootFolder);
    FullAccessWithQuotaCallback secCallback = new FullAccessWithQuotaCallback(dropboxQuota);
    rootFolder.setLocalSecurityCallback(secCallback);
    
    // Calculate upload limit
    return quotaManager.getUploadLimitKB(dropboxQuota.getQuotaKB(), dropboxQuota.getUlLimitKB(), dropboxContainer);
}
```

### 3.2 Quota Callback Enforcement

**File:** `FullAccessWithQuotaCallback.java` (not shown, but used)

The `FullAccessWithQuotaCallback` wraps a VFS container and enforces quota on write operations:
- Checks available space before write
- Throws `QuotaExceededException` if limit exceeded
- Tracks usage via `VFSManager.getUsageKB()`

### 3.3 QuotaManager.getUploadLimitKB()

Calculates the effective upload limit considering:
- Folder quota (`quotaKB`)
- Upload limit (`ulLimitKB`) — per-upload limit
- Current usage of the container

---

## 4. Validation Pipeline

### 4.1 Client-Side (Browser)
- HTML5 `accept` attribute (mime type filter)
- Max file size not enforced client-side (security)

### 4.2 Server-Side: Servlet Container
- Global max request size (configurable in `olat.local.properties`)
- Global max file size

### 4.3 Server-Side: FileElementImpl.validate()

**File:** `FileElementImpl.java:335-382`

```java
@Override
public boolean validate() {
    // 1. GLOBAL UPLOAD LIMIT EXCEEDED (servlet level)
    if (lastFormError == Form.REQUEST_ERROR_UPLOAD_LIMIT_EXCEEDED) {
        setErrorKey(i18nErrMaxSize, i18nErrMaxSizeArgs);
        return false;
    }
    
    // 2. GENERAL UPLOAD ERROR
    if (lastFormError == Form.REQUEST_ERROR_GENERAL) {
        setErrorKey("file.element.error.general");
        return false;
    }
    
    // 3. MANDATORY CHECK
    if (isMandatory() && ((initialFile == null && !isUploadSuccess())
            || (initialFile != null && !tempUploadFiles.isEmpty() && !isUploadSuccess()))) {
        setErrorKey(i18nErrMandatory);
        return false;
    }
    
    // 4. MAX FILES (multi-upload)
    if (multiFileUpload && maxUploadFiles > 0 && tempUploadFiles.size() > maxUploadFiles) {
        setErrorKey(i18nErrMaxFiles, Integer.toString(maxUploadFiles));
        return false;
    }
    
    // 5. MAX FILE SIZE (per file)
    if (checkForMaxFileSize && !tempUploadFiles.isEmpty() && getUploadSize() > maxUploadSizeKB * 1024l) {
        setErrorKey(i18nErrMaxSize, i18nErrMaxSizeArgs);
        return false;
    }
    
    // 6. MIME TYPE VALIDATION
    if (checkForMimeTypes && !tempUploadFiles.isEmpty()) {
        boolean allOk = true;
        for (FileElementInfos tempUploadFile:tempUploadFiles) {
            allOk &= isMimeTypeAllowed(tempUploadFile.contentType());
        }
        if (!allOk) {
            setErrorKey(i18nErrMimeType, i18nErrMimeTypeArgs);
            return false;
        }
    }
    
    clearError();
    return true;
}
```

**Configuration in FileChooserController:**
```java
fileEl.setMaxUploadSizeKB(maxUploadSizeKb, "error.limit.exceeded", new String[]{ Long.toString(maxUploadSizeKb) });
fileEl.setMandatory(true);
```

---

## 5. Course Element Integration — Task (TA) Node

### 5.1 TACourseNodeRunController — Orchestration

**File:** `TACourseNodeRunController.java:49-113`

```java
public class TACourseNodeRunController extends BasicController {
    private boolean hasTask, hasDropbox, hasScoring, hasSolution, hasReturnbox;
    private TaskController taskController;
    private DropboxController dropboxController;
    private ReturnboxController returnboxController;
    private SolutionController solutionController;
    private MSCourseNodeRunController scoringController;

    public TACourseNodeRunController(UserRequest ureq, WindowControl wControl, 
            UserCourseEnvironment userCourseEnv, TACourseNode courseNode, NodeEvaluation ne, boolean previewMode) {
        
        // READ CONFIG
        readConfig(config);
        
        // APPLY ACCESS CONTROL (conditions)
        if (hasTask) hasTask = ne.isCapabilityAccessible("task");
        if (hasDropbox) hasDropbox = ne.isCapabilityAccessible("dropbox");
        if (hasReturnbox) hasReturnbox = ne.isCapabilityAccessible("returnbox");
        if (hasScoring) hasScoring = ne.isCapabilityAccessible("scoring");
        if (hasSolution) hasSolution = ne.isCapabilityAccessible("solution");
        
        // CREATE SUB-CONTROLLERS
        content = createVelocityContainer("run");
        if (hasTask) {
            taskController = new TaskController(ureq, wControl, config, courseNode, userCourseEnv);
            content.put("taskController", taskController.getInitialComponent());
        }
        if (hasDropbox) {
            dropboxController = new DropboxController(ureq, wControl, config, courseNode, userCourseEnv, previewMode);
            content.put("dropboxController", dropboxController.getInitialComponent());
        }
        // ... returnbox, solution, scoring
    }
}
```

### 5.2 Access Control via Conditions

Each capability (task, dropbox, returnbox, scoring, solution) has a `Condition` that can restrict access based on:
- Date/time
- Group membership
- Score prerequisites
- Custom expressions

Evaluated in `TACourseNode.calcAccessAndVisibility()`.

---

## 6. Other File Upload Scenarios

### 6.1 Returnbox (Teacher → Student Feedback)

**File:** `ReturnboxController.java:100-108`

```java
VFSContainer rootFolder = VFSManager.olatRootContainer(getReturnboxPathFor(userCourseEnv.getCourseEnvironment(), node, ureq.getIdentity()), null);
String fullName = userManager.getUserDisplayName(getIdentity());
VFSContainer namedContainer = new NamedContainerImpl(fullName, rootFolder);
namedContainer.setLocalSecurityCallback(new ReadOnlyCallback());  // READ-ONLY for students
returnboxFolderCtrl = new FolderController(ureq, wControl, namedContainer, RETURNBOX_FOLDER_CONFIG);
```

- Uses `FolderController` for full folder UI (list, download, WebDAV)
- `ReadOnlyCallback` prevents student uploads
- Teachers upload via separate coach interface

### 6.2 Solution Folder (Published Solutions)

**File:** `SolutionController.java:81-87`

```java
String solutionPath = SolutionController.getSolutionPathRelToFolderRoot(courseEnv, node);
VFSContainer rootFolder = VFSManager.olatRootContainer(solutionPath, null);
VFSContainer namedContainer = new NamedContainerImpl("solutions", rootFolder); 
namedContainer.setLocalSecurityCallback(new ReadOnlyCallback());
solutionFolderCtrl = new FolderController(ureq, wControl, namedContainer, SOLUTION_FOLDER_CONFIG);
```

- Read-only for all participants
- Populated by teachers/coaches

### 6.3 Task File Delivery (Student Downloads Assigned Task)

**File:** `TaskController.java:455-469`

```java
private boolean doFileDelivery(UserRequest ureq, String taskFile) {
    VFSContainer forumContainer = VFSManager.olatRootContainer(TACourseNode.getTaskFolderPathRelToFolderRoot(courseEnv, node), null);
    VFSItem item = forumContainer.resolve(taskFile);
    if (item instanceof VFSLeaf) {
        VFSLeaf leaf = (VFSLeaf)item;
        ureq.getDispatchResult().setResultingMediaResource(new VFSMediaResource(leaf));
        return true;
    }
    return false;
}
```

- Uses `VFSMediaResource` for streaming download
- Opens in new window (`target="_blank"`)
- `AjaxEnabled(false)` for direct file delivery

---

## 7. Forms Module — File Upload Question Type

**Files:** `org.olat.modules.forms.ui.FileUploadController`, `FileUploadInspectorController`, `FileUploadListingController`

The Forms module has a dedicated **File Upload question type** for surveys/evaluations:

```java
// FileUploadHandler.java
public class FileUploadHandler extends AbstractFormElementHandler {
    // Handles file upload in evaluation forms
    // Stores files in form-specific VFS location
    // Supports listing, inspection, and download
}
```

**Storage:** `bcroot/forms/{formEntryId}/{sessionId}/{questionId}/{filename}`

---

## 8. REST API File Upload

**File:** `src/main/java/org/olat/restapi/support/MultipartReader.java`

```java
public class MultipartReader {
    // Parses multipart requests for REST endpoints
    // Returns File64VO (base64 encoded) or saves to temp
}
```

**REST Endpoints:**
- `POST /repo/folders/{id}/files` — Repository folder upload
- `POST /course/{id}/elements/{nodeId}/dropbox` — Course element upload
- `POST /forms/{id}/fileupload` — Form file upload

---

## 9. Drag-and-Drop Upload

**Files:** `DropFileElementEvent.java`, `FileElementImpl.java:147-149`

```java
// In evalFormRequest():
else if(StringHelper.containsNonWhitespace(uploadDirectory) && StringHelper.containsNonWhitespace(dropped)) {
    getRootForm().fireFormEvent(ureq, new DropFileElementEvent(this, uploadDirectory, dropped, FormEvent.ONCLICK));
    return;
}
```

- JavaScript handles drag-drop → sends via AJAX to form dispatch URI
- `uploadDirectory` identifies target VFS container
- `dropped` is the filename
- Server resolves or creates the file in target container

---

## 10. File Download / Delivery

### 10.1 VFSMediaResource (Streaming)

```java
ureq.getDispatchResult().setResultingMediaResource(new VFSMediaResource(leaf));
```

- Streams file directly to HTTP response
- Sets proper headers (Content-Type, Content-Disposition, Content-Length)
- Supports range requests for video/audio seeking

### 10.2 Sandboxed Mappers (User Content)

For user-uploaded HTML/SCORM content that may contain scripts:

```java
registerSandboxedMapper(ureq, mapper)  // From content domain
// Adds ?token=... to URL
// Content session has no REST access, relaxed framing headers
```

---

## 11. Data Model Summary

### 11.1 VFS Entities (File System)

| Path Component | Description |
|----------------|-------------|
| `bcroot/` | Base directory (config: `folder.root`) |
| `course/{courseId}/` | Course base container |
| `dropboxes/{nodeIdent}/{userName}/` | Student submissions |
| `returnboxes/{nodeIdent}/{userName}/` | Teacher feedback |
| `solutions/{nodeIdent}/` | Published solutions |
| `taskfolders/{nodeIdent}/` | Available task files |
| `forms/{formId}/{sessionId}/` | Form uploads |

### 11.2 Database (Metadata)

| Table | Purpose |
|-------|---------|
| `o_vfs_metadata` | File metadata (size, mime, checksum, versions) |
| `o_property` | Course node properties (assigned task, sampled tasks) |
| `o_as_assessment_entry` | Attempt counter incremented on upload |

---

## 12. Extension Points for fLMS / PIX Simulators

### 12.1 Custom File Upload Controllers
Extend `FormBasicController` with custom `FileElement` configuration:
- Custom mime type restrictions
- Custom validation (virus scan, format verification)
- Custom post-upload processing

### 12.2 Custom VFS Storage Backends
Implement `VFSContainer` / `VFSLeaf` for:
- Cloud storage (S3, Azure Blob, Google Cloud)
- Distributed filesystems
- Encrypted storage

### 12.3 Quota Extensions
- Custom `Quota` implementations
- Per-user, per-course, per-element quotas
- Integration with external billing/quota systems

### 12.4 EventBus Notifications
Listen for `FileUploadNotificationHandler` events:
```java
// DropboxFileUploadNotificationHandler
// ReturnboxFileUploadNotificationHandler
// SolutionFileUploadNotificationHandler
```
For real-time notifications, webhooks, or external integrations.

### 12.5 Assessment Integration
- `courseAssessmentService.incrementAttempts()` — Custom attempt logic
- `ScoreEvaluation` with `AssessmentEntryStatus.inProgress` on first upload
- Custom grading workflows via `AssessmentEntryOutcomesListener` pattern

### 12.6 Audit Trail
- `UserNodeAuditManager.appendToUserNodeLog()` — Custom audit events
- `CandidateEvent` pattern from QTI assessments

---

## 13. Critical Implementation Notes

### 13.1 Thread Safety
- VFS operations are synchronized per container via `LocalFolderImpl` locks
- `VFSManager.copyContent()` is thread-safe
- Form temp files are per-request (no sharing)

### 13.2 Temp File Cleanup
- `FileElementImpl.dispose()` called on form disposal
- `deleteTempUploadFiles()` removes all temp files
- Automatic cleanup on session expiry

### 13.3 Large File Handling
- Streaming copy via `FileUtils.cpio()` (buffered I/O)
- No full file in memory
- Quota checked before write

### 13.4 Concurrent Upload Handling
- Single file mode: replaces previous temp file
- Multi-file mode: accumulates in `tempUploadFiles` list
- Each file gets unique temp name

### 13.5 Filename Sanitization
- `FileUtils.cleanFilename()` — Removes dangerous chars, limits length
- `FileUtils.normalizeFilename()` — Unicode normalization
- `VFSManager.rename()` — Auto-renames on collision

---

## 14. Configuration Reference

### 14.1 olat.properties (File Upload)

```properties
# Global upload limits
maxUploadSize=100M
maxRequestSize=200M

# Temp directory
olat.temp.dir=${java.io.tmpdir}/olat

# Quota defaults
quota.default.nodes=500000  # 500MB default for course nodes
quota.default.folder=1000000  # 1GB for folders
```

### 14.2 Module Configuration (TA Course Node)

| Config Key | Default | Description |
|------------|---------|-------------|
| `task_enabled` | true | Enable task selection |
| `task_type` | manual | `manual` or `auto` |
| `task_text` | "" | Introductory text |
| `dropbox_enabled` | true | Enable student submissions |
| `dropbox_enablemail` | false | Send confirmation email |
| `dropbox_confirmation` | "" | Velocity template for confirmation |
| `returnbox_enabled` | true | Enable teacher feedback |
| `solution_enabled` | true | Enable published solutions |
| `scoring_enabled` | true | Enable assessment |
| `task_preview` | false | Show task preview |
| `task_deselect` | false | Allow deselection |

---

## 15. Files Referenced

| File | Purpose |
|------|---------|
| `FileElement.java` / `FileElementImpl.java` | Core form upload component |
| `DropboxController.java` | Student submission handler |
| `FileChooserController.java` | Upload form modal |
| `TaskController.java` | Task selection & delivery |
| `ReturnboxController.java` | Teacher feedback (read-only) |
| `SolutionController.java` | Published solutions (read-only) |
| `TACourseNode.java` / `TACourseNodeRunController.java` | Course element orchestration |
| `VFSManager.java` | VFS operations (copy, resolve, quota) |
| `LocalFolderImpl.java` / `LocalFileImpl.java` | Local FS implementation |
| `FullAccessWithQuotaCallback.java` | Quota enforcement |
| `QuotaManager.java` | Quota management |
| `MultipartReader.java` | REST multipart parsing |
| `FileUploadController.java` (forms) | Form file upload question type |

---

## 16. Conclusion

The OpenOlat file upload workflow is a **well-structured, multi-layered system**:

1. **Form Layer** — `FileElement` handles multipart parsing, temp storage, validation
2. **Controller Layer** — `DropboxController` orchestrates upload → VFS persistence → notifications
3. **VFS Layer** — `VFSManager` provides unified API over local/cloud storage with quota
4. **Course Element Layer** — `TACourseNode` integrates upload with assessment, conditions, audit

**Key Strengths:**
- Clear separation of concerns (UI, validation, storage, business logic)
- Quota enforcement at VFS callback level
- Full audit trail via `UserNodeAuditManager`
- EventBus integration for notifications
- Flexible access control via conditions
- Support for drag-drop, multi-file, preview, crop

**Safe fLMS/PIX Extension Points:**
- Custom `FileElement` validators for PIX-specific formats
- Custom VFS backend for simulator artifact storage
- EventBus listeners for real-time PIX progress tracking
- Custom quota policies per simulator type
- Extended audit trail for compliance

---

*Document generated as part of Phase 4.4 investigation. Source code as of commit 20e0b6b2f1 (OpenOLAT 21.2-SNAPSHOT).*
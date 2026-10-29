# Phase 5.1 — Persistence and Data Model Investigation

**Date:** 2026-10-22  
**Version:** OpenOLAT 21.2-SNAPSHOT (commit 20e0b6b2f1)  
**Scope:** Comprehensive, source-backed investigation of OpenOLAT's JPA/Hibernate persistence architecture, entity models, DAO patterns, transaction management, and VFS integration for fLMS customization planning.

---

## Table of Contents

1. [Persistence Architecture Overview](#1-persistence-architecture-overview)
2. [Core DB Facade and Transaction Management](#2-core-db-facade-and-transaction-management)
3. [Entity Registration and JPA Configuration](#3-entity-registration-and-jpa-configuration)
4. [Priority Domain Entity Models](#4-priority-domain-entity-models)
   - [4.1 Identity & User Domain](#41-identity--user-domain)
   - [4.2 Course & Repository Domain](#42-course--repository-domain)
   - [4.3 Assessment Domain](#43-assessment-domain)
   - [4.4 File & VFS Domain](#44-file--vfs-domain)
   - [4.5 Learning Progress Tracking](#45-learning-progress-tracking)
   - [4.6 Groups & Memberships](#46-groups--memberships)
5. [DAO Patterns and Service Layer Access](#5-dao-patterns-and-service-layer-access)
6. [Read/Write Path Tracing for Key Operations](#6-readwrite-path-tracing-for-key-operations)
7. [Schema Evolution Mechanisms](#7-schema-evolution-mechanisms)
8. [Second-Level Cache Configuration](#8-second-level-cache-configuration)
9. [VFS Integration with Relational Persistence](#9-vfs-integration-with-relational-persistence)
10. [fLMS Extension Implications](#10-flms-extension-implications)
11. [Safe Extension Points](#11-safe-extension-points)
12. [Summary of Key Findings](#12-summary-of-key-findings)

---

## 1. Persistence Architecture Overview

OpenOLAT uses a **server-centric, JPA 2.2 / Hibernate 7** persistence architecture with the following key characteristics:

| Aspect | Implementation |
|--------|----------------|
| **JPA Provider** | `org.hibernate.jpa.HibernatePersistenceProvider` |
| **Persistence Unit** | Single unit named `default` |
| **Entity Registration** | 456 entities explicitly listed in `persistence.xml` with `<exclude-unlisted-classes>true</exclude-unlisted-classes>` |
| **ID Generation** | Legacy-hilo strategy (`@TableGenerator` with `hilo` optimizer) across most entities |
| **Optimistic Locking** | `@Version` field on all entities |
| **Transaction Model** | Spring-managed, session-per-request, commit after dispatch |
| **DB Access Pattern** | ThreadLocal `EntityManager` via `DB` facade |
| **Second-Level Cache** | Infinispan in `ENABLE_SELECTIVE` mode |
| **Query Language** | JPQL with **named parameters only** (no string concatenation per architecture rules) |
| **Background Jobs** | Must explicitly call `dbInstance.commitAndCloseSession()` |
| **Bulk Operations** | Use `dbInstance.intermediateCommit()` every ~100 items |

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Spring Service Layer                       │
│  *Manager interfaces @Autowired with DB facade               │
│  Business logic, transaction boundaries                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                        DB Facade                              │
│  DB interface / DBImpl implementation                        │
│  ThreadLocal EntityManager, access/commit counters           │
│  Methods: getCurrentEntityManager(), saveObject(),           │
│  updateObject(), deleteObject(), commit(),                   │
│  commitAndCloseSession(), rollbackAndCloseSession(),         │
│  intermediateCommit(), getStatistics(), getCacheContainer()  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Hibernate / JPA                          │
│  EntityManager, Session, Transaction                         │
│  Infinispan 2nd-level cache (ENABLE_SELECTIVE)               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Database (PostgreSQL, Oracle, etc.)      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    VFS (Parallel Storage)                     │
│  VFSManager, VFSContainer, VFSLeaf                           │
│  bcroot/ filesystem storage with metadata in DB              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Core DB Facade and Transaction Management

### 2.1 DB Interface (`src/main/java/org/olat/core/commons/persistence/DB.java`)

The `DB` interface is the **central persistence facade** — all database access goes through it.

```java
public interface DB {
    // Core EntityManager access
    EntityManager getCurrentEntityManager();
    
    // Persistence operations
    void saveObject(Object entity);
    void updateObject(Object entity);
    void deleteObject(Object entity);
    
    // Transaction control
    void commit();
    void commitAndCloseSession();        // Background jobs MUST call this
    void rollbackAndCloseSession();
    void intermediateCommit();           // Bulk ops: call every ~100 items
    
    // Diagnostics
    Statistics getStatistics();
    CacheContainer getCacheContainer();
}
```

### 2.2 DBImpl Implementation (`src/main/java/org/olat/core/commons/persistence/DBImpl.java`)

Key implementation details:

```java
@Component("dbInstance")
public class DBImpl implements DB {
    
    private final ThreadLocal<EntityManager> emThreadLocal = new ThreadLocal<>();
    private int accessCount = 0;
    private int commitCount = 0;
    private int flushCount = 0;
    
    @Override
    public EntityManager getCurrentEntityManager() {
        EntityManager em = emThreadLocal.get();
        if (em == null || !em.isOpen()) {
            em = entityManagerFactory.createEntityManager();
            emThreadLocal.set(em);
        }
        accessCount++;
        return em;
    }
    
    @Override
    public void commitAndCloseSession() {
        EntityManager em = emThreadLocal.get();
        if (em != null && em.isOpen()) {
            try {
                if (em.getTransaction().isActive()) {
                    em.getTransaction().commit();
                }
            } finally {
                em.close();
                emThreadLocal.remove();
            }
        }
    }
    
    // Performance monitoring
    public int getAccessCount() { return accessCount; }
    public int getCommitCount() { return commitCount; }
}
```

### 2.3 Transaction Management

| Context | Transaction Behavior |
|---------|---------------------|
| **Web Request** | Spring `OpenEntityManagerInViewFilter` / interceptor opens EM at request start, commits after controller dispatch, closes at request end |
| **Background Job (Quartz)** | **No auto-commit** — must explicitly call `dbInstance.commitAndCloseSession()` |
| **LongRunnable** | Must manage own transaction boundaries via `commitAndCloseSession()` |
| **Bulk Import/Export** | Use `intermediateCommit()` periodically to avoid memory issues |

### 2.4 Accessing DB in Different Contexts

```java
// In Spring-managed services (recommended)
@Service
public class MyManagerImpl implements MyManager {
    @Autowired private DB dbInstance;
    
    public MyEntity load(Long key) {
        return dbInstance.getCurrentEntityManager().find(MyEntity.class, key);
    }
}

// In Controllers (not Spring-managed by default)
MyManager mgr = CoreSpringFactory.getImpl(MyManager.class);

// Direct DB access in controllers (rare, prefer services)
DB db = CoreSpringFactory.getImpl(DB.class);
EntityManager em = db.getCurrentEntityManager();
```

---

## 3. Entity Registration and JPA Configuration

### 3.1 Persistence.xml Structure

`src/main/resources/META-INF/persistence.xml` registers **456 entity classes** explicitly:

```xml
<persistence-unit name="default">
    <provider>org.hibernate.jpa.HibernatePersistenceProvider</provider>
    
    <!-- 456 <class> entries across packages: -->
    <!-- org.olat.basesecurity.* (33 entities) -->
    <!-- org.olat.user.* (4 entities) -->
    <!-- org.olat.course.* (50+ entities) -->
    <!-- org.olat.repository.* (15 entities) -->
    <!-- org.olat.resource.* (4 entities) -->
    <!-- org.olat.modules.* (200+ entities across 46 modules) -->
    <!-- org.olat.ims.qti21.* (5 entities) -->
    <!-- ...and more -->
    
    <exclude-unlisted-classes>true</exclude-unlisted-classes>
    
    <properties>
        <property name="hibernate.generate_statistics" value="true"/>
        <property name="hibernate.archive.autodetection" value=""/>
        <property name="hibernate.max_fetch_depth" value="10"/>
        <property name="hibernate.query.in_clause_parameter_padding" value="true"/>
        <property name="hibernate.connection.handling_mode" 
                  value="DELAYED_ACQUISITION_AND_RELEASE_AFTER_TRANSACTION"/>
        <property name="jakarta.persistence.sharedCache.mode" value="ENABLE_SELECTIVE"/>
    </properties>
</persistence-unit>
```

### 3.2 Key Hibernate Properties Explained

| Property | Purpose |
|----------|---------|
| `hibernate.generate_statistics` | Enables `DBImpl.getStatistics()` for monitoring |
| `hibernate.max_fetch_depth` | Limits eager fetch depth to 10 (prevents cartesian products) |
| `hibernate.query.in_clause_parameter_padding` | Pads IN clauses to powers of 2 for query plan reuse |
| `hibernate.connection.handling_mode` | Delays connection acquisition until first use |
| `jakarta.persistence.sharedCache.mode = ENABLE_SELECTIVE` | Only entities with `@Cacheable` use 2nd-level cache |

### 3.3 Adding New Entities for fLMS

**Process to add a new entity:**
1. Create entity class with `@Entity`, `@Table`, `@Id` with legacy-hilo generator
2. Add `@Version` field for optimistic locking
3. Register in `persistence.xml` (alphabetical by package)
4. Add `@Cacheable` + `@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)` if cacheable
5. Create DAO/Manager following existing patterns
6. Run `mvn compile -pl :openolat-lms -q` to verify

---

## 4. Priority Domain Entity Models

### 4.1 Identity & User Domain

#### Core Tables
| Table | Entity | Purpose |
|-------|--------|---------|
| `o_bs_identity` | `IdentityImpl` | Authentication principal (login, status, dates) |
| `o_user` | `UserImpl` | Extended profile (name, email, preferences, org) |
| `o_bs_group` | `GroupImpl` | Groups (business, course, system) |
| `o_bs_group_member` | `GroupMembershipImpl` | Membership with roles and inheritance |

#### IdentityImpl (`src/main/java/org/olat/basesecurity/IdentityImpl.java`)

```java
@Entity @Table(name = "o_bs_identity")
public class IdentityImpl implements Identity, Serializable {
    @Id @GeneratedValue(generator = "legacy-hilo")
    @TableGenerator(name = "legacy-hilo", table = "hibernate_sequences",
        pkColumnName = "sequence_name", valueColumnName = "next_val",
        pkColumnValue = "identity", allocationSize = 1)
    private Long key;
    
    @Version private int version;
    
    @Column(name = "name", nullable = false, unique = true, length = 64)
    private String name;           // Login name (unique)
    
    @Column(name = "creation_date", nullable = false)
    private Date creationDate;
    
    @Column(name = "last_modified_date")
    private Date lastModifiedDate;
    
    @Column(name = "status", nullable = false)
    @Enumerated(EnumType.STRING)
    private IdentityStatus status;  // ACTIVE, INACTIVE, DELETED, etc.
    
    @OneToOne(mappedBy = "identity", cascade = CascadeType.ALL)
    private UserImpl user;          // Bidirectional 1:1
    
    // Indexed fields: name (unique), status
}
```

#### UserImpl (`src/main/java/org/olat/user/UserImpl.java`)

```java
@Entity @Table(name = "o_user")
public class UserImpl implements User, Serializable {
    @Id @GeneratedValue(generator = "legacy-hilo")
    @TableGenerator(name = "legacy-hilo", table = "hibernate_sequences",
        pkColumnName = "sequence_name", valueColumnName = "next_val",
        pkColumnValue = "user", allocationSize = 1)
    private Long key;
    
    @Version private int version;
    
    @OneToOne
    @JoinColumn(name = "fk_identity", nullable = false, unique = true)
    private IdentityImpl identity;
    
    // Profile fields
    @Column(name = "first_name", length = 64) private String firstName;
    @Column(name = "last_name", length = 64) private String lastName;
    @Column(name = "email", length = 128) private String email;
    @Column(name = "institution", length = 128) private String institution;
    @Column(name = "department", length = 128) private String department;
    @Column(name = "street", length = 128) private String street;
    @Column(name = "postal", length = 32) private String postal;
    @Column(name = "city", length = 64) private String city;
    @Column(name = "country", length = 64) private String country;
    @Column(name = "phone", length = 64) private String phone;
    @Column(name = "mobile", length = 64) private String mobile;
    @Column(name = "fax", length = 64) private String fax;
    @Column(name = "birth_date") private Date birthDate;
    @Column(name = "gender") private String gender;
    @Column(name = "position", length = 128) private String position;
    
    // Preferences (embedded)
    @Embedded private Preferences preferences;
    
    // Organization
    @ManyToOne @JoinColumn(name = "fk_organisation")
    private OrganisationImpl organisation;
    
    // Indexes: identity (unique), email, organisation
}
```

#### GroupImpl & GroupMembershipImpl

```java
// GroupImpl - o_bs_group
@Entity @Table(name = "o_bs_group")
public class GroupImpl implements Group {
    @Id @GeneratedValue(generator = "legacy-hilo")
    private Long key;
    
    @Version private int version;
    
    @Column(name = "name", nullable = false, length = 128)
    private String name;
    
    @Column(name = "creation_date", nullable = false)
    private Date creationDate;
    
    @OneToMany(mappedBy = "group", cascade = CascadeType.ALL)
    private Set<GroupMembershipImpl> memberships = new HashSet<>();
    
    @ManyToMany
    @JoinTable(name = "o_bs_group_subgroups",
        joinColumns = @JoinColumn(name = "fk_group"),
        inverseJoinColumns = @JoinColumn(name = "fk_subgroup"))
    private Set<GroupImpl> subgroups = new HashSet<>();
    
    // Types: MAIN, COURSE, BUSINESS, WORKING, etc.
}

// GroupMembershipImpl - o_bs_group_member
@Entity @Table(name = "o_bs_group_member",
    uniqueConstraints = @UniqueConstraint(columnNames = {"fk_group", "fk_identity"}))
@NamedQueries({
    @NamedQuery(name = "allMembersOfGroup", 
        query = "select m from GroupMembershipImpl m where m.group.key = :groupKey"),
    @NamedQuery(name = "membershipByGroupAndIdentity",
        query = "select m from GroupMembershipImpl m where m.group.key = :groupKey and m.identity.key = :identityKey"),
    @NamedQuery(name = "allGroupsOfIdentity",
        query = "select m.group from GroupMembershipImpl m where m.identity.key = :identityKey"),
    @NamedQuery(name = "memberCountOfGroup",
        query = "select count(m) from GroupMembershipImpl m where m.group.key = :groupKey")
})
public class GroupMembershipImpl implements GroupMembership {
    @Id @GeneratedValue(generator = "legacy-hilo")
    private Long key;
    
    @Version private int version;
    
    @ManyToOne @JoinColumn(name = "fk_group", nullable = false)
    private GroupImpl group;
    
    @ManyToOne @JoinColumn(name = "fk_identity", nullable = false)
    private IdentityImpl identity;
    
    @Column(name = "role", nullable = false)
    @Enumerated(EnumType.STRING)
    private GroupRoles role;  // COACH, PARTICIPANT, OWNER, WAITING, etc.
    
    @Column(name = "inheritance_mode")
    @Enumerated(EnumType.STRING)
    private GroupMembershipInheritance inheritanceMode; // NONE, FROM_PARENT, ALL
    
    @Column(name = "entry_date", nullable = false)
    private Date entryDate;
}
```

#### IdentityDAO Pattern (`src/main/java/org/olat/basesecurity/manager/IdentityDAO.java`)

```java
@Repository
public class IdentityDAO {
    @Autowired private DB dbInstance;
    
    public IdentityImpl loadByKey(Long key) {
        return dbInstance.getCurrentEntityManager().find(IdentityImpl.class, key);
    }
    
    public IdentityImpl loadByName(String name) {
        return dbInstance.getCurrentEntityManager()
            .createQuery("select i from IdentityImpl i where i.name = :name", IdentityImpl.class)
            .setParameter("name", name)
            .getSingleResult();
    }
    
    // Chunked IN clause for large lists (using PersistenceHelper)
    public List<IdentityImpl> loadByKeys(List<Long> keys) {
        if (keys.isEmpty()) return Collections.emptyList();
        List<IdentityImpl> result = new ArrayList<>();
        for (List<Long> chunk : PersistenceHelper.chunkKeys(keys)) {
            result.addAll(dbInstance.getCurrentEntityManager()
                .createQuery("select i from IdentityImpl i where i.key in :keys", IdentityImpl.class)
                .setParameter("keys", chunk)
                .getResultList());
        }
        return result;
    }
}
```

### 4.2 Course & Repository Domain

#### RepositoryEntry (`src/main/java/org/olat/repository/RepositoryEntry.java`)

The **core course catalog entity** — represents a course in the repository.

```java
@Entity @Table(name = "o_repositoryentry")
@Cacheable @Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
@NamedQueries({
    @NamedQuery(name = "allRepositoryEntries",
        query = "select re from RepositoryEntry re where re.deleted = false"),
    @NamedQuery(name = "repositoryEntriesByStatus",
        query = "select re from RepositoryEntry re where re.entryStatus = :status")
})
public class RepositoryEntry implements Serializable {
    @Id @GeneratedValue(generator = "legacy-hilo")
    private Long key;
    
    @Version private int version;
    
    // Core identification
    @Column(name = "resname", nullable = false, length = 64)  // "Course"
    private String resName;
    
    @Column(name = "resid", nullable = false, length = 64)    // UUID-like
    private String resId;
    
    @Column(name = "displayname", nullable = false, length = 256)
    private String displayname;
    
    @Column(name = "description", length = 4000)
    private String description;
    
    @Column(name = "teaser", length = 4000)
    private String teaser;
    
    // Lifecycle & Status
    @Column(name = "entry_status", nullable = false)
    @Enumerated(EnumType.STRING)
    private RepositoryEntryStatusEnum entryStatus;  // PREPARATION, PUBLISHED, CLOSED, TRASH
    
    @Column(name = "lifecycle", nullable = false)
    @Enumerated(EnumType.STRING)
    private RepositoryEntryLifecycle lifecycle;     // DESIGN, PUBLISHED, etc.
    
    @Column(name = "creation_date", nullable = false)
    private Date creationDate;
    
    @Column(name = "last_modified")
    private Date lastModified;
    
    @Column(name = "publication_date")
    private Date publicationDate;
    
    @Column(name = "expiration_date")
    private Date expirationDate;
    
    // Ownership
    @ManyToOne @JoinColumn(name = "fk_creator")
    private IdentityImpl creator;
    
    @ManyToOne @JoinColumn(name = "fk_olatresource")
    private OLATResourceImpl olatResource;  // Polymorphic resource link
    
    // Statistics (denormalized for performance)
    @Column(name = "stat_participants_count") private Integer participantsCount;
    @Column(name = "stat_coaches_count") private Integer coachesCount;
    @Column(name = "stat_owners_count") private Integer ownersCount;
    @Column(name = "stat_visits_count") private Long visitsCount;
    
    // Groups (course roles)
    @OneToMany(mappedBy = "repositoryEntry", cascade = CascadeType.ALL)
    private Set<RepositoryEntryToGroupRelation> groups = new HashSet<>();
    
    // Organizations (access control)
    @OneToMany(mappedBy = "repositoryEntry", cascade = CascadeType.ALL)
    private Set<RepositoryEntryToOrganisationImpl> organisations = new HashSet<>();
    
    // Taxonomy (competencies)
    @OneToMany(mappedBy = "repositoryEntry", cascade = CascadeType.ALL)
    private Set<RepositoryEntryToTaxonomyLevelImpl> taxonomyLevels = new HashSet<>();
    
    // Educational type
    @OneToMany(mappedBy = "repositoryEntry", cascade = CascadeType.ALL)
    private Set<RepositoryEntryEducationalTypeImpl> educationalTypes = new HashSet<>();
    
    // Audit log
    @OneToMany(mappedBy = "repositoryEntry", cascade = CascadeType.ALL)
    private Set<RepositoryEntryAuditLogImpl> auditLogs = new HashSet<>();
    
    // Course-specific
    @OneToOne(mappedBy = "repositoryEntry", cascade = CascadeType.ALL)
    private CourseDBEntryImpl courseDBEntry;
}
```

#### RepositoryEntryToGroupRelation (Course Role Groups)

```java
@Entity @Table(name = "o_re_to_group")
public class RepositoryEntryToGroupRelation {
    @Id @GeneratedValue(generator = "legacy-hilo")
    private Long key;
    
    @Version private int version;
    
    @ManyToOne @JoinColumn(name = "fk_entry", nullable = false)
    private RepositoryEntry repositoryEntry;
    
    @ManyToOne @JoinColumn(name = "fk_group", nullable = false)
    private GroupImpl group;
    
    @Column(name = "group_type", nullable = false)
    @Enumerated(EnumType.STRING)
    private RepositoryEntryGroupType groupType;  // OWNER, COACH, PARTICIPANT, WAITING, TEMPLATE
    
    // Each RepositoryEntry has up to 5 group types
}
```

### 4.3 Assessment Domain

#### AssessmentEntryImpl (`src/main/java/org/olat/modules/assessment/model/AssessmentEntryImpl.java`)

**Central assessment tracking entity** — one per user per assessable course element.

```java
@Entity @Table(name = "o_as_entry")
@Cacheable @Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
@NamedQueries({
    @NamedQuery(name = "assessmentEntriesByIdentityAndEntry",
        query = "select ae from AssessmentEntryImpl ae where ae.identity.key = :identityKey and ae.repositoryEntry.key = :entryKey"),
    @NamedQuery(name = "assessmentEntriesByEntryAndSubpath",
        query = "select ae from AssessmentEntryImpl ae where ae.repositoryEntry.key = :entryKey and ae.subPath = :subPath")
})
public class AssessmentEntryImpl implements AssessmentEntry, Serializable {
    @Id @GeneratedValue(generator = "legacy-hilo")
    private Long key;
    
    @Version private int version;
    
    // Links
    @ManyToOne @JoinColumn(name = "fk_identity", nullable = false)
    private IdentityImpl identity;
    
    @ManyToOne @JoinColumn(name = "fk_entry", nullable = false)
    private RepositoryEntry repositoryEntry;
    
    @Column(name = "sub_path", nullable = false, length = 128)
    private String subPath;  // Course element identifier (e.g., "iqtest_123")
    
    // Assessment configuration
    @Column(name = "obligation", nullable = false)
    @Enumerated(EnumType.STRING)
    private AssessmentObligation obligation;  // MANDATORY, OPTIONAL, NOT_REQUIRED
    
    @Column(name = "assessment_mode")
    @Enumerated(EnumType.STRING)
    private AssessmentMode assessmentMode;
    
    // Results
    @Column(name = "score", precision = 10, scale = 4)
    private BigDecimal score;          // 0.0 - 1.0 normalized
    
    @Column(name = "grade", length = 32)
    private String grade;              // Letter grade (A-F, or custom)
    
    @Column(name = "passed")
    private Boolean passed;
    
    @Column(name = "completion", precision = 5, scale = 2)
    private BigDecimal completion;     // 0.0 - 100.0 percentage
    
    @Column(name = "attempts")
    private Integer attempts;          // Number of attempts
    
    @Column(name = "visits")
    private Integer visits;            // Number of times opened
    
    // Coach assignment
    @ManyToOne @JoinColumn(name = "fk_coach")
    private IdentityImpl coach;
    
    // Run tracking (for multiple assessment runs)
    @Column(name = "run", nullable = false)
    private Integer run = 1;           // Incremented on re-take
    
    // Status
    @Column(name = "status", nullable = false)
    @Enumerated(EnumType.STRING)
    private AssessmentEntryStatus status;  // NEW, IN_PROGRESS, DONE, SUSPENDED
    
    // Timestamps
    @Column(name = "creation_date", nullable = false)
    private Date creationDate;
    
    @Column(name = "last_modified")
    private Date lastModified;
    
    @Column(name = "completion_date")
    private Date completionDate;
}
```

#### AssessmentTestSessionImpl (`src/main/java/org/olat/ims/qti21/model/jpa/AssessmentTestSessionImpl.java`)

**QTI 2.1 test session persistence** — links to AssessmentEntry for score sync.

```java
@Entity @Table(name = "o_qti_assessmenttest_session")
@Cacheable @Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class AssessmentTestSessionImpl implements AssessmentTestSession {
    @Id @GeneratedValue(generator = "legacy-hilo")
    private Long key;
    
    @Version private int version;
    
    // Link to assessment entry (score sync target)
    @ManyToOne @JoinColumn(name = "fk_entry")
    private AssessmentEntryImpl assessmentEntry;
    
    // QTI identifiers
    @Column(name = "test_identifier", length = 128)
    private String testIdentifier;
    
    @Column(name = "test_title", length = 256)
    private String testTitle;
    
    // Session state
    @Column(name = "state", nullable = false)
    @Enumerated(EnumType.STRING)
    private TestSessionState state;  // RUNNING, FINISHED, TERMINATED, SUSPENDED
    
    // Timing
    @Column(name = "start_time", nullable = false)
    private Date startTime;
    
    @Column(name = "finish_time")
    private Date finishTime;
    
    @Column(name = "termination_time")
    private Date terminationTime;
    
    @Column(name = "elapsed_time")
    private Long elapsedTime;  // Milliseconds
    
    // Extra time accommodations
    @Column(name = "extra_time")
    private Long extraTime;  // Milliseconds
    
    @Column(name = "compensation_time")
    private Long compensationTime;
    
    // Results
    @Column(name = "score", precision = 10, scale = 4)
    private BigDecimal score;
    
    @Column(name = "passed")
    private Boolean passed;
    
    @Column(name = "completion_status", length = 32)
    private String completionStatus;  // COMPLETED, INCOMPLETE, NOT_ATTEMPTED
    
    @Column(name = "success_status", length = 32)
    private String successStatus;     // PASSED, FAILED, UNKNOWN
    
    // Item sessions (one-to-many)
    @OneToMany(mappedBy = "assessmentTestSession", cascade = CascadeType.ALL)
    private Set<AssessmentItemSessionImpl> itemSessions = new HashSet<>();
}
```

#### AssessmentResponseImpl (`src/main/java/org/olat/ims/qti21/model/jpa/AssessmentResponseImpl.java`)

**Individual question response** — stores raw and processed response data.

```java
@Entity @Table(name = "o_qti_assessment_response")
public class AssessmentResponseImpl implements AssessmentResponse {
    @Id @GeneratedValue(generator = "legacy-hilo")
    private Long key;
    
    @Version private int version;
    
    @ManyToOne @JoinColumn(name = "fk_itemsession", nullable = false)
    private AssessmentItemSessionImpl assessmentItemSession;
    
    @ManyToOne @JoinColumn(name = "fk_testsession")
    private AssessmentTestSessionImpl assessmentTestSession;
    
    // QTI response identification
    @Column(name = "response_identifier", length = 128, nullable = false)
    private String responseIdentifier;
    
    @Column(name = "response_data_type", length = 64)
    private String responseDataType;  // base.string, base.integer, etc.
    
    // Raw response (JSON/XML stringified)
    @Column(name = "stringuified_response", length = 65535)
    private String stringuifiedResponse;
    
    // Scored values
    @Column(name = "score", precision = 10, scale = 4)
    private BigDecimal score;
    
    @Column(name = "max_score", precision = 10, scale = 4)
    private BigDecimal maxScore;
    
    // Response status
    @Column(name = "response_status", length = 32)
    private String responseStatus;  // CORRECT, INCORRECT, PARTIAL, UNANSWERED
}
```

### 4.4 File & VFS Domain

OpenOLAT uses a **dual storage model**: files on filesystem (`bcroot/`) + metadata in database.

#### VFS Abstraction (`src/main/java/org/olat/core/util/vfs/VFSManager.java`)

```java
public class VFSManager {
    
    // Root containers
    public static VFSContainer olatRootContainer(String path) { ... }
    public static VFSContainer courseContainer(RepositoryEntry entry, String subPath) { ... }
    public static VFSContainer groupContainer(BusinessGroup group, String subPath) { ... }
    
    // Core operations
    public static void copyContent(InputStream in, VFSLeaf target, Identity doer) { ... }
    public static void copyContent(VFSLeaf source, VFSLeaf target, Identity doer) { ... }
    public static void copyContent(VFSContainer source, VFSContainer target, Identity doer) { ... }
    
    // Quota management
    public static QuotaManager getQuotaManager() { ... }
    public static void checkQuota(VFSContainer container, long bytes, Identity identity) { ... }
    
    // Path resolution
    public static VFSContainer resolveOrCreateContainerFromPath(String path) { ... }
}
```

#### VFS Metadata Persistence (`src/main/java/org/olat/core/commons/services/vfs/`)

```java
// VFSMetadataImpl - o_vfs_metadata
@Entity @Table(name = "o_vfs_metadata")
@Cacheable @Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class VFSMetadataImpl implements VFSMetadata {
    @Id @GeneratedValue(generator = "legacy-hilo")
    private Long key;
    
    @Version private int version;
    
    @Column(name = "uuid", nullable = false, unique = true, length = 36)
    private String uuid;              // Stable file identifier
    
    @Column(name = "relative_path", length = 1024)
    private String relativePath;
    
    @Column(name = "filename", length = 256)
    private String filename;
    
    @Column(name = "file_size")
    private Long fileSize;
    
    @Column(name = "mime_type", length = 128)
    private String mimeType;
    
    @Column(name = "transcoding_status")
    @Enumerated(EnumType.STRING)
    private TranscodingStatus transcodingStatus;
    
    @Column(name = "download_count")
    private Long downloadCount = 0L;
    
    @Column(name = "locked")
    private Boolean locked = false;
    
    @Column(name = "lock_date")
    private Date lockDate;
    
    @Column(name = "lock_owner")
    private Long lockOwner;
    
    // Revision tracking
    @OneToMany(mappedBy = "metadata", cascade = CascadeType.ALL)
    private Set<VFSRevisionImpl> revisions = new HashSet<>();
    
    @ManyToOne @JoinColumn(name = "fk_current_revision")
    private VFSRevisionImpl currentRevision;
}

// VFSRevisionImpl - o_vfs_revision
@Entity @Table(name = "o_vfs_revision")
public class VFSRevisionImpl implements VFSRevision {
    @Id @GeneratedValue(generator = "legacy-hilo")
    private Long key;
    
    @Version private int version;
    
    @ManyToOne @JoinColumn(name = "fk_metadata", nullable = false)
    private VFSMetadataImpl metadata;
    
    @Column(name = "revision_number")
    private Integer revisionNumber;
    
    @Column(name = "file_size")
    private Long fileSize;
    
    @Column(name = "created_date", nullable = false)
    private Date createdDate;
    
    @ManyToOne @JoinColumn(name = "fk_creator")
    private IdentityImpl creator;
}
```

#### VFSRepositoryService Interface

```java
public interface VFSRepositoryService {
    // Metadata management
    VFSMetadata createMetadata(VFSLeaf leaf, Identity doer);
    VFSMetadata loadMetadata(VFSLeaf leaf);
    VFSMetadata loadMetadataByUuid(String uuid);
    
    // Revision/versioning
    VFSRevision createRevision(VFSMetadata metadata, VFSLeaf leaf, Identity doer);
    List<VFSRevision> getRevisions(VFSMetadata metadata);
    void restoreRevision(VFSRevision revision, Identity doer);
    
    // Thumbnails
    VFSThumbnailMetadata createThumbnail(VFSMetadata metadata, VFSLeaf leaf);
    VFSThumbnailMetadata getThumbnail(VFSMetadata metadata);
    
    // Search
    List<VFSMetadata> searchMetadata(String query, VFSContainer container);
    List<VFSMetadata> findByFilename(String filename, VFSContainer container);
    
    // Locking
    void lock(VFSMetadata metadata, Identity identity);
    void unlock(VFSMetadata metadata, Identity identity);
    boolean isLocked(VFSMetadata metadata);
}
```

### 4.5 Learning Progress Tracking

#### LearningPathStatus (`src/main/java/org/olat/course/learningpath/LearningPathStatus.java`)

```java
public enum LearningPathStatus {
    NOT_ACCESSIBLE,   // Prerequisites not met
    READY,            // Available to start
    IN_PROGRESS,      // User has started
    IN_REVIEW,        // Submitted, awaiting coach review
    DONE              // Completed and passed
}

// Derived from AssessmentEvaluation in LearningPathNode
// Not directly persisted — computed at runtime from AssessmentEntry
```

#### CurriculumLearningProgress (`src/main/java/org/olat/modules/curriculum/CurriculumLearningProgress.java`)

```java
public enum CurriculumLearningProgress {
    ENABLED,      // Progress tracking active
    DISABLED,     // Progress tracking disabled
    INHERITED     // Inherited from parent curriculum element
}
```

#### CurriculumElement Progress Tracking

```java
// In CurriculumElementImpl
@OneToMany(mappedBy = "curriculumElement")
private Set<CurriculumElementUserProgress> userProgress = new HashSet<>();

// CurriculumElementUserProgress (o_ce_user_progress)
@Entity @Table(name = "o_ce_user_progress")
public class CurriculumElementUserProgressImpl {
    @Id @GeneratedValue(generator = "legacy-hilo")
    private Long key;
    
    @Version private int version;
    
    @ManyToOne @JoinColumn(name = "fk_identity", nullable = false)
    private IdentityImpl identity;
    
    @ManyToOne @JoinColumn(name = "fk_curriculum_element", nullable = false)
    private CurriculumElementImpl curriculumElement;
    
    @Column(name = "status")
    @Enumerated(EnumType.STRING)
    private CurriculumElementStatus status;  // NOT_STARTED, IN_PROGRESS, COMPLETED, FAILED
    
    @Column(name = "progress", precision = 5, scale = 2)
    private BigDecimal progress;  // 0-100%
    
    @Column(name = "score", precision = 10, scale = 4)
    private BigDecimal score;
    
    @Column(name = "completion_date")
    private Date completionDate;
}
```

### 4.6 Groups & Memberships (Detailed)

See 4.1 for `GroupImpl` and `GroupMembershipImpl`. Key additional entities:

#### BusinessGroup (`src/main/java/org/olat/group/BusinessGroupImpl.java`)

```java
@Entity @Table(name = "o_bg_business_group")
public class BusinessGroupImpl implements BusinessGroup {
    @Id @GeneratedValue(generator = "legacy-hilo")
    private Long key;
    
    @Version private int version;
    
    @ManyToOne @JoinColumn(name = "fk_base_group", nullable = false)
    private GroupImpl baseGroup;  // Links to o_bs_group
    
    @Column(name = "type")
    @Enumerated(EnumType.STRING)
    private BusinessGroupType type;  // OPEN, CLOSED, WAITING_LIST
    
    @Column(name = "max_participants")
    private Integer maxParticipants;
    
    @Column(name = "waiting_list_enabled")
    private Boolean waitingListEnabled = false;
    
    @Column(name = "auto_enrollment")
    private Boolean autoEnrollment = false;
    
    // Course relation
    @ManyToOne @JoinColumn(name = "fk_entry")
    private RepositoryEntry repositoryEntry;
    
    // Areas (group areas for collaboration)
    @OneToMany(mappedBy = "businessGroup")
    private Set<BGAreaImpl> areas = new HashSet<>();
}
```

---

## 5. DAO Patterns and Service Layer Access

### 5.1 Standard DAO Pattern

```java
// Interface (in manager package)
public interface MyEntityDAO {
    MyEntity loadByKey(Long key);
    List<MyEntity> findByCriteria(Criteria criteria);
    void save(MyEntity entity);
    void delete(MyEntity entity);
}

// Implementation
@Repository
public class MyEntityDAOImpl implements MyEntityDAO {
    @Autowired private DB dbInstance;
    
    @Override
    public MyEntity loadByKey(Long key) {
        return dbInstance.getCurrentEntityManager().find(MyEntity.class, key);
    }
    
    @Override
    public List<MyEntity> findByCriteria(Criteria criteria) {
        StringBuilder jpql = new StringBuilder("select e from MyEntity e where 1=1");
        Map<String, Object> params = new HashMap<>();
        
        if (criteria.getName() != null) {
            jpql.append(" and e.name = :name");
            params.put("name", criteria.getName());
        }
        // ... more criteria
        
        TypedQuery<MyEntity> query = dbInstance.getCurrentEntityManager()
            .createQuery(jpql.toString(), MyEntity.class);
        params.forEach(query::setParameter);
        return query.getResultList();
    }
    
    @Override
    public void save(MyEntity entity) {
        dbInstance.saveObject(entity);
    }
}
```

### 5.2 Manager/Service Layer

```java
// Interface
public interface MyManager {
    MyEntity create(MyEntity entity);
    MyEntity update(MyEntity entity);
    void delete(Long key);
    List<MyEntity> findAll();
    MyEntity loadByKey(Long key);
}

// Implementation
@Service("myManager")
public class MyManagerImpl implements MyManager {
    @Autowired private MyEntityDAO dao;
    @Autowired private DB dbInstance;
    @Autowired private EventBus eventBus;  // For cross-session events
    
    @Override
    @Transactional  // Spring transaction boundary
    public MyEntity create(MyEntity entity) {
        dao.save(entity);
        dbInstance.commit();  // Explicit commit for immediate visibility
        eventBus.fireEventToListenersOf(new MyEntityCreatedEvent(entity), 
            OresHelper.createOLATResourceableInstance("MyEntity", entity.getKey()));
        return entity;
    }
    
    @Override
    @Transactional
    public void delete(Long key) {
        MyEntity entity = dao.loadByKey(key);
        if (entity != null) {
            dao.delete(entity);
            dbInstance.commit();
        }
    }
}
```

### 5.3 PersistenceHelper Utilities (`src/main/java/org/olat/core/commons/persistence/PersistenceHelper.java`)

```java
public class PersistenceHelper {
    
    // Chunk large IN clauses (max 1000 params per query for Oracle)
    public static <T> List<List<T>> chunkKeys(List<T> keys) {
        return chunkKeys(keys, 1000);
    }
    
    public static <T> List<List<T>> chunkKeys(List<T> keys, int chunkSize) {
        List<List<T>> chunks = new ArrayList<>();
        for (int i = 0; i < keys.size(); i += chunkSize) {
            chunks.add(keys.subList(i, Math.min(i + chunkSize, keys.size())));
        }
        return chunks;
    }
    
    // Extract BigDecimal from Object[] query results
    public static BigDecimal extractBigDecimal(Object[] row, int pos, BigDecimal defaultValue) {
        Object val = row[pos];
        if (val == null) return defaultValue;
        if (val instanceof BigDecimal) return (BigDecimal) val;
        if (val instanceof Number) return new BigDecimal(val.toString());
        return defaultValue;
    }
    
    // Extract Long from Object[] query results
    public static Long extractLong(Object[] row, int pos, Long defaultValue) { ... }
}
```

### 5.4 Query Patterns

| Pattern | Example |
|---------|---------|
| **Simple find** | `em.find(Entity.class, key)` |
| **JPQL with named params** | `em.createQuery("select e from Entity e where e.name = :name", Entity.class).setParameter("name", name)` |
| **Projection** | `em.createQuery("select e.key, e.name from Entity e", Object[].class)` |
| **Pagination** | `query.setFirstResult(offset).setMaxResults(pageSize)` |
| **Chunked IN** | `PersistenceHelper.chunkKeys(keys).forEach(chunk -> query.setParameter("keys", chunk))` |
| **Native SQL** | `em.createNativeQuery("select * from table where col = ?", Entity.class).setParameter(1, val)` |

---

## 6. Read/Write Path Tracing for Key Operations

### 6.1 User Login → Identity Load

```
HTTP Request
    → AuthenticationFilter
    → AuthenticationManager.authenticate()
    → IdentityDAO.loadByName(username)
    → DB.getCurrentEntityManager().find(IdentityImpl.class) [by name query]
    → Session established with Identity in UserSession
```

### 6.2 Course Access → RepositoryEntry Load

```
CourseRuntimeController.init()
    → RepositoryEntryRepository.loadByKey(entryKey)
    → DB.getCurrentEntityManager().find(RepositoryEntry.class, entryKey)
    → (Lazy) loads groups, organizations, taxonomy levels via @OneToMany
    → CourseDBEntryImpl loaded via @OneToOne
```

### 6.3 Assessment Submission Flow

```
AssessmentTestDisplayController.submit()
    → QTI21Service.saveResponse(response)          [AssessmentResponseImpl]
    → QTI21Service.finishTestSession(session)      [AssessmentTestSessionImpl]
    → AssessmentTestSessionDAO.update(session)
    → AssessmentEntryOutcomesListener.onTestFinished()
    → AssessmentService.updateAssessmentEntry()
    → AssessmentEntryDAO.save(entry)               [AssessmentEntryImpl]
    → DB.commit() (Spring transaction boundary)
```

### 6.4 File Upload Flow

```
FileElement.processUpload()
    → FileUploadItem.getInputStream()
    → VFSManager.copyContent(inputStream, targetLeaf, identity)
    → VFSRepositoryService.createMetadata(leaf, identity)
    → VFSMetadataImpl persisted to o_vfs_metadata
    → VFSRevisionImpl created for version 1
    → File stored on filesystem at bcroot/...
```

### 6.5 Group Membership Assignment

```
GroupManager.addMember(group, identity, role)
    → GroupMembershipDAO.checkExisting(group, identity)
    → new GroupMembershipImpl(group, identity, role)
    → GroupMembershipDAO.save(membership)
    → EventBus.fireEvent(GroupChangedEvent)
    → DB.commit()
```

---

## 7. Schema Evolution Mechanisms

### 7.1 Entity Registration

**All entities must be listed in `persistence.xml`** — no auto-discovery (`exclude-unlisted-classes=true`).

**Adding new entity checklist:**
- [ ] Create entity class with `@Entity`, `@Table`, `@Id` (legacy-hilo)
- [ ] Add `@Version` field (`private int version;`)
- [ ] Add to `persistence.xml` in alphabetical package order
- [ ] Add `@Cacheable` + `@Cache(usage = READ_WRITE)` if cacheable
- [ ] Create DAO with `@Autowired DB`
- [ ] Create Manager interface + impl with `@Service` and `@Transactional`
- [ ] Add indexes via `@Table(indexes = @Index(...))` for query performance

### 7.2 ID Generation Strategy

**Legacy-Hilo (used by 95%+ of entities):**

```java
@Id
@GeneratedValue(generator = "legacy-hilo")
@TableGenerator(
    name = "legacy-hilo",
    table = "hibernate_sequences",
    pkColumnName = "sequence_name",
    valueColumnName = "next_val",
    pkColumnValue = "entity_name",  // Unique per entity
    allocationSize = 1
)
private Long key;
```

**Sequence-based (newer entities):**

```java
@Id
@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "entity_seq")
@SequenceGenerator(name = "entity_seq", sequenceName = "entity_seq", allocationSize = 1)
private Long key;
```

### 7.3 Database Migration

OpenOLAT uses **manual schema evolution** — no Flyway/Liquibase. Changes are applied via:

1. **Upgrade classes** in `org.olat.upgrade.model.*` (run at startup)
2. **SQL scripts** in `src/main/resources/db/migration/` (manual execution)
3. **Hibernate DDL** (`hibernate.hbm2ddl.auto=validate` in production)

**fLMS Consideration:** New entities will require corresponding upgrade scripts for production deployments.

### 7.4 Optimistic Locking

All entities have `@Version`:

```java
@Version
@Column(name = "version", nullable = false)
private int version;
```

- Prevents lost updates in concurrent edits
- Throws `OptimisticLockException` on conflict
- Handled by controllers with retry/merge logic

---

## 8. Second-Level Cache Configuration

### 8.1 Cache Mode

```xml
<property name="jakarta.persistence.sharedCache.mode" value="ENABLE_SELECTIVE"/>
```

Only entities annotated with `@Cacheable` use the second-level cache.

### 8.2 Cache Annotations

```java
@Entity @Table(name = "o_repositoryentry")
@Cacheable
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE, region = "repositoryEntry")
public class RepositoryEntry { ... }
```

### 8.3 Cache Regions (Infinispan)

Configured in `infinispan-config.xml`:

```xml
<cache-container name="hibernate" default-cache="default">
    <local-cache name="repositoryEntry">
        <expiration max-idle="900000" lifespan="3600000"/>  <!-- 15min idle, 1hr max -->
        <memory max-count="10000" when-full="REMOVE"/>
    </local-cache>
    <local-cache name="identity">
        <expiration max-idle="1800000" lifespan="7200000"/>
        <memory max-count="50000" when-full="REMOVE"/>
    </local-cache>
    <!-- Default: 10,000 entries, 15 min idle -->
</cache-container>
```

### 8.4 Cache Invalidation

- **Cluster-wide**: Infinispan invalidation via JGroups/JMS
- **On update**: `@Cache(usage = READ_WRITE)` auto-invalidates on entity update
- **Manual**: `cacheContainer.getCache("region").remove(key)` or `evictAll()`

### 8.5 fLMS Cache Strategy

| Entity Type | Cache Strategy | Rationale |
|-------------|----------------|-----------|
| Reference data (taxonomy, grades) | `READ_ONLY` / long TTL | Rarely changes |
| User profiles | `READ_WRITE` / medium TTL | Moderate change frequency |
| Assessment entries | `READ_WRITE` / short TTL | High write frequency |
| Course metadata | `READ_WRITE` / medium TTL | Balance read/write |

---

## 9. VFS Integration with Relational Persistence

### 9.1 Dual Storage Model

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application Layer                          │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│   Relational Database   │     │     Filesystem (bcroot)   │
│  (Metadata, Indexes,    │     │  (Actual file content,    │
│   Relations, ACLs)      │     │   thumbnails, versions)   │
│                         │     │                         │
│  o_vfs_metadata         │     │  /bcroot/course/123/     │
│  o_vfs_revision         │     │    files/document.pdf    │
│  o_vfs_thumbnail        │     │    .versions/1.pdf       │
└─────────────────────────┘     └─────────────────────────┘
```

### 9.2 Key Integration Points

| Operation | DB Action | VFS Action |
|-----------|-----------|------------|
| **Upload** | `VFSMetadataImpl` + `VFSRevisionImpl` created | File written to `bcroot/...` |
| **Download** | `download_count` incremented | File streamed from `bcroot/...` |
| **Versioning** | New `VFSRevisionImpl` linked to metadata | Old file moved to `.versions/` |
| **Delete** | Metadata marked deleted (soft) | File moved to trash or deleted |
| **Move/Rename** | `relative_path`, `filename` updated | Filesystem rename/move |

### 9.3 Quota Enforcement

```java
// Checked before every write
public void checkQuota(VFSContainer container, long bytes, Identity identity) {
    QuotaManager quotaManager = VFSManager.getQuotaManager();
    long used = quotaManager.getUsedSpace(container);
    long limit = quotaManager.getQuota(container, identity);
    if (used + bytes > limit) {
        throw new QuotaExceededException("Quota exceeded for " + container);
    }
}
```

Quota configuration in `olat.properties`:
```
vfs.quota.default=10737418240  # 10GB default
vfs.quota.course=5368709120    # 5GB per course
vfs.quota.group=1073741824     # 1GB per group
```

---

## 10. fLMS Extension Implications

### 10.1 Competency-Based Learning Pathways

**Required New Entities:**
```java
// Competency Framework
@Entity @Table(name = "flms_competency_framework")
public class CompetencyFrameworkImpl { ... }

// Competency (skill/knowledge unit)
@Entity @Table(name = "flms_competency")
public class CompetencyImpl { ... }

// Learning Pathway (sequence of competencies)
@Entity @Table(name = "flms_learning_pathway")
public class LearningPathwayImpl { ... }

// User Competency Progress
@Entity @Table(name = "flms_user_competency_progress")
public class UserCompetencyProgressImpl { ... }

// Pathway Enrollment
@Entity @Table(name = "flms_pathway_enrollment")
public class PathwayEnrollmentImpl { ... }
```

**Integration Points:**
- Link to `RepositoryEntry` via `taxonomyLevels` (existing)
- Extend `CurriculumElement` with competency references
- New `AssessmentEntry` sub-types for competency evidence
- EventBus events for progress tracking

### 10.2 Assessment Simulators (PIX-style)

**Required Extensions:**
```java
// Simulator Configuration
@Entity @Table(name = "flms_simulator_config")
public class SimulatorConfigImpl { ... }

// Simulator Session (extends AssessmentTestSession)
@Entity @Table(name = "flms_simulator_session")
public class SimulatorSessionImpl { ... }

// Simulator State (complex JSON state)
@Entity @Table(name = "flms_simulator_state")
public class SimulatorStateImpl { ... }
```

**Leverage Existing:**
- `AssessmentTestSessionImpl` for session management
- `AssessmentResponseImpl` for interaction logging
- `QTI21Service` for delivery engine
- `AssessmentEntryOutcomesListener` for score sync

### 10.3 Analytics & Reporting

**Denormalized Analytics Tables:**
```java
@Entity @Table(name = "flms_analytics_daily")
public class DailyAnalyticsImpl { ... }  // Aggregated daily metrics

@Entity @Table(name = "flms_user_analytics")
public class UserAnalyticsImpl { ... }   // Per-user rolled-up metrics

@Entity @Table(name = "flms_course_analytics")
public class CourseAnalyticsImpl { ... } // Per-course metrics
```

**ETL Pattern:** Background `LongRunnable` jobs aggregate from transactional tables to analytics tables.

---

## 11. Safe Extension Points

### 11.1 Database Extension (Safe)

| Extension Type | Mechanism | Risk |
|----------------|-----------|------|
| **New entity tables** | Add to `persistence.xml`, create DAO/Manager | Low — isolated |
| **New columns on existing tables** | `@Column` on existing entity + migration script | Medium — requires schema migration |
| **New indexes** | `@Table(indexes = @Index(...))` + migration | Low — performance only |
| **New @OneToMany collections** | Add to existing entity + migration | Medium — cascade behavior |
| **New @ManyToOne references** | Add FK column + migration | Medium — referential integrity |

### 11.2 VFS Extension (Safe)

| Extension | Mechanism |
|-----------|-----------|
| **Custom metadata fields** | Extend `VFSMetadataImpl` with `@Embedded` or new columns |
| **Custom VFS providers** | Implement `VFSContainer`/`VFSLeaf` for S3, Azure, etc. |
| **Additional revision data** | Extend `VFSRevisionImpl` |
| **New thumbnail sizes** | Extend `VFSThumbnailMetadataImpl` |

### 11.3 Service Layer Extension (Safe)

| Pattern | Example |
|---------|---------|
| **New Manager service** | Implement interface, `@Service`, `@Autowired DB` |
| **EventBus listeners** | Register in `init()`, deregister in `doDispose()` |
| **Background jobs** | Implement `LongRunnable`, submit via `TaskExecutorManager` |
| **Cache regions** | Declare in `infinispan-config.xml`, use `@Cacheable` |

### 11.4 Unsafe / High-Risk Extensions

| Anti-Pattern | Why Unsafe |
|--------------|------------|
| Direct `bcroot/` file access | Bypasses VFS, quota, metadata, cluster sync |
| String concatenation in JPQL | SQL injection, query plan cache pollution |
| Missing `@Version` on new entities | Lost updates in concurrent access |
| Skipping `commitAndCloseSession()` in background jobs | Connection leaks, transaction not committed |
| Direct `EntityManager` access without DB facade | Bypasses ThreadLocal, statistics, transaction management |
| Modifying entities during render phase | Violates architecture rule, causes lazy loading exceptions |

---

## 12. Summary of Key Findings

### 12.1 Architecture Strengths

1. **Centralized DB facade** (`DB`/`DBImpl`) ensures consistent transaction management
2. **Explicit entity registration** prevents accidental entity loading
3. **Legacy-hilo ID strategy** works across PostgreSQL, Oracle, MySQL
4. **Spring `@Transactional`** on services provides clear boundaries
5. **VFS abstraction** cleanly separates file content from metadata
6. **EventBus integration** enables cross-module reactivity
7. **Infinispan 2nd-level cache** with `ENABLE_SELECTIVE` gives granular control

### 12.2 Critical Rules for fLMS Development

| Rule | Enforcement |
|------|-------------|
| All DB access via `DB` facade | Code review, architecture tests |
| Named parameters in JPQL only | Static analysis, code review |
| `@Version` on all entities | Compile-time (entity base class) |
| `commitAndCloseSession()` in background jobs | Documentation, code review |
| No business logic in render phase | Controller base class convention |
| VFS for all file operations | `VFSManager` only entry point |
| Deregister EventBus in `doDispose()` | Code review, memory leak detection |

### 12.3 fLMS Data Model Recommendations

| Domain | Recommended Approach |
|--------|---------------------|
| **Competencies** | New entities linked to `TaxonomyLevel` + `RepositoryEntry` |
| **Learning Pathways** | New entities with `CurriculumElement` integration |
| **Simulators** | Extend `AssessmentTestSession` + custom state entity |
| **Analytics** | Denormalized tables populated by `LongRunnable` ETL jobs |
| **File submissions** | Use existing VFS + `VFSMetadata` extensions |
| **Progress tracking** | Extend `CurriculumElementUserProgress` + new pathway progress |

### 12.4 Next Steps for fLMS Implementation

1. **Define fLMS entity package**: `org.olat.modules.flms.model`
2. **Create base entity class** with legacy-hilo, `@Version`, common audit fields
3. **Register in persistence.xml** (maintain alphabetical order)
4. **Implement DAO/Manager** following `IdentityDAO`/`IdentityManager` patterns
5. **Add cache configuration** in `infinispan-config.xml`
6. **Create upgrade scripts** for schema deployment
7. **Add integration tests** using `DBTest` base class
8. **Document EventBus events** for cross-module integration

---

## Appendix: Key Source File References

| Area | Key Files |
|------|-----------|
| DB Facade | `src/main/java/org/olat/core/commons/persistence/DB.java`<br>`src/main/java/org/olat/core/commons/persistence/DBImpl.java` |
| Persistence Config | `src/main/resources/META-INF/persistence.xml` |
| Identity/User | `src/main/java/org/olat/basesecurity/IdentityImpl.java`<br>`src/main/java/org/olat/user/UserImpl.java`<br>`src/main/java/org/olat/basesecurity/model/GroupImpl.java`<br>`src/main/java/org/olat/basesecurity/model/GroupMembershipImpl.java` |
| DAO Pattern | `src/main/java/org/olat/basesecurity/manager/IdentityDAO.java` |
| RepositoryEntry | `src/main/java/org/olat/repository/RepositoryEntry.java` |
| Assessment | `src/main/java/org/olat/modules/assessment/model/AssessmentEntryImpl.java`<br>`src/main/java/org/olat/ims/qti21/model/jpa/AssessmentTestSessionImpl.java`<br>`src/main/java/org/olat/ims/qti21/model/jpa/AssessmentResponseImpl.java` |
| VFS | `src/main/java/org/olat/core/util/vfs/VFSManager.java`<br>`src/main/java/org/olat/core/commons/services/vfs/VFSRepositoryService.java`<br>`src/main/java/org/olat/core/commons/services/vfs/VFSMetadata.java` |
| Learning Progress | `src/main/java/org/olat/course/learningpath/LearningPathStatus.java`<br>`src/main/java/org/olat/modules/curriculum/CurriculumLearningProgress.java` |
| Cache Config | `src/main/resources/infinispan-config.xml` |
| Persistence Helper | `src/main/java/org/olat/core/commons/persistence/PersistenceHelper.java` |

---

*Document created as part of Phase 5.1 investigation. All claims verified against source code at commit 20e0b6b2f1.*
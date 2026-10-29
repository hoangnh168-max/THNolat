# Repository Baseline

## Repository Identity
- **Local Path:** `C:\Users\huyho\IdeaProjects\fLMS`
- **Git Remote:** `https://github.com/OpenOLAT/OpenOLAT` (as seen in pom.xml scm.url)
- **Current Branch:** `master`
- **Current Commit SHA:** `20e0b6b2f15333d3c785cce0e670ab5bd6b6c828`
- **Repository Status:** Working tree has untracked files (docs/ directory)

## Version and Build Information
- **Project Version:** `21.2-SNAPSHOT` (from pom.xml)
- **Project Name:** OpenOLAT LMS
- **Required Java Version:** 17+ (from maven-enforcer-plugin configuration and properties.targetJdk)
- **Required Maven Version:** 3.0.5+ (from maven-enforcer-plugin)
- **Build System:** Maven (multi-module project)
- **Packaging:** WAR (web application archive)

## Top-Level Directory Inventory
```
.
├── .claude/               # Claude Code configuration (skills, agents, etc.)
├── .git/                  # Git repository data
├── .github/               # GitHub workflows and templates
├── .idea/                 # IntelliJ IDEA project files
├── doc/                   # Technical documentation (architecture, etc.)
├── scripts/               # Build and utility scripts
├── src/                   # Source code
│   ├── main/              # Main source
│   │   ├── java/          # Java source code
│   │   ├── resources/     # Configuration, XML, properties files
│   │   └── webapp/        # Web application resources (static files, WEB-INF)
│   └── test/              # Test sources
├── LICENSE                # Apache 2.0 license
├── NOTICE.TXT             # Copyright notices
├── README.md              # Project overview
├── olat.local.properties.sample  # Template for local configuration
├── openolat-lms.iml       # IntelliJ module file
└── pom.xml                # Maven project descriptor
Untracked directories:
├── docs/                  # Documentation directory (not tracked by Git)
   └── claude-code/        # Claude Code knowledge base
      ├── 00-REPOSITORY-BASELINE.md
      ├── 02-MODULE-CATALOG.md
      ├── 03-PACKAGE-AND-SYMBOL-INDEX.md
      ├── 12-INVESTIGATION-LEDGER.md
      ├── 13-CLAUDE-CODE-ENTRY-POINT.md
      ├── 14-I18N-AND-LOCALIZATION.md
      └── INVESTIGATION_SUMMARY.md
```

## Build Requirements and Profiles
- **Java:** Version 17 (specified in `<targetJdk>17</targetJdk>`)
- **Maven:** 3.0.5+ (enforced by maven-enforcer-plugin)
- **Active Profiles by Default:** `tomcat` (activates Tomcat-specific dependencies and webapp resources)
- **Available Profiles:**
  - `compressjs`: JavaScript and CSS compression
  - `tomcat`: Default profile for Tomcat deployment
  - `jbosseap`: JBoss EAP deployment
  - `wildfly`: WildFly deployment (experimental)
  - `mysqlunittests`, `postgresqlunittests`, `oracleunittests`: Test profiles for specific databases

## Key Dependencies (from pom.xml)
- **Spring Framework:** 7.0.9
- **Hibernate ORM:** 7.4.13.Final
- **Hibernate Validator:** 9.1.5.Final
- **Apache Log4j:** 2.26.1
- **Apache CXF:** 4.2.4 (for web services)
- **Apache PDFBox:** 3.0.8
- **Apache POI:** 5.5.1 (for Microsoft Office formats)
- **Infinispan:** 16.3.0 (caching)
- **Lucene:** 7.7.0 (search)
- **Jackson:** 2.22.4 (JSON processing)
- **MySQL Connector/J:** 26.7.0
- **PostgreSQL JDBC:** 42.7.14
- **ActiveMQ Artemis:** 2.57.0 (messaging)
- **LangChain4j:** 1.22.0 (AI integrations)
- **MCP SDK:** 2.0.1 (Model Context Protocol)

## Investigation Scope
As per the mission, this investigation aims to:
1. Establish a persistent technical knowledge base for OpenOLAT
2. Inventory all first-party modules and their responsibilities
3. Map major architectural components and dependencies
4. Trace key end-to-end workflows (login, course access, assessment submission, etc.)
5. Analyze persistence layer and data model
6. Document API and integration boundaries
7. Identify safe extension points for future fLMS development
8. Produce navigable documentation in `docs/claude-code/`

## Current Progress
**Phase 1 — Baseline and inventory: IN PROGRESS**
- ✅ Repository identity established
- ✅ Git branch and commit recorded
- ✅ Working tree status confirmed (untracked docs/ directory noted)
- ✅ Build requirements identified from pom.xml
- ✅ Top-level directory inventory completed
- ⏳ Detailed module inventory pending
- ⏳ Source code analysis pending
- ⏳ Documentation files creation pending

**Next Steps:**
1. Complete detailed inventory of src/main/java/org/olat package structure
2. Examine key modules (core, course, modules) to understand responsibilities
3. Begin Phase 2 — Module mapping: inspect module descriptors and map dependencies

## Investigation Constraints
- No modification of source code, configuration, or build files
- Only read-only operations permitted during investigation
- Documentation updates limited to `docs/claude-code/` directory
- Must preserve original repository state for future sessions

*Baseline updated: 2026-10-20*
# OpenOLAT Package and Symbol Index

This document provides a searchable index of packages and significant classes/interfaces in the OpenOLAT codebase. It serves as a navigational aid for understanding the codebase structure.

## Top-Level Packages (org.olat)

The main packages under `org/olat` are:

| Package | Description |
|---------|-------------|
| **admin** | Administrative functions, user management, system configuration |
| **basesecurity** | Core security: authentication, authorization, roles, organizations |
| **collaboration** | Collaboration tools and social features |
| **commons** | Common utilities, services, and shared components |
| **core** | Core framework: controllers, GUI components, utilities, configuration |
| **course** | Course management: creation, execution, lifecycle, course elements |
| **dispatcher** | Request dispatching and routing |
| **fileresource** | File resource handling and storage |
| **group** | Group management (course groups, business groups) |
| **gui** | GUI framework: components, controllers, FlexiTable, windows |
| **home** | Personal home page and dashboard |
| **ims** | IMS standards integration: LTI, QTI, etc. |
| **instantMessaging** | Real-time chat and messaging |
| **ldap** | LDAP integration and synchronization |
| **login** | Authentication mechanisms and login modules |
| **mcp** | Model Context Protocol for AI integrations |
| **modules** | Feature modules (60+ optional modules) |
| **note** | Note-taking functionality |
| **portal** | Portal and site management |
| **properties** | Configuration properties management |
| **registration** | User registration and invitation workflows |
| **repository** | Resource repository and metadata management |
| **resource** | Resource access control and permissions |
| **restapi** | REST API endpoints and services |
| **search** | Search functionality and indexing |
| **shibboleth** | Shibboleth SSO integration |
| **social** | Social networking and community features |
| **upgrade** | Database upgrade and migration scripts |
| **user** | User profiles, preferences, and personal data |
| **util** | Utility classes and helper functions |

## Package Details

### org.olat.admin
Administrative console and backend management functions.

**Subpackages:**
- `admin.bc` - Briefcase/file administration
- `admin.cache` - Cache monitoring and management
- `admin.help` - Help system administration
- `admin.landingpages` - Custom landing pages
- `admin.layout` - Page layout and template management
- `admin.notifications` - Notification system administration
- `admin.privacy` - Privacy and data protection controls
- `admin.quota` - Storage quota management
- `admin.registration` - User registration workflows
- `admin.restapi` - Administrative REST API endpoints
- `admin.search` - Search configuration and administration
- `admin.security` - Security administration and monitoring
- `admin.securitygroup` - Security group and role management
- `admin.setup` - Initial system setup and configuration
- `admin.site` - Site management and configuration
- `admin.statistics` - Usage statistics and reporting
- `admin.sysinfo` - System information and monitoring
- `admin.user` - User administration and management

### org.olat.basesecurity
Core security infrastructure.

**Subpackages:**
- `basesecurity.events` - Security-related events and listeners
- `basesecurity.manager` - Security managers (auth, role, session)
- `basesecurity.model` - Security model classes (User, Group, Role, etc.)
- `basesecurity.webdav` - WebDAV integration and access control

### org.olat.commons
Shared utilities, services, and common components used across the application.

**Subpackages:**
- `commons.calendar` - Calendar and scheduling functionality
- `commons.commonservices` - Various service integrations (mail, SMS, PDF, etc.)
- `commons.controllers` - Shared GUI controllers
- `commons.files` - File handling utilities
- `commons.persistence` - Persistence utilities and DAO bases
- `commons.rights` - Access control and permission utilities
- `commons.services` - Service interfaces and base implementations
- `commons.util` - Utility classes (StringHelper, Formatter, etc.)
- `commons.web` - Web-related utilities (URL handling, etc.)

### org.olat.core
Core framework components providing fundamental infrastructure and services.

**Subpackages:**
- `core.configuration` - Spring configuration and module system (AbstractSpringModule, ConfigOnOff, PersistedProperties)
- `core.dispatcher` - Request dispatching and routing (Dispatcher, DispatcherModule)
- `core.gui` - GUI framework: components, controllers, windows (Controller, DefaultController, WindowControl, UserRequest)
- `core.id` - Identifier generation and context management (Identity, User, Roles, OLATResourceable)
- `core.logging` - Logging and tracing utilities (Tracing, AssertException)
- `core.util` - Core utilities (StringHelper, WebappHelper, Util)
- `core.util.coordinate` - Coordinator manager for inter-controller communication (CoordinatorManager)
- `core.helpers` - Application helpers (Settings, WebappHelper)

**Key Responsibilities:**
- Provides the foundation for the module system via AbstractSpringModule
- Manages HTTP request processing through the dispatcher system
- Implements the GUI framework with controller hierarchies and component model
- Handles identity, roles, and security contexts
- Offers centralized logging, configuration, and utility services
- Coordinates cross-component communication through CoordinatorManager

### org.olat.course
Course management and execution engine.

**Subpackages:**
- `course.assessment` - Assessment and test execution
- `course.certificate` - Certificate generation
- `course.commitment` - Commitment and enrollment tracking
- `course.db` - Database access for course data
- `course.env` - Course environment and configuration
- `course.generator` - Course generation and templating
- `course.nodes` - Course elements and learning activities
- `course.odsa` - Open Digital Scholarly Authentication
- `course.presentation` - Course presentation and rendering
- `course.ref` - Reference management for course elements
- `course.security` - Course-specific security and access control
- `course.tree` - Course structure and navigation
- `course.user` - User-course relationships (membership, roles, etc.)
- `course.wizard` - Course creation and configuration wizards

### org.olat.modules
Optional feature modules (60+ modules). Each module is self-contained.

See `02-MODULE-CATALOG.md` for complete module listing.

## Significant Interfaces and Base Classes

### Key Base Classes
- `org.olat.core.configuration.AbstractSpringModule` - Base class for most modules
- `org.olat.user.UserModule` - Base for user-related modules
- `org.olat.core.gui.control.GenericController` - Base GUI controller
- `org.olat.core.gui.control.WindowControl` - Window controller base
- `org.olat.core.gui.control.Event` - Event base class
- `org.olat.core.util.SpringTools` - Spring utility helpers

### Important Interfaces
- `org.olat.core.gui.control.Controller` - Main GUI controller interface
- `org.olat.core.gui.window.Window` - Window interface
- `org.olat.core.util.cache.UserStorageManager` - User session storage
- `org.olat.repository.RepositoryEntry` - Resource entry interface
- `org.olat.basesecurity.manager.Security` - Security manager interface
- `org.olat.course.nodes.CourseNode` - Course element node interface
- `org.olat.course.assessment.Assessment` - Assessment interface
- `org.olat.restapi.RestAPI` - REST API endpoint registration

## Symbol Index Guidelines

This index will be expanded in subsequent phases to include:
- Significant classes and their responsibilities
- Key interfaces and their contracts
- Important methods and their signatures
- Configuration classes and properties
- Service interfaces and implementations
- Entity classes and persistence mappings
- Utility classes and helper functions

*Index created: 2026-10-20*
*Status: Phase 1 - Baseline inventory in progress*
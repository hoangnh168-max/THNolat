# BaseSecurity Package Structure (`org.olat.basesecurity`)

The basesecurity package contains core security infrastructure including authentication, authorization, roles, organizations, and user management.

## Overview

The basesecurity package serves as the foundation for all security-related functionality in OpenOLAT, providing:
- Authentication mechanisms and user identity management
- Role-based access control (RBAC) and permission systems
- Organization and group management
- User search and administration capabilities
- Security-related services and utilities

## Sub-packages and Responsibilities

| Package | Responsibility | Key Classes/Interfaces |
|---------|----------------|------------------------|
| `org.olat.basesecurity` | Root basesecurity package | BaseSecurity, BaseSecurityManager, Authentication |
| `org.olat.basesecurity.events` | Security-related events and listeners | Various event classes for security changes |
| `org.olat.basesecurity.manager` | Security managers (auth, role, session) | AuthenticationManager, RoleManager, SessionManager |
| `org.olat.basesecurity.model` | Security model classes (User, Group, Role, etc.) | User, Group, Role, Organisation, Identity |
| `org.olat.basesecurity.webdav` | WebDAV integration and access control | WebDAV security handling |

## Key Components

### Core Security Classes
- **BaseSecurity**: Main security interface providing core security operations
- **BaseSecurityManager**: Central manager for security operations, implements BaseSecurity
- **Authentication**: Interface for authentication mechanisms
- **AuthenticationImpl**: Default implementation of authentication
- **AuthHelper**: Utility class for authentication-related operations
- **Identity**: Represents a user identity in the system
- **IdentityImpl**: Default implementation of Identity
- **User**: Extends Identity with user-specific properties
- **Group**: Represents a group of users
- **Role**: Represents a role that can be assigned to users/groups
- **Organisation**: Represents an organization/institution

### Security Management
- **AuthenticationManager**: Handles authentication processes
- **RoleManager**: Manages roles and role assignments
- **SessionManager**: Manages user sessions and session security
- **SearchIdentityParams**: Parameters for searching identities/users
- **IdentityRef**: Lightweight reference to an identity

### Security Model
- **OrganisationRoles**: Enumeration of standard roles in the system
- **GroupMembership**: Represents membership of a user in a group
- **OrganisationEmailDomain**: Email domain associations for organizations
- **OrganisationType**: Types of organizations (university, company, etc.)
- **SecurityGroup**: Grouping of roles for easier permission management

### Events
- Various event classes for security-related changes (user creation, role assignment, etc.)

### WebDAV Integration
- WebDAV security handling and access control for WebDAV resources

## Architectural Patterns

1. **Role-Based Access Control (RBAC)**: Permissions are assigned to roles, which are assigned to users/groups
2. **Hierarchical Organization**: Organizations can contain sub-organizations in a tree structure
3. **Pluggable Authentication**: Supports multiple authentication mechanisms via the Authentication interface
4. **Separation of Concerns**: Clear separation between security model, managers, and core interfaces
5. **Delegation Pattern**: BaseSecurityModule delegates to BaseSecurityManager for actual security operations
6. **Configuration-Driven**: Many security features are configurable via properties (wiki enabled, user search settings, etc.)
7. **Extensible Model**: Security model designed to be extended for custom attributes and relationships

## Key Design Principles

1. **Centralized Security**: All security checks route through BaseSecurityManager
2. **Defensive Programming**: Extensive null checking and validation
3. **Auditing**: Security-relevant operations are logged for audit trails
4. **Performance Optimization**: Caching strategies for frequently accessed security data
5. **Backward Compatibility**: Care taken to maintain API compatibility across versions
6. **Internationalization Ready**: Security messages and labels are externalized for i18n
7. **Testability**: Components designed to be easily unit tested with mocks

## Important Classes and Interfaces

| Class/Interface | Package | Responsibility |
|----------------|---------|----------------|
| `BaseSecurity` | `org.olat.basesecurity` | Main security interface for core operations |
| `BaseSecurityManager` | `org.olat.basesecurity.manager` | Central manager implementing BaseSecurity |
| `Authentication` | `org.olat.basesecurity` | Interface for authentication mechanisms |
| `AuthenticationImpl` | `org.olat.basesecurity` | Default authentication implementation |
| `AuthHelper` | `org.olat.basesecurity` | Authentication-related utility functions |
| `Identity` | `org.olat.basesecurity.model` | Represents a user identity |
| `IdentityImpl` | `org.olat.basesecurity.model` | Default Identity implementation |
| `User` | `org.olat.basesecurity.model` | Extends Identity with user-specific properties |
| `Group` | `org.olat.basesecurity.model` | Represents a group of users |
| `Role` | `org.olat.basesecurity.model` | Represents a role for permission assignment |
| `Organisation` | `org.olat.basesecurity.model` | Represents an organization/institution |
| `OrganisationRoles` | `org.olat.basesecurity.model` | Standard roles enumeration |
| `GroupMembership` | `org.olat.basesecurity.model` | User-group membership relationship |
| `IdentityRef` | `org.olat.basesecurity.model` | Lightweight identity reference |
| `SearchIdentityParams` | `org.olat.basesecurity.manager` | Parameters for identity/user searches |
| `SecurityGroup` | `org.olat.basesecurity.model` | Grouping of roles for permission management |
| `OrganisationType` | `org.olat.basesecurity.model` | Organization type classification |
| `OrganisationEmailDomain` | `org.olat.basesecurity.model` | Email domain configuration for orgs |

## BaseSecurityModule Responsibilities

The BaseSecurityModule extends AbstractSpringModule and is responsible for:

1. **Configuration Management**:
   - Manages user search properties for different roles (admin props, last login visibility, etc.)
   - Controls wiki enabling via `base.security.wiki` property
   - Manages identity name generation strategy
   - Configures relation role management settings

2. **Context Entry Registration**:
   - Registers UserAdminContextEntryControllerCreator for user administration
   - Provides context entry controllers for user management in the admin console

3. **Property Synchronization**:
   - Keeps configuration properties synchronized with the persistence layer
   - Updates internal properties when configuration changes

4. **Security Feature Flags**:
   - Controls whether wiki functionality is enabled
   - Manages user search capabilities (admin props, last login visibility, autocomplete, bulk search)
   - Configures relation role management features

5. **Security Policy Methods**:
   - Determines if users can view admin properties based on their roles
   - Controls last login visibility based on user roles
   - Manages autocomplete and bulk search permissions
   - Evaluates critical user/invitee change permissions
   - Provides utility methods for role-based access decisions

## Integration Points

- **Used by Core**: Core packages utilize basesecurity for authentication and authorization
- **Used by GUI**: GUI framework depends on basesecurity for user context and permissions
- **Used by Modules**: All feature modules rely on basesecurity for access control
- **Used by Services**: Service implementations check permissions via basesecurity
- **Used by REST API**: REST endpoints validate user permissions through basesecurity
- **Used by Admin Console**: Administrative functions depend heavily on basesecurity

## Configuration Properties

The module manages numerous configuration properties including:
- User search administration properties for each role type
- Last login visibility settings for each role type
- User search autocomplete settings for each role type
- User search bulk operations settings for each role type
- Wiki enablement flag (`base.security.wiki`)
- Identity name generation strategy (`identity.name`)
- Relation role management flags
- Maximum results for user searches

## Key Workflows

1. **Authentication**: User credentials validated via AuthenticationManager
2. **Authorization**: Permission checks performed via BaseSecurityManager
3. **User Management**: Admin console uses context entry controllers for user administration
4. **Role Management**: Roles assigned to users/groups via RoleManager
5. **Session Management**: User sessions created, validated, and invalidated via SessionManager
6. **Organization Hierarchy**: Organizations structured in trees with inheritance of properties
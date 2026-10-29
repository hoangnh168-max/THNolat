# Commons Package Structure (`org.olat.commons`)

The commons package contains shared utilities, services, and components that are used across multiple modules and packages in OpenOLAT.

## Overview

The commons package serves as a shared library of functionality that cuts across the application, providing:
- Common GUI controllers and components
- Shared services (mail, SMS, PDF generation, etc.)
- Utility classes for string manipulation, formatting, etc.
- Persistence helpers and DAO bases
- Access control and permission utilities
- Web-related helpers

## Sub-packages and Responsibilities

| Package | Responsibility | Key Classes/Interfaces |
|---------|----------------|------------------------|
| `org.olat.commons` | Root commons package | Various shared utilities |
| `org.olat.commons.controller` | Shared GUI controllers | Various reusable controllers |
| `org.olat.commons.services` | Service interfaces and implementations | MailService, SMSService, etc. |
| `org.olat.commons.util` | Utility classes | StringHelper, Formatter, etc. |
| `org.olat.commons.persistence` | Persistence utilities and DAO bases | GenericDAO, etc. |
| `org.olat.commons.rights` | Access control and permission utilities | Various permission helpers |
| `org.olat.commons.files` | File handling utilities | File upload/download helpers |
| `org.olat.commons.web` | Web-related utilities | URL handling, etc. |
| `org.olat.commons.calendar` | Calendar and scheduling functionality | Calendar utilities |
| `org.olat.commons.commonservices` | Various service integrations | External service adapters |

## Key Components

### Shared Controllers (`org.olat.commons.controller`)
- Reusable GUI controllers for common UI patterns
- Examples: File chooser controllers, activity log controllers, impression controllers
- Designed to be embedded in multiple contexts across different modules

### Shared Services (`org.olat.commons.services`)
- Service interfaces for common functionality:
  - MailService - Sending emails
  - SMSService - Sending SMS messages
  - PDFService - PDF generation and manipulation
  - GraphService - Graph/chart generation
  - Various integration services (Twitter, LinkedIn, etc.)

### Utility Classes (`org.olat.commons.util`)
- StringHelper - String manipulation utilities (containsNonWhitespace, escaping, etc.)
- Formatter - Number and date formatting utilities
- Various collection and iteration helpers
- Encoding/decoding utilities

### Persistence Helpers (`org.olat.commons.persistence`)
- GenericDAO - Base implementation for data access objects
- Persistence helpers for common database operations
- Transaction management utilities

### Access Control Utilities (`org.olat.commons.rights`)
- Permission checking helpers
- Access evaluation utilities
- Role-based access control helpers

## Architectural Patterns

1. **Shared Services**: Common functionality extracted into reusable services
2. **Utility-First Approach**: Common string/collection/web utilities centralized
3. **Controller Reusability**: GUI controllers designed for embedding in multiple contexts
4. **Service Interface Pattern**: Well-defined interfaces for swappable implementations
5. **Persistence Abstraction**: Common DAO patterns to reduce boilerplate
6. **Separation of Concerns**: Each subpackage has a clear, focused responsibility

## Integration Points

- **Used by Modules**: All feature modules can import and use commons packages
- **Used by Core**: Core packages utilize commons services and utilities
- **Used by GUI**: GUI framework depends on commons controllers and utilities
- **Used by Services**: Various service implementations depend on commons helpers
- **Configuration Access**: Commons provides access to system settings via Settings class

## Key Design Principles

1. **DRY (Don't Repeat Yourself)**: Common functionality extracted to commons
2. **Modularity**: Loose coupling between commons and consuming packages
3. **Reusability**: Components designed for use in multiple contexts
4. **Consistency**: Standardized approaches to common problems
5. **Backward Compatibility**: Care taken to maintain API stability

## Examples of Usage

- A module needing to send emails would use MailService from commons.services
- A controller needing to display formatted dates would use Formatter from commons.util
- A file upload component would use helpers from commons.files
- A permission check would use utilities from commons.rights
- Database access would build upon bases in commons.persistence

The commons package represents the "shared toolkit" of OpenOLAT, enabling consistency and reducing duplication across the codebase.
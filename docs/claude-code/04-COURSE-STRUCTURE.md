# Course Package Structure (`org.olat.course`)

The course package manages the creation, execution, and lifecycle of courses in OpenOLAT. It serves as the central engine for learning activities.

## Overview

The course package is responsible for:
- Course creation and configuration
- Course execution and lifecycle management
- Course elements (learning activities) management
- Course membership and user tracking
- Course-level services and utilities

## Sub-packages and Responsibilities

| Package | Responsibility | Key Classes/Interfaces |
|---------|----------------|------------------------|
| `org.olat.course` | Core course management | `CourseModule`, `ICourse`, `CourseFactory` |
| `org.olat.course.assessment` | Assessment and testing | `AssessmentModule`, `AssessmentManager`, `Assessment` |
| `org.olat.course.certificate` | Certificate generation | `CertificatesModule` |
| `org.olat.course.commitment` | Commitment and enrollment tracking | (To be investigated) |
| `org.olat.course.db` | Database access for course data | (To be investigated) |
| `org.olat.course.env` | Course environment and configuration | `CourseEnvironment` |
| `org.olat.course.generator` | Course generation and templating | (To be investigated) |
| `org.olat.course.nodes` | Course elements and learning activities | `CourseNode`, various node types |
| `org.olat.course.odsa` | Open Digital Scholarly Authentication | (To be investigated) |
| `org.olat.course.presentation` | Course presentation and rendering | (To be investigated) |
| `org.olat.course.ref` | Reference management for course elements | (To be investigated) |
| `org.olat.course.security` | Course-specific security and access control | (To be investigated) |
| `org.olat.course.tree` | Course structure and navigation | `Structure` |
| `org.olat.course.user` | User-course relationships | (To be investigated) |
| `org.olat.course.wizard` | Course creation and configuration wizards | (To be investigated) |

## Key Components

### CourseModule (`org.olat.course.CourseModule`)
- Main module class extending `AbstractSpringModule`
- Manages course-level configuration and settings
- Provides access to course-type defaults and execution settings
- Handles course metadata like teaser images, infobox settings, etc.
- Integrates with assessment and other course-related systems

### ICourse (`org.olat.course.ICourse`)
- Interface representing a course instance
- Defines core course operations and properties
- Used throughout the system for course references

### CourseFactory (`org.olat.course.CourseFactory`)
- Factory for creating course instances
- Handles course instantiation from repository entries
- Manages course lifecycle transitions

### CourseEnvironment (`org.olat.course.env.CourseEnvironment`)
- Represents the runtime environment of a course
- Provides access to course-specific settings and resources
- Used during course execution to contextualize operations

### CourseNode (`org.olat.course.nodes.CourseNode`)
- Base interface for all course elements (learning activities)
- Defines common operations for learning activities
- Extended by specific node types (assessment, wiki, forum, etc.)

### Structure (`org.olat.course.Structure`)
- Represents the hierarchical structure of a course
- Manages course nodes and their relationships
- Handles course navigation and sequencing

## Architectural Patterns

1. **Course as Modular Entity**: Courses are composed of CourseNodes which can be various learning activities
2. **Separation of Concerns**: Course management is divided into modules (assessment, certificate, etc.) that integrate with the core course system
3. **Environment Context**: CourseEnvironment provides runtime context for course operations
4. **Factory Pattern**: CourseFactory handles course instantiation and lifecycle management
5. **Node-Based Structure**: Courses are trees of CourseNodes enabling flexible course designs
6. **Plugin Architecture**: Course elements (nodes) can be developed as plugins extending the base CourseNode

## Integration Points

- **Repository System**: Courses are stored and versioned in the repository via RepositoryModule
- **Assessment System**: AssessmentModule integrates with CourseModule for test execution within courses
- **Certificate System**: Certificate generation is triggered by course completion
- **Security System**: Course-specific access controls integrate with BaseSecurityModule
- **Groups System**: Course membership and group interactions managed through GroupModule
- **Notification System**: Course events trigger notifications via commons.services.notifications

## Configuration

CourseModule manages numerous configuration properties including:
- Course type defaults (progress, classic, etc.)
- Default execution settings
- UI display preferences (infobox, changelog, etc.)
- Teaser image configuration
- Archive retention policies
- Efficiency statement settings
- Various feature flags for course behavior

## Key Workflows

1. **Course Creation**: User creates course via wizard → CourseFactory creates course instance → Stored in repository
2. **Course Execution**: Course accessed → CourseEnvironment initialized → Course nodes activated based on structure
3. **Learning Activity Execution**: User interacts with CourseNode → Node-specific controller handles interaction → State persisted
4. **Course Completion**: Completion conditions evaluated → Certificates generated → Course archived based on retention policy
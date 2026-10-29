# OpenOLAT Architecture Overview

This document provides an overview of the OpenOLAT architecture based on the investigation of the codebase.

## Core Package (`org.olat.core`)

The core package contains fundamental infrastructure and services that are used throughout the application.

### Key Components

1. **CoreSpringFactory** - Central factory for accessing Spring beans and resources
2. **CoreSpringInitializer** - Bootstrap Spring initialization with OpenOLAT-specific configurations
3. **Configuration System** (`org.olat.core.configuration`) -
   - `AbstractSpringModule` - Base class for all modules that extends Spring functionality
   - `ConfigOnOff` - Simple interface for modules that can be enabled/disabled
   - `PersistedProperties` - Handles module-specific configuration persistence
4. **GUI Framework** (`org.olat.core.gui`) -
   - Controller hierarchy: `Controller` → `DefaultController` → specialized controllers
   - Window management and user request handling
   - Component system for building UI elements
5. **Dispatcher System** (`org.olat.core.dispatcher`) -
   - Main entry point for HTTP requests
   - Mapper system for session-unique URLs
   - Static media delivery
6. **Util** (`org.olat.core.util`) -
   - String helpers, coordination managers, tracing/logging
   - Session management, user context handling
7. **Helpers** (`org.olat.core.helpers`) -
   - Settings access, web application helpers
8. **Logging** (`org.olat.core.logging`) -
   - Tracing, activity logging, exception handling
9. **ID System** (`org.olat.core.id`) -
   - Identity, roles, OLATResourceable system for security and permissions

### Architectural Patterns

- **Module System**: All features are implemented as modules extending `AbstractSpringModule`
- **Configuration**: Modules use `@Value` annotations with defaults and read configuration in `init()` method
- **Event System**: Generic event listener pattern for module communication
- **Spring Integration**: Heavy use of Spring dependency injection via `@Autowired`
- **Controller Lifecycle**: Framework manages controller creation, event handling, and disposal
- **Persistence**: Core services provide access to DB layer and transaction management

### Key Design Principles

1. **Server-Centric UI**: All state lives on server, browser receives HTML fragments via AJAX
2. **Module Independence**: Features are packaged as independent modules that can be enabled/disabled
3. **Spring-Based**: Extensive use of Spring for dependency injection and configuration
4. **Event-Driven**: Communication between components happens through events
5. **Configuration Over Code**: Module behavior is configurable through properties files
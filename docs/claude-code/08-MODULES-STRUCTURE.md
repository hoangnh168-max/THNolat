# Modules Package Structure (`org.olat.modules`)

The modules package contains all feature modules that extend the core functionality of OpenOLAT. Each module is self-contained and can be enabled/disabled independently.

## Overview

The modules package follows a modular architecture where:
- Each feature is implemented as a separate module extending `AbstractSpringModule`
- Modules can be enabled/disabled via configuration properties
- Modules register context entry controllers for integration with the admin console
- Modules follow a standard structure with `_content/`, `_i18n/`, and `_spring/` directories
- Modules interact with core services through dependency injection
- The package represents the extensibility point of OpenOLAT for adding new features

## Standard Module Structure

Each module in `org.olat.modules` typically contains:

```
org.olat.modules.modulename/
├── Modulename.java                 # Main module class (extends AbstractSpringModule)
├── _content/                       # Velocity templates (*.vm files)
├── _i18n/                          # Internationalization files (LocalStrings_XX.properties)
├── _spring/                        # Spring configuration files
├── manager/                        # Service interfaces and implementations
├── model/                          # JPA/Hibernate entity classes
├── ui/                             # User interface controllers and components
└── restapi/                        # REST API endpoints (if applicable)
```

## Key Characteristics of Modules

1. **Spring Integration**: All modules are Spring beans annotated with `@Service`
2. **Configuration Pattern**: Modules use `@Value` annotations to inject configuration properties
3. **Initialization**: Modules implement `init()` and `initFromChangedProperties()` methods
4. **Dependency Injection**: Modules receive required services via constructor injection (typically `CoordinatorManager`)
5. **Context Registration**: Modules register context entry controllers via `NewControllerFactory.addContextEntryControllerCreator()`
6. **ConfigOnOff**: Some modules implement `ConfigOnOff` interface for simple enable/disable functionality
7. **Persistence**: Modules typically use Hibernate/JPA for data access via service layer (`*Manager` classes)
8. **Internationalization**: Modules include `_i18n/` directories with property files for UI text
9. **Templates**: Modules include `_content/` directories with Velocity templates for UI rendering

## Module Responsibilities

Modules are responsible for:

1. **Feature Implementation**: Providing specific functionality (assessment, video conferencing, file sharing, etc.)
2. **Configuration Management**: Reading and persisting module-specific configuration
3. **UI Contribution**: Adding UI components to the admin console and user interface
4. **Integration**: Registering with core systems (repository, menu, notifications, etc.)
5. **Lifecycle Management**: Handling initialization, configuration updates, and shutdown
6. **Security Integration**: Working with basesecurity for authentication and authorization
7. **Event Participation**: Publishing and subscribing to events via the EventBus
8. **REST Endpoints**: Providing programmatic access to functionality (when applicable)
9. **Data Persistence**: Defining and managing domain-specific data models

## Common Module Patterns

### Configuration Pattern
```java
@Value("${modulename.property:default}")
private String propertyName;

@Override
protected void initFromChangedProperties() {
    propertyName = getStringPropertyValue("modulename.property", propertyName);
}
```

### Constructor Injection
```java
@Autowired
public MyModule(CoordinatorManager coordinatorManager) {
    super(coordinatorManager);
    // additional dependencies
}
```

### Context Registration
```java
@Override
public void init() {
    NewControllerFactory.getInstance().addContextEntryControllerCreator(
        "EntityClassName", 
        new MyEntityContextEntryControllerCreator());
}
```

### Service Access Pattern
```java
// In service methods
MyService service = CoreSpringFactory.getImpl(MyService.class);
```

## Integration Points

- **Used by Core**: Core packages utilize modules for extended functionality
- **Used by GUI**: GUI framework integrates module context entries and UI components
- **Used by Services**: Module services are accessed via CoreSpringFactory
- **Used by REST API**: Module REST endpoints are registered with the main REST API
- **Used by Admin Console**: Administrative functions for modules are provided through context entries

## Configuration Properties

Modules typically manage configuration properties including:
- Enable/disable flags (`${modulename.enabled:true}`)
- Feature-specific settings
- Integration points with other systems
- UI customization options
- Behavior toggles
- Limits and thresholds

## Relationship with Other Packages

- **Depends on**: `org.olat.core` (framework), `org.olat.basesecurity` (security), `org.olat.commons` (utilities)
- **Depended by**: `org.olat.gui` (for UI integration), `org.olat.restapi` (for REST exposure)
- **Interacts with**: `org.olat.repository` (for resource storage), `org.olat.course` (for course integration)

## Examples of Module Types

1. **Simple On/Off Modules**: Basic feature toggles (e.g., ZoomModule, WikiModule)
2. **Integration Modules**: Connect to external systems (e.g., BigBlueButtonModule, ViteroModule)
3. **Content Modules**: Manage learning content (e.g., MediaModule, PodcastModule)
4. **Communication Modules**: Facilitate interaction (e.g., ForumModule, ChatModule)
5. **Assessment Modules**: Handle testing and evaluation (e.g., QuestionPoolModule, Assessment-related modules)
6. **Administrative Modules**: Provide admin console functionality (e.g., UserManager, OrganizationModule)
7. **Reporting Modules**: Generate reports and analytics (e.g., StatisticsModule, TrackerModule)
8. **Specialized Modules**: Domain-specific functionality (e.g., CurriculumModule, CompetencyModule)

## Notable Observations

- Most modules follow the pattern of having a `*Module.java` file in their package root
- Some larger modules (like assessment) may have more complex internal structure without a root Module.java
- Modules consistently use `AbstractSpringModule` as their base class
- Configuration properties follow the pattern `${modulename.property:default}`
- Modules register themselves as Spring services with `@Service` annotation
- All modules receive `CoordinatorManager` in their constructor for event bus access
- Modules demonstrate good separation of concerns between API, model, and UI layers
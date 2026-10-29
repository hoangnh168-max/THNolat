# GUI Package Structure (`org.olat.gui`)

The GUI package contains the user interface framework of OpenOLAT, including components, controllers, and rendering systems.

## Overview

OpenOLAT uses a server-centric UI architecture where:
- All UI state lives on the server
- The browser receives HTML fragments via AJAX
- There is no client-side framework (no React/Angular/Vue)
- The GUI package provides the building blocks for constructing server-rendered UIs

## Sub-packages and Responsibilities

| Package | Responsibility | Key Classes/Interfaces |
|---------|----------------|------------------------|
| `org.olat.gui` | Root GUI package | Various GUI components |
| `org.olat.gui.components` | UI components (buttons, links, panels, etc.) | Button, Link, Panel, Form elements |
| `org.olat.gui.control` | Controller framework and event system | Controller, DefaultController, Event |
| `org.olat.gui.render` | Rendering systems and output handling | StringOutput, various renderers |
| `org.olat.gui.translator` | Internationalization and translation | Translator, PackageTranslator |
| `org.olat.gui.theme` | Themings and skins | Theme management |
| `org.olat.gui.util` | GUI-specific utilities | Various helper functions |
| `org.olat.gui.media` | Media resources and handling | MediaResource, various media types |
| `org.olat.gui.recorder` | Audio/video recording components | Audio/video recorder controllers |
| `org.olat.gui.qrscanner` | QR code scanning functionality | QR scanner controllers |

## Key Components

### GUI Components (`org.olat.gui.components`)
- **Basic Elements**: Button, Link, Checkbox, RadioButton, TextElement, etc.
- **Containers**: Panel, SimplePanel, VelocityContainer (for templates)
- **Complex Components**: FlexiTable (data grid), TabContainer, AjaxDispatcher
- **Form Elements**: All form item types (text, select, checkbox, date, etc.)
- **Navigation**: Breadcrumbs, tabs, menus, trees
- **Display**: Images, videos, iframes, progress indicators
- **Specialized**: Color picker, date picker, rich text editors

### Controller Framework (`org.olat.gui.control`)
- **Controller Interface**: Base contract for all controllers
- **DefaultController**: Base implementation providing common functionality
- **Event System**: Event class and ControllerEventListener for communication
- **WindowControl**: Manages window/state information for controllers
- **ChiefController**: Specialized controller for handling chief (main) window operations
- **ModalController**: Base for modal dialog controllers
- **DispatchResult**: Result of controller dispatch operations

### Rendering System (`org.olat.gui.render`)
- **StringOutput**: Efficient string building for HTML generation
- **Various Renderers**: Specific renderers for different output formats
- **Velocity Integration**: Apache Velocity template engine integration
- **CSS/JS Management**: JSAndCSSAdder for managing client-side resources

### Internationalization (`org.olat.gui.translator`)
- **Translator**: Interface for resolving internationalized strings
- **PackageTranslator**: Translator for specific resource bundles
- **Locale Handling**: Management of user locales and fallback chains
- **MessageFormat**: Parameterized message support with {0}, {1}, etc.

### Media Handling (`org.olat.gui.media`)
- **MediaResource**: Abstract representation of media content
- **Various Implementations**: File-based, URL-based, dynamically generated media
- **Security**: Secure delivery of media with proper headers and tokens
- **Caching**: Support for browser caching through headers

## Architectural Patterns

1. **Component-Based UI**: UIs built by composing reusable components
2. **MVC Variants**: Controller-component separation with server-side state
3. **Event-Driven Communication**: Controllers communicate via events
4. **Hierarchical Controllers**: Parent-child controller relationships with automatic disposal
5. **Pluggable Rendering**: Support for different template engines (Velocity primary)
6. **State Management**: WindowControl encapsulates user interaction state
7. **Internationalization First**: Built-in i18n support with fallback chains
8. **Security-Aware**: Automatic XSS prevention through escaping requirements

## Controller Hierarchy

```
Controller (interface)
  └─ DefaultController (event dispatch, dispose lifecycle)
       └─ BasicController (listenTo, Velocity, mappers)
            ├─ FormBasicController (FlexiForm support)
            └─ ChiefController (chief window handling)
```

## Key Design Principles

1. **Server-Centric**: All state maintained on server, minimal client-side state
2. **Component Reusability**: UI components designed for reuse across contexts
3. **Controller Lifecycle**: Framework manages creation, event handling, and disposal
4. **Event Separation**: Component events vs controller events clearly separated
5. **Automatic Disposal**: listenTo() ensures automatic cleanup of child controllers
6. **Template Safety**: Velocity templates with required escaping for user content
7. **Internationalization**: Built-in support with fallback locale chains
8. **Accessibility**: Components designed with accessibility considerations
9. **Extensibility**: Framework designed for extension via subclassing

## Important Classes and Interfaces

| Class/Interface | Package | Responsibility |
|----------------|---------|----------------|
| `Controller` | `org.olat.gui.control` | Base contract for all controllers |
| `DefaultController` | `org.olat.gui.control` | Base implementation with event handling |
| `BasicController` | `org.olat.gui.control` | Extends DefaultController with Velocity support |
| `FormBasicController` | `org.olat.gui.control` | Adds FlexiForm support |
| `Component` | `org.olat.gui.components` | Base class for all UI components |
| `WindowControl` | `org.olat.gui.control` | Manages window/state for controllers |
| `UserRequest` | `org.olat.gui` | Encapsulates HTTP request information |
| `Event` | `org.olat.gui.control` | Base class for all events |
| `Translator` | `org.olat.gui.translator` | Internationalization string resolution |
| `PackageTranslator` | `org.olat.gui.translator` | Locale-specific translator |
| `MediaResource` | `org.olat.gui.media` | Abstract media representation |
| `StringOutput` | `org.olat.gui.render` | Efficient string builder for HTML |
| `FlexiTable` | `org.olat.gui.components` | Data grid/table component |
| `VelocityContainer` | `org.olat.gui.components` | Container for Velocity templates |

## Velocity Template Usage

Templates are stored in `_content/` directories alongside controllers:
- `$r.render("componentId")` - Renders a child component
- `$r.translate("key")` - Resolves internationalized string
- `$r.translate("key", $arg1)` - Resolves string with arguments
- `$r.escapeHtml($userText)` - **Critical**: Escapes user-provided text to prevent XSS
- `$r.sectionHeader("title")` - Creates section headers (New in 21.1.0)
- Conditional rendering: `#if($condition) ... #end`
- Loops: `#foreach($item in $list) ... #end`

## Important Notes

1. **XSS Prevention**: **Always** use `$r.escapeHtml($var)` for user-provided text in Velocity templates
   - Variables from `contextPut()` are NOT auto-escaped
   - Component rendering via `$r.render()` IS auto-escaped by the component
2. **Controller Disposal**: Always use `listenTo()` for child controllers to ensure automatic disposal
3. **Controller Replacement**: Use `removeAsListenerAndDispose()` before replacing a controller
4. **Event Registration**: Always deregister EventBus listeners in `doDispose()`
5. **Render Phase**: No business logic or DB access allowed during render phase
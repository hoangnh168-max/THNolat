# OpenOLAT Internationalization and Localization Architecture

## Overview

OpenOLAT provides a comprehensive internationalization (i18n) and localization (L10n) system that supports multiple languages, fallback chains, parameter substitution, gender strategies, and recursive key references. The system is designed to allow easy customization through overlay mechanisms without modifying the core code.

## Key Components

### I18nManager (`org.olat.core.util.i18n.I18nManager`)
Central class responsible for:
- Managing the fallback bundle chain
- Resolving translations with recursive key references
- Applying parameter substitution (`MessageFormat`)
- Processing gender strategies
- Handling missing keys (debug error message vs. returning key in production)
- Caching translators for performance

### PackageTranslator (`org.olat.core.util.i18n.PackageTranslator`)
Per-controller translator created via `I18nManager.createPackageTranslator(String bundleName)`. Responsible for:
- Delegating translation to `I18nManager`
- Providing a simple `translate(String key)` and `translate(String key, Object[] args)` API
- Created per controller in `BasicController.getTranslator()`

### I18nModule (`org.olat.core.util.i18n.I18nModule`)
Spring module that initializes the i18n system and configures the fallback chain.

### Velocity Render Decorator (`org.olat.core.gui.render.VelocityRenderDecorator`)
Provides the `$r.translate()` method in Velocity templates, which delegates to the current controller's translator.

## Translation Files

### Location and Naming
- Located in `_i18n/` subdirectories alongside controller packages (e.g., `src/main/java/org/olat/core/gui/_i18n/LocalStrings_de.properties`)
- Named `LocalStrings_XX.properties` where `XX` is the language code (e.g., `de`, `en`, `fr`)
- Must be sorted alphabetically by key (mandatory)

### Fallback Chain
When a key is not found in the primary bundle, the system checks bundles in this order:
1. `de_CH__customizing` (Swiss German overlay)
2. `de_CH` (Swiss German)
3. `de__customizing` (German overlay)
4. `de` (German)
5. `en__customizing` (English overlay)
6. `en` (English, default)
7. `en` (English, final fallback)

### Overlay Mechanism
Clients can customize translations via:
```
{userData}/customizing/lang/overlay/{package}/_i18n/LocalStrings_XX__customizing.properties
```
- Overlay files take precedence over the corresponding base bundle
- Allows language-specific customizations without modifying the shipped JARs

## Translation Resolution

### Recursive Key References
- Same-package: `$\:other.key` or `${other.key}` (references another key in the same `.properties` file)
- Cross-package: `$org.olat.other.package:other.key` or `${org.olat.other.package:other.key}`
- Recursive resolution limited to 10 levels deep to prevent infinite loops
- Verified in `I18nTest.testRecursiveResolution()`

### Parameter Substitution
- Uses `java.text.MessageFormat`
- Parameters: `{0}`, `{1}`, etc.
- Escape single quotes as `''`
- Example: `"msg.format": "Hello {0}, you have {1} new messages."`

### Gender Strategy
- Supports constructs like `Benutzer{in}` (German) or `Utilisateur{trice}` (French)
- Conversion based on locale-specific configuration (star `*`, colon `:`, etc.)
- Handled during translation resolution before parameter substitution

### Missing Key Handling
- **Development/Debug mode**: Returns error message like `[!!! KEY_NOT_FOUND: my.missing.key !!!]`
- **Production mode**: Returns the key itself (e.g., `my.missing.key`) to avoid breaking the UI
- Controlled by `I18nManager.DEBUG_MODE` (set via Java system property or configuration)

## Usage in Java

### In Controllers
Controllers extending `BasicController` (or `FormBasicController`) have access to:
```java
// Simple translation
String msg = translate("my.key");

// With parameters
String msg = translate("my.key", new String[]{param1, param2});

// Access the translator directly (rarely needed)
PackageTranslator translator = getTranslator();
```

### Creating a PackageTranslator Manually
```java
PackageTranslator translator = CoreSpringFactory.getImpl(I18nManager.class)
    .createPackageTranslator("org.olat.my.package");
```

## Usage in Velocity Templates
```velocity
## Simple translation
$r.translate("my.key")

## With parameters
$r.translate("greeting", $userName)
$r.translate("msg.format", $arg1, $arg2)

## Nested translation (recursive)
#set($nestedKey = "$\:other.key")
$r.translate($nestedKey)
```

## Testing
- See `src/test/java/org/olat/core/util/i18n/I18nTest.java` for comprehensive tests covering:
  - Recursive key resolution (up to 10 levels)
  - Fallback chain order
  - Parameter substitution
  - Gender strategy processing
  - Missing key behavior in debug vs. production
  - Overlay mechanism

## Recommendations for Vietnamese Localization

### Adding Vietnamese Translation
1. Create `LocalStrings_vi.properties` files in the appropriate `_i18n/` directories
2. Follow the alphabetical ordering requirement for keys
3. Provide translations for all keys present in the base language (German) bundles
4. Consider creating an overlay for client-specific customizations:
   ```
   {userData}/customizing/lang/overlay/org.olat.my.package/_i18n/LocalStrings_vi__customizing.properties
   ```

### Important Notes
- Vietnamese does not typically use gender strategies, but the system will still process gender constructs if present in the source keys
- Ensure recursive key references are valid and do not create circular dependencies
- Test thoroughly with the `I18nTest` test suite as a reference for expected behavior
- When in doubt, refer to the German (`de`) bundles as the source of truth for terminology
- Consult `doc/i18n-translation-reference.yaml` for mandatory term translations (generated from the concept map)

## Source References
- `BasicController.java` - `translate()` and `getTranslator()` methods
- `FormBasicController.java` - inherits translation functionality
- `Util.java` - `createPackageTranslator` factory method
- `PackageTranslator.java` - translation delegation and fallback
- `I18nManager.java` - fallback chain, recursion, parameter substitution, gender strategy, missing-key handling
- `VelocityRenderDecorator.java` - `$r.translate` implementation in Velocity
- `I18nTest.java` - test evidence for all features

## Verification
All claims in this document have been verified against the OpenOLAT source code at commit `20e0b6b2f15333d3c785cce0e670ab5bd6b6c828` (OpenOLAT 21.2-SNAPSHOT).
# Claude Code Entry Point for OpenOLAT Investigation

This document serves as the entry point for navigating the OpenOLAT investigation documentation created in the `docs/claude-code/` directory.

## Documentation Overview

The investigation has produced the following documents:

- [**00-REPOSITORY-BASELINE.md**](00-REPOSITORY-BASELINE.md) - Repository identity, commit, version, and build requirements
- [**12-INVESTIGATION-LEDGER.md**](12-INVESTIGATION-LEDGER.md) - Tracking progress across investigation phases
- [**02-MODULE-CATALOG.md**](02-MODULE-CATALOG.md) - Catalog of all 60 first-party modules
- [**03-PACKAGE-AND-SYSTEM-INDEX.md**](03-PACKAGE-AND-SYSTEM-INDEX.md) - Top-level package overview (org.olat)
- [**14-I18N-AND-LOCALIZATION.md**](14-I18N-AND-LOCALIZATION.md) - Internationalization and localization architecture (this follow-up investigation)

## How to Verify Localization Claims

To verify claims about OpenOLAT's internationalization and localization system against the source code:

1. **Controller Translation Methods**
   - Check `src/main/java/org/olat/core/gui/control/BasicController.java` for `translate()` and `getTranslator()` methods
   - Verify `FormBasicController.java` inherits these methods

2. **Translation Resource Storage**
   - Look for `_i18n/` directories alongside controller packages
   - Example: `src/main/java/org/olat/core/gui/_i18n/LocalStrings_de.properties`

3. **Fallback Chains**
   - Examine `src/main/java/org/olat/core/util/i18n/I18nManager.java`
   - Check the `getTranslator` method and `createPackageTranslator` method
   - Verify the fallback bundle order: `de_CH__customizing → de_CH → de__customizing → de → en__customizing → en → en`

4. **Parameter Substitution**
   - Review `I18nManager.java` for `MessageFormat` usage
   - Check test cases in `src/test/java/org/olat/core/util/i18n/I18nTest.java`

5. **Gender Strategies**
   - Look for gender strategy processing in `I18nManager.java`
   - Verify handling of constructs like `Benutzer{in}`

6. **Recursive Key References**
   - Check `PackageTranslator.java` for recursive resolution logic
   - Verify the 10-level depth limit
   - See test evidence in `I18nTest.testRecursiveResolution()`

7. **Missing Key Handling**
   - Examine `I18nManager.java` for debug vs. production behavior
   - Check for `I18nManager.DEBUG_MODE` flag

8. **Velocity Template Usage**
   - Review `src/main/java/org/olat/core/gui/render/VelocityRenderDecorator.java`
   - Verify `$r.translate()` method implementation

9. **Overlay Customization**
   - Check documentation in `I18nManager.java` about overlay mechanism
   - Look for `{userData}/customizing/lang/overlay/{package}/_i18n/LocalStrings_XX__customizing.properties` pattern

## Recommended Next Steps for Investigators

1. Begin with the [Investigation Ledger](12-INVESTIGATION-LEDGER.md) to understand progress
2. Consult the [Repository Baseline](00-REPOSITORY-BASELINE.md) for version and build information
3. Explore specific areas of interest using the [Module Catalog](02-MODULE-CATALOG.md) and [Package Index](03-PACKAGE-AND-SYSTEM-INDEX.md)
4. For localization work, start with [14-I18N-AND-LOCALIZATION.md](14-I18N-AND-LOCALIZATION.md)
5. When verifying claims, always refer back to the source code as the ultimate authority

## Investigation Philosophy

All documentation in this directory should be:
- **Source-grounded**: Every claim should be verifiable against the current source code
- **Navigation-focused**: Organized to help investigators find relevant code quickly
- **Progress-tracking**: Updated regularly to reflect investigation advancement
- **Concise yet thorough**: Balancing detail with usability

*Entry point created: 2026-10-20*
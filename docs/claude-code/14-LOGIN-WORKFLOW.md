# Login Workflow Analysis

This document traces the login workflow in OpenOLAT from initial HTTP request through authentication to session establishment.

## Overview

OpenOLAT uses a server-centric architecture where all authentication state is maintained on the server. The login process involves multiple components working together to verify credentials, establish user sessions, and initialize the user interface.

## Workflow Steps

### 1. Initial Request Processing (`AuthenticatedDispatcher`)

The login workflow begins when an unauthenticated request reaches the `AuthenticatedDispatcher`:

```java
// In AuthenticatedDispatcher.execute()
if (!auth) { // !usess.isAuthenticated()
    // Check for guest login attempt
    String guestAccess = ureq.getParameter(GUEST);
    if (guestAccess == null || !CoreSpringFactory.getImpl(LoginModule.class).isGuestLoginEnabled()) {
        // Store business path for post-login redirect
        String businessPath = extractBusinessPath(ureq, request, uriPrefix);
        if(businessPath != null) {
            usess.putEntryInNonClearedStore(AUTHDISPATCHER_BUSINESSPATH, businessPath);
        }
        forwardToDefaultDispatcher(request, response); // Goes to login screen
        return;
    }
    // ... handle guest login
}
```

For regular login attempts, the request is forwarded to the default dispatcher which serves the login screen.

### 2. Login Form Presentation (`OLATAuthenticationController`)

The login screen is presented by `OLATAuthenticationController` which extends `AuthenticationController`:

```java
public OLATAuthenticationController(UserRequest ureq, WindowControl winControl) {
    super(ureq, winControl, Util.createPackageTranslator(RegistrationManager.class, ureq.getLocale()));
    
    loginComp = createVelocityContainer("olat_log", "olatlogin");
    
    // prepare login form
    loginForm = new WebAuthnAuthenticationForm(ureq, winControl, "olat_login", getTranslator());
    listenTo(loginForm);
    
    loginComp.put("loginForm", loginForm.getInitialComponent());
    
    // Check for login error parameter
    if (ureq.getParameterSet().contains(PARAM_LOGINERROR)) {
        showError(translate("login.error", WebappHelper.getMailConfig("mailReplyTo")));
    }
    
    putInitialPanel(loginComp);
}
```

The controller delegates to either standard form (`WebAuthnAuthenticationForm`) or other specialized login forms.

### 3. Credential Submission (`OLATAuthenticationForm`)

When the user submits credentials, the `OLATAuthenticationForm` processes the submission:

```java
@Override
protected void formOK(UserRequest ureq) {
    if(passEl.isVisible()) {
        doLogin(ureq); // Standard password login
    } else {
        doStart(); // Username-only flow (for user registration)
        fireEvent(ureq, new LoginEvent());
    }
}

private void doLogin(UserRequest ureq) {
    clearError();
    
    String login = loginEl.getValue();
    String pass = passEl.getValue();	
    
    // Check for login blocking (attack prevention)
    if (loginModule.isLoginBlocked(login)) {
        setError("login.blocked", loginModule.getAttackPreventionTimeoutMin().toString());
        return;
    }

    AuthenticationStatus status = new AuthenticationStatus();
    Identity authenticatedIdentity = olatAuthenticationSpi.authenticate(null, login, pass, status);
    
    // Handle various authentication outcomes...
    if (authenticatedIdentity == null) {
        // Handle failed login
        if (loginModule.registerFailedLoginAttempt(login)) {
            setError("login.blocked", loginModule.getAttackPreventionTimeoutMin().toString());
        } else {
            setError("login.error", WebappHelper.getMailConfig("mailReplyTo"));
        }
    } else {
        // Successful authentication
        loginModule.clearFailedLoginAttempts(login);
        fireEvent(ureq, new AuthenticationEvent(authenticatedIdentity, BaseSecurityModule.getDefaultAuthProviderIdentifier()));
    }
}
```

### 4. Authentication Provider (`OLATAuthManager`)

The actual credential verification is delegated to the `OLATAuthManager`:

```java
public Identity authenticate(Identity ident, String login, String password, AuthenticationStatus status) {
    Authentication authentication;	
    if (ident == null) {
        // Check for email instead of username if ident is null
        ident = findIdentityByEmail(login);
        if(ident == null) {
            authentication = securityManager.findAuthenticationByAuthusername(login, "OLAT", BaseSecurity.DEFAULT_ISSUER);
        } else {
            authentication = securityManager.findAuthentication(ident, "OLAT", BaseSecurity.DEFAULT_ISSUER);
        }
    } else {
        authentication = securityManager.findAuthentication(ident,  "OLAT", BaseSecurity.DEFAULT_ISSUER);
    }

    if (authentication == null) {
        // Authentication not found
        if(status != null) {
            status.setStatus(AuthHelper.LOGIN_FAILED);
        }
        return null;
    }

    // Verify credentials
    if (securityManager.checkCredentials(authentication, password)) {
        // Optional: upgrade password hash algorithm if needed
        Algorithm algorithm = Algorithm.find(authentication.getAlgorithm());
        Algorithm defAlgorithm = loginModule.getDefaultHashAlgorithm();
        if(Algorithm.md5.equals(algorithm) || algorithm != defAlgorithm) {
            authentication = securityManager.updateCredentials(authentication, password, defAlgorithm);
        }
        
        Identity identity = authentication.getIdentity();
        
        // Final permission check
        if(!securityManager.isIdentityLoginAllowed(identity, "OLAT")) {
            // Set appropriate status for inactive/pending/denied
            if(status != null) {
                if(Identity.STATUS_INACTIVE.equals(identity.getStatus())) {
                    status.setStatus(AuthHelper.LOGIN_INACTIVE);
                } else if (Identity.STATUS_PENDING.equals(identity.getStatus())) {
                    status.setStatus(AuthHelper.LOGIN_PENDING);
                } else {
                    status.setStatus(AuthHelper.LOGIN_DENIED);
                }
            }
            return identity;
        }
        
        // Handle WebDAV password upgrade if applicable
        if(identity != null && webDAVAuthManager != null) {
            webDAVAuthManager.upgradePassword(identity, login, password);
        }
        
        status.setProvider("OLAT");
        status.setStatus(AuthHelper.LOGIN_OK);
        return identity;
    } else {
        // Invalid credentials
        if(status != null) {
            status.setStatus(AuthHelper.LOGIN_FAILED);
        }
        return null;
    }
}
```

### 5. Credential Verification (`BaseSecurityManager`)

The core password verification happens in `BaseSecurityManager.checkCredentials()`:

```java
@Override
public boolean checkCredentials(Authentication authentication, String password) {
    Algorithm algorithm = Algorithm.find(authentication.getAlgorithm());
    String hash = Encoder.encrypt(password, authentication.getSalt(), algorithm);
    return hash != null && authentication.getCredential() != null
           && MessageDigest.isEqual(authentication.getCredential().getBytes(), hash.getBytes());
}
```

### 6. Session Establishment (`AuthHelper.doLogin`)

After successful authentication, control returns to `AuthHelper.doLogin()`:

```java
public static int doLogin(Identity identity, String authProvider, UserRequest ureq) {
    int initializeStatus = initializeLogin(identity, authProvider, ureq, false);
    if (initializeStatus != LOGIN_OK) {
        return initializeStatus; // login not successful
    }

    // do logging
    ThreadLocalUserActivityLogger.log(OlatLoggingAction.OLAT_LOGIN, AuthHelper.class, LoggingResourceable.wrap(identity));

    // successful login, reregister window
    ChiefController occ;
    if(ureq.getUserSession().getRoles().isGuestOnly()){
        occ = createGuestHome(ureq);
    }else{
        occ = createAuthHome(ureq);
    }

    Window currentWindow = occ.getWindow();
    currentWindow.setUriPrefix(WebappHelper.getServletContextPath() + DispatcherModule.PATH_AUTHENTICATED);
    Windows.getWindows(ureq).registerWindow(occ);
    ureq.overrideWindowComponentID(currentWindow.getDispatchID());

    // Handle redirect logic
    RedirectMediaResource redirect;
    String redirectPath = (String) ureq.getUserSession().getEntry(AuthenticatedDispatcher.AUTHDISPATCHER_REDIRECT_PATH);
    String redirectTo = (String)ureq.getUserSession().getEntry("redirect-bc");
    if(StringHelper.containsNonWhitespace(redirectPath)) {
        String url = WebappHelper.getServletContextPath() + DispatcherModule.PATH_AUTHENTICATED + redirectPath + "?oow=" + currentWindow.getDispatchID();
        redirect = new RedirectMediaResource(url);
    } else if(StringHelper.containsNonWhitespace(redirectTo)) {
        String url = WebappHelper.getServletContextPath() + DispatcherModule.PATH_AUTHENTICATED + redirectTo + "?oow=" + currentWindow.getDispatchID();
        redirect = new RedirectMediaResource(url);
    } else {
        // redirect to AuthenticatedDispatcher
        URLBuilder ubu = new URLBuilder(WebappHelper.getServletContextPath() + DispatcherModule.PATH_AUTHENTICATED,
                currentWindow.getInstanceId(), "1", currentWindow.getCsrfToken());
        try(StringOutput sout = new StringOutput(30)) {
            ubu.buildURI(sout, null, null);
            redirect = new RedirectMediaResource(sout.toString());
        } catch(IOException e) {
            log.error("", e);
            redirect = null;
        }
    }
    ureq.getDispatchResult().setResultingMediaResource(redirect);
    return LOGIN_OK;
}
```

### 7. Post-Login UI Initialization

The `createAuthHome()` method establishes the initial post-login interface:

```java
public static ChiefController createAuthHome(UserRequest ureq) {
    if (!ureq.getUserSession().isAuthenticated()) throw new AssertException("not authenticated!");

    BaseFullWebappControllerParts authSitesAndNav = new AuthBFWCParts();
    return new BaseFullWebappController(ureq, authSitesAndNav);
}
```

The `AuthBFWCParts` (Base Full Webapp Controller Parts) defines the initial UI components including navigation, toolbar, and content area.

## Key Implementation Details

### Authentication Flow Summary

1. **Request Interception**: `AuthenticatedDispatcher` detects unauthenticated request
2. **Login Form**: `OLATAuthenticationController` presents login interface
3. **Credential Validation**: `OLATAuthenticationForm` collects and validates input
4. **Provider Delegation**: `OLATAuthManager` handles OLAT-specific authentication
5. **Identity Lookup**: Find authentication record by username/email
6. **Password Check**: `BaseSecurityManager.checkCredentials()` verifies password
7. **Permission Check**: `isIdentityLoginAllowed()` validates account status
8. **Session Setup**: `AuthHelper.initializeLogin()` establishes user session
9. **UI Initialization**: `createAuthHome()` creates initial post-login interface
10. **Redirect Handling**: Process stored redirect path or go to default home

### Security Features

- **Password Hashing**: Uses configurable algorithms (MD5, SHA, Argon2id) with per-user salt
- **Credential Verification**: Uses `MessageDigest.isEqual()` for timing-attack safe comparison
- **Login Blocking**: Tracks failed attempts and temporarily blocks after threshold
- **Session Protection**: Session rotation on login to prevent session fixation
- **Audit Logging**: All login attempts logged via `ThreadLocalUserActivityLogger`
- **Password History**: Prevents reuse of recent passwords
- **Account Status Checks**: Blocks inactive, pending, or denied accounts

### Configuration Points

Login behavior is configurable via:
- `${login.attackPreventionEnabled:true}` - Enable brute force protection
- `${login.AttackPreventionMaxattempts:5}` - Max attempts before block
- `${login.AttackPreventionTimeoutmin:5}` - Block duration in minutes
- `${login.using.username.or.email.enabled:true}` - Allow login via email
- `${login.faq.url}` - URL for login help/FAQ
- `${login.attackPreventionEnabled:true}` - Enable/disable attack prevention

## fLMS Customization Opportunities

For fLMS customization, the login workflow can be extended through:

1. **Alternative Authentication Providers**: Implement new `AuthenticationProvider` beans
2. **Login Form Modification**: Extend or replace `OLATAuthenticationForm` 
3. **Post-Login Processing**: Add listeners to `AuthenticationEvent` via EventBus
4. **Session Initialization**: Extend `AuthHelper.initializeLogin()` behavior
5. **UI Customization**: Modify `AuthBFWCParts` or create custom `BaseFullWebappControllerParts`
6. **Redirect Logic**: Alter post-login redirect behavior via session attributes
7. **Password Policy**: Customize validation via `PasswordValidationRulesFactory`
8. **Attack Prevention**: Adjust blocking thresholds and mechanisms

## Files Involved in Login Workflow

- `org.olat.dispatcher.AuthenticatedDispatcher` - Request interception and routing
- `org.olat.login.OLATAuthenticationController` - Login screen controller
- `org.olat.login.auth.OLATAuthenticationForm` - Credential collection and validation
- `org.olat.login.auth.OLATAuthManager` - OLAT-specific authentication logic
- `org.olat.basesecurity.BaseSecurityManager` - Core security operations
- `org.olat.basesecurity.AuthHelper` - Session establishment and post-login setup
- `org.olat.login.LoginModule` - Login-specific configuration and attack prevention
- `org.olat.basesecurity.AuthenticationImpl` - Authentication data model

## Sequence Summary

```
HTTP Request → 
AuthenticatedDispatcher (detects unauthenticated) → 
Forward to Default Dispatcher (serves login form) → 
OLATAuthenticationController (presents login UI) → 
OLATAuthenticationForm (collects credentials) → 
OLATAuthManager (verifies credentials via DB) → 
BaseSecurityManager (checks password hash) → 
AuthHelper.doLogin() (establishes session) → 
AuthHelper.createAuthHome() (creates initial UI) → 
AuthenticatedDispatcher (processes post-login redirect) → 
Windows.dispatchRequest() (renders initial page)
```
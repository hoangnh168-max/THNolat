# OpenOLAT Module Catalog

This document catalogs all first-party modules in the OpenOLAT LMS. Each module is a self-contained unit of functionality that can be enabled/disabled via configuration.

## Module Structure

Each module typically follows this structure:
- `src/main/java/org/olat/modules/[module-name]/[ModuleName]Module.java` - Main module class extending `AbstractSpringModule`
- `src/main/java/org/olat/modules/[module-name]/_content/` - Velocity templates
- `src/main/java/org/olat/modules/[module-name]/_i18n/` - Internationalization properties
- `src/main/java/org/olat/modules/[module-name]/_spring/` - Spring configuration files
- Additional packages for managers, services, ui, model, restapi, etc. as needed

## Module List

| Module | Description | Primary Class |
|--------|-------------|---------------|
| **adobeconnect** | Integration with Adobe Connect web conferencing | `AdobeConnectModule` |
| **appointments** | Appointment scheduling and management | *(to be investigated)* |
| **assessment** | Assessment and test creation, delivery, and grading | *(to be investigated)* |
| **audiovideorecording** | Audio/video recording capabilities | `AVModule` |
| **bigbluebutton** | Integration with BigBlueButton web conferencing | `BigBlueButtonModule` |
| **card2brain** | Integration with Card2Brain flashcard learning platform | `Card2BrainModule` |
| **catalog** | Course catalog and course discovery | `CatalogV2Module` |
| **ceditor** | Content editor for rich text/html content | `ContentEditorModule` |
| **cemedia** | Media management and streaming | `MediaModule` |
| **certificationprogram** | Certification program management | `CertificationModule` |
| **co** | *(unclear - possibly "Company" or "Contact")* | *(to be investigated)* |
| **coach** | Coaching and mentoring functionality | `CoachingModule` |
| **contacttracing** | Contact tracing (likely pandemic-related) | `ContactTracingModule` |
| **cp** | *(unclear - possibly "Course Points" or similar)* | *(to be investigated)* |
| **creditpoint** | Credit point management system | `CreditPointModule` |
| **curriculum** | Curriculum and learning path management | `CurriculumModule` |
| **dcompensation** | *(unclear - possibly "Degree Compensation")* | *(to be investigated)* |
| **docpool** | Document pool for sharing resources | `DocumentPoolModule` |
| **edubase** | Educational resource database | `EdubaseModule` |
| **edusharing** | Educational resource sharing platform | `EdusharingModule` |
| **externalsite** | External site integration/linking | *(to be investigated)* |
| **fo** | Forum/discussion functionality | `ForumModule` |
| **forms** | Form creation and evaluation (likely EvaluationForms) | `EvaluationFormsModule` |
| **glossary** | Glossary and term management | *(to be investigated)* |
| **gotomeeting** | Integration with GoToMeeting web conferencing | `GoToMeetingModule` |
| **grade** | Grade management and grading tools | `GradeModule` |
| **grading** | Grading workflows and assessment | `GradingModule` |
| **immunityproof** | Immunity/vaccination proof management | `ImmunityProofModule` |
| **invitation** | Invitation management for courses/users | `InvitationModule` |
| **jupyterhub** | Integration with JupyterHub for notebooks | `JupyterHubModule` |
| **lecture** | Lecture management and scheduling | `LectureModule` |
| **library** | Library resource management | `LibraryModule` |
| **mediassite** | Integration with Mediasite video platform | `MediaSiteModule` |
| **message** | Internal messaging and notifications | *(to be investigated)* |
| **oaipmh** | OAI-PMH protocol for metadata sharing with configurable set types and search engine integration | `OAIPmhModule` |
| **openbadges** | Open Badges integration for micro-credentials | `OpenBadgesModule` |
| **opencast** | Integration with Opencast lecture capture system | `OpencastModule` |
| **openmeetings** | Integration with OpenMeetings web conferencing | `OpenMeetingsModule` |
| **portfolio** | E-portfolio and competency tracking | `PortfolioV2Module` |
| **project** | Project management and collaboration | `ProjectModule` |
| **qpool** | Question pool management for assessments | `QuestionPoolModule` |
| **quality** | Quality management and quality assurance | `QualityModule` |
| **reminder** | Reminder and notification system | `ReminderModule` |
| **roommanagement** | Room and facility booking management | `RoomManagementModule` |
| **scorm** | SCORM (Sharable Content Object Reference Model) support | *(to be investigated)* |
| **selectus** | Applicant tracking and recruitment system (positions, applications, reviews) | `RecruitingModule` |
| **sharedfolder** | Shared folder and file collaboration | *(to be investigated)* |
| **sharepoint** | Integration with Microsoft SharePoint | `SharePointModule` |
| **taxonomy** | Taxonomy and classification system | `TaxonomyModule` |
| **teams** | Integration with Microsoft Teams | `TeamsModule` |
| **todo** | Personal task and to-do list management | `ToDoModule` |
| **topicbroker** | Topic broker for course element exchange | `TopicBrokerModule` |
| **video** | Video management and streaming | `VideoModule` |
| **vitero** | Integration with Vitero web conferencing | `ViteroModule` |
| **webFeed** | RSS/Atom feed aggregation and display | *(to be investigated)* |
| **wiki** | Collaborative wiki functionality | `WikiModule` |
| **zoom** | Integration with Zoom web conferencing | `ZoomModule` |

### Core System Modules (outside modules/ directory)

In addition to the 46 modules in the modules directory, OpenOLAT has core system modules located directly under `org/olat`:

| Module Area | Description | Key Classes |
|-------------|-------------|-------------|
| **Course Management** | Core course creation, execution, and lifecycle | `CourseModule` (`org.olat.course.CourseModule`) |
| **Assessment Engine** | Test execution, submission, and evaluation | `AssessmentModule` (`org.olat.course.assessment.AssessmentModule`) |
| **Certificate Management** | Certificate generation and management | `CertificatesModule` (`org.olat.course.certificate.CertificatesModule`) |
| **Repository** | Resource storage, versioning, and access control | `RepositoryModule` (`org.olat.repository.RepositoryModule`) |
| **Resource Access Control** | Permissions and access control for resources | `AccessControlModule` (`org.olat.resource.accesscontrol.AccessControlModule`) |
| **Base Security** | Authentication, authorization, and role management | `BaseSecurityModule` (`org.olat.basesecurity.BaseSecurityModule`) |
| **Organisation Management** | Organizational structure and hierarchy | `OrganisationModule` (`org.olat.basesecurity.OrganisationModule`) |
| **Media Server** | Media streaming and processing capabilities | `MediaServerModule` (`org.olat.basesecurity.MediaServerModule`) |
| **Group Management** | Course groups and business groups | `BusinessGroupModule` (`org.olat.group.BusinessGroupModule`) |
| **Login Systems** | Various authentication methods | `LoginModule` (`org.olat.login.LoginModule`), `OAuthLoginModule`, `LDAPLoginModule`, etc. |
| **Instant Messaging** | Real-time chat and messaging | `InstantMessagingModule` (`org.olat.instantMessaging.InstantMessagingModule`) |
| **IMS Standards** | LTI, QTI, and other educational standards | `LTIModule` (`org.olat.ims.lti.LTIModule`), `LTI13Module`, `QTI21Module` |
| **Search** | Full-text search and indexing capabilities | `SearchModule` (`org.olat.search.SearchModule`) |
| **REST API** | RESTful web services interface | `RestModule` (`org.olat.restapi.RestModule`) |
| **Monitoring** | System monitoring and health checks | `MonitoringModule` (`org.olat.restapi.system.MonitoringModule`) |
| **User Management** | User profiles, properties, and preferences | `UserModule` (`org.olat.user.UserModule`) |
| **Social Features** | Social networking and collaboration features | `SocialModule` (`org.olat.social.SocialModule`) |
| **Shibboleth** | Shibboleth SSO integration | `ShibbolethModule` (`org.olat.shibboleth.ShibbolethModule`) |
| **MCP** | Model Context Protocol for AI integrations | `McpModule` (`org.olat.mcp.McpModule`) |
| **Office Tools** | User tools and administration utilities | `UserToolsModule` (`org.olat.admin.user.tools.UserToolsModule`) |
| **System Setup** | Initial system configuration and setup | `SetupModule` (`org.olat.admin.setup.SetupModule`) |
| **Registration** | User registration and invitation workflows | `SystemRegistrationModule` (`org.olat.admin.registration.SystemRegistrationModule`) |
| **Layout Management** | Page layout and template management | `LayoutModule` (`org.olat.admin.layout.LayoutModule`) |
| **Landing Pages** | Custom landing pages and site entry points | `LandingPagesModule` (`org.olat.admin.landingpages.LandingPagesModule`) |
| **Administration** | Core administrative functions | `AdminModule` (`org.olat.admin.AdminModule`) |

## Investigation Status

- [x] Listed all 46 modules from `modules/` directory
- [x] Investigated each module's responsibilities and key classes (36/46 investigated)
- [ ] Documented core system modules outside modules/ directory
- [ ] Mapped module dependencies and interactions
- [ ] Identified extension points and integration mechanisms

*Note: This catalog is a work in progress. Each module's description needs to be verified by examining its source code, particularly the main module class and any available documentation.*

*Catalog updated: 2026-10-20*